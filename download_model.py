#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""下载 faster-whisper 预转换模型到 models/ 目录。

用法:
    python download_model.py medium
    python download_model.py large-v3
    python download_model.py --list
    python download_model.py medium --endpoint https://huggingface.co

设计说明:
    - 本机直连 huggingface.co 会超时, 因此默认走国内镜像 https://hf-mirror.com
    - 采用纯 HTTP 流式下载(不依赖 huggingface_hub):
        huggingface_hub 会为每个文件创建 .lock 再删除, 本机安全策略拦截删除操作,
        会导致下载进程被中断。纯 HTTP 只写文件、不删文件, 可稳定运行。
    - 支持断点续传: 中断后重新执行同一条命令即可接着下
    - 已完整下载的模型会自动跳过
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_ENDPOINT = "https://hf-mirror.com"
USER_AGENT = "download_model.py/1.0"
CHUNK = 1024 * 1024

ROOT = Path(__file__).resolve().parent
MODELS_DIR = ROOT / "models"
REPO_PREFIX = "Systran/faster-whisper-"

# 支持的标准尺寸 -> HuggingFace 仓库
SIZES = {
    "tiny": "tiny",
    "tiny.en": "tiny.en",
    "base": "base",
    "small": "small",
    "medium": "medium",
    "large-v1": "large-v1",
    "large-v2": "large-v2",
    "large-v3": "large-v3",
    "large": "large-v3",  # large 别名, 与 OpenAI 命名一致
    "large-v3-turbo": "large-v3-turbo",
}

# 模型运行需要的文件, 其余(.git 等)不下载
REQUIRED = ["config.json", "model.bin", "tokenizer.json", "vocabulary.txt"]
OPTIONAL = ["preprocessor_config.json", "README.md", ".gitattributes"]

# 各尺寸 model.bin 的近似字节数, 用于校验与跳过判断
APPROX_BYTES = {
    "tiny": 75_522_048,
    "tiny.en": 75_522_048,
    "base": 145_313_792,
    "small": 483_546_902,
    "medium": 1_527_906_378,
    "large-v1": 3_085_082_368,
    "large-v2": 3_085_082_368,
    "large-v3": 3_085_082_368,
    "large-v3-turbo": 1_617_881_600,
}


def human(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def list_sizes() -> None:
    print("支持的模型尺寸:")
    for name in sorted(SIZES):
        canonical = SIZES[name]
        size = APPROX_BYTES.get(canonical, 0)
        note = "" if name == canonical else f"(= {canonical})"
        print(f"  {name:<16} {REPO_PREFIX + canonical:<40} 约 {human(size):>10} {note}")


def http_json(url: str, timeout: int = 20):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def remote_sizes(endpoint: str, repo_id: str) -> dict:
    """问 API 要每个文件的真实大小, 用于校验。"""
    data = http_json(f"{endpoint}/api/models/{repo_id}?blobs=true")
    out = {}
    for s in data.get("siblings", []):
        name = s.get("rfilename")
        if name:
            out[name] = s.get("size") or 0
    return out


def download_file(url: str, dest: Path, expected: int, retries: int = 6) -> int:
    """流式下载到 dest, 支持断点续传。返回最终字节数。"""
    dest.parent.mkdir(parents=True, exist_ok=True)

    for attempt in range(1, retries + 1):
        have = dest.stat().st_size if dest.exists() else 0
        if expected and have == expected:
            return have
        if expected and have > expected:
            have = 0  # 大小异常, 重新下
            try:
                dest.unlink()
            except OSError:
                pass

        headers = {"User-Agent": USER_AGENT}
        if have:
            headers["Range"] = f"bytes={have}-"

        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=60) as r:
                if r.status == 206:
                    mode, total = "ab", have + int(r.headers.get("Content-Length") or 0)
                else:
                    mode, have, total = "wb", 0, int(r.headers.get("Content-Length") or 0)

                t0 = time.time()
                done = have
                last_report = 0.0
                with open(dest, mode) as f:
                    while True:
                        chunk = r.read(CHUNK)
                        if not chunk:
                            break
                        f.write(chunk)
                        done += len(chunk)
                        now = time.time()
                        if total and now - last_report >= 3:
                            last_report = now
                            speed = (done - have) / max(now - t0, 0.01) / 1024 / 1024
                            pct = done / total * 100
                            eta = (total - done) / max(speed * 1024 * 1024, 1)
                            print(f"\r    {human(done)}/{human(total)} "
                                  f"({pct:5.1f}%)  {speed:5.2f} MB/s  ETA {eta:4.0f}s",
                                  end="", flush=True)
            if total:
                print()
            final = dest.stat().st_size
            if expected and final != expected:
                raise IOError(f"大小不符: 得到 {final}, 期望 {expected}")
            return final
        except (urllib.error.URLError, IOError, OSError) as exc:
            wait = min(2 ** attempt, 20)
            print(f"\n    [重试 {attempt}/{retries}] {type(exc).__name__}: {exc}  "
                  f"{wait}s 后继续")
            time.sleep(wait)

    raise RuntimeError(f"下载失败, 已重试 {retries} 次: {url}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="下载 faster-whisper 预转换模型(默认走 hf-mirror 镜像, 支持断点续传)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            "  python download_model.py medium\n"
            "  python download_model.py medium --endpoint https://huggingface.co\n"
            "  python download_model.py --list\n"
            "\n"
            "用 run.bat 启动可避免选错解释器:\n"
            "  run.bat download_model.py medium\n"
        ),
    )
    parser.add_argument("size", nargs="?", help="模型尺寸, 如 tiny / small / medium / large-v3")
    parser.add_argument("--list", action="store_true", help="列出支持的模型尺寸后退出")
    parser.add_argument("--repo", default=None, help="直接指定 HuggingFace 仓库名, 覆盖 size")
    parser.add_argument("--endpoint", default=None, help=f"镜像地址, 默认 {DEFAULT_ENDPOINT}")
    parser.add_argument("--outdir", default=None, help="输出目录, 默认 models/faster-whisper-<size>")
    parser.add_argument("--force", action="store_true", help="忽略已存在的完整文件, 重新下载")
    parser.add_argument("--required-only", action="store_true", help="只下运行必需文件")

    if len(sys.argv) == 1:
        parser.print_help()
        return 0
    args = parser.parse_args()

    if args.list:
        list_sizes()
        return 0

    endpoint = (args.endpoint or os.environ.get("HF_ENDPOINT") or DEFAULT_ENDPOINT).rstrip("/")

    if args.repo:
        repo_id = args.repo
        canonical = args.repo.rsplit("/", 1)[-1].replace("faster-whisper-", "")
        out_name = "faster-whisper-" + canonical
    else:
        if not args.size:
            print("[错误] 缺少模型尺寸参数。用 --list 查看可选值。", file=sys.stderr)
            parser.print_help()
            return 2
        key = args.size.strip()
        if key not in SIZES:
            print(f"[错误] 未知尺寸: {key}", file=sys.stderr)
            list_sizes()
            return 2
        canonical = SIZES[key]
        repo_id = REPO_PREFIX + canonical
        out_name = "faster-whisper-" + canonical

    outdir = Path(args.outdir) if args.outdir else (MODELS_DIR / out_name)
    if not outdir.is_absolute():
        outdir = ROOT / outdir
    approx = APPROX_BYTES.get(canonical, 0)

    print("=" * 66)
    print(f"  仓库      : {repo_id}")
    print(f"  镜像      : {endpoint}")
    print(f"  输出目录  : {outdir}")
    print("=" * 66)

    # 取远程文件清单与大小
    try:
        sizes = remote_sizes(endpoint, repo_id)
    except Exception as exc:  # noqa: BLE001
        print(f"[错误] 无法获取仓库信息: {type(exc).__name__}: {exc}")
        print("       可尝试 --endpoint https://huggingface.co")
        return 1

    wanted = list(REQUIRED) if args.required_only else (REQUIRED + OPTIONAL)
    plan = [(name, sizes[name]) for name in wanted if name in sizes]
    if not plan:
        print("[错误] 仓库中没有找到预期的文件")
        return 1

    # 已完整则跳过
    skip_all = True
    for name, size in plan:
        dest = outdir / name
        if not dest.exists() or (size and dest.stat().st_size != size):
            skip_all = False
            break
    if skip_all and not args.force:
        print(f"[跳过] 已存在且完整: {outdir}")
        for name, _ in plan:
            print(f"    {name:<28} {human((outdir / name).stat().st_size)}")
        return 0

    total_bytes = sum(s for _, s in plan)
    print(f"  待下载    : {len(plan)} 个文件, 共 {human(total_bytes)}")
    print("-" * 66)

    t0 = time.time()
    for name, size in plan:
        dest = outdir / name
        url = f"{endpoint}/{repo_id}/resolve/main/{name}"
        if dest.exists() and size and dest.stat().st_size == size and not args.force:
            print(f"  [跳过] {name:<28} {human(size)}")
            continue
        have = dest.stat().st_size if dest.exists() else 0
        tag = f"续传自 {human(have)}" if have and size and have < size else "开始"
        print(f"  [下载] {name:<28} {human(size)}  ({tag})")
        got = download_file(url, dest, size)
        print(f"  [完成] {name:<28} {human(got)}")

    # 校验 model.bin
    model_bin = outdir / "model.bin"
    print("-" * 66)
    ok = True
    if model_bin.exists():
        exp = sizes.get("model.bin", approx)
        got = model_bin.stat().st_size
        if exp and got != exp:
            ok = False
            print(f"[警告] model.bin 大小异常: {human(got)} (期望 {human(exp)})")
        else:
            print(f"model.bin 校验通过: {human(got)}")
    else:
        ok = False
        print("[警告] 未找到 model.bin")

    print(f"耗时: {time.time() - t0:.1f}s")
    if ok:
        print(f"[完成] {outdir}")
        print()
        print("用法示例:")
        print(f"  run.bat eval_zh.py samples\\zh_tts_1.wav samples\\zh_tts_1.txt --models {out_name}")
        print(f"  run.bat transcribe.py samples\\zh_tts_1.wav --model {out_name} --srt")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
