# 协作指南

面向所有参与本项目的同学。第一次上手请按顺序读完第一部分，再照第二部分操作。
项目整体说明见 [demo_readme.md](demo_readme.md)，实验结论见 [EXPERIMENTS.md](EXPERIMENTS.md)。

## 一、开始之前：三件事必须先处理

### 1. 模型文件不在仓库里

仓库只包含代码和测试素材（几百 KB），**不含模型权重**（small 模型约 483 MB）。
直接运行 `demo.py` 会提示"模型目录不存在"，这是正常的，不是环境装错了。

需要自己下载 4 个文件，放到 `models/faster-whisper-small/`：

```
https://hf-mirror.com/Systran/faster-whisper-small/resolve/main/model.bin
https://hf-mirror.com/Systran/faster-whisper-small/resolve/main/config.json
https://hf-mirror.com/Systran/faster-whisper-small/resolve/main/tokenizer.json
https://hf-mirror.com/Systran/faster-whisper-small/resolve/main/vocabulary.txt
```

浏览器打开链接直接下载即可，四个文件缺一不可。（`hf-mirror.com` 是 HuggingFace 的国内镜像；
直连 `huggingface.co` 通常会卡在 0 字节。）

### 2. Python 必须是 3.12

不要用系统默认的 3.13 / 3.14——`ctranslate2`、`onnxruntime` 等包还没有对应的预编译 wheel，
pip 会尝试现场编译然后失败。

```powershell
uv venv .venv --python 3.12 --seed
.\.venv\Scripts\python.exe -m pip install -e . -i https://pypi.tuna.tsinghua.edu.cn/simple
```

装完之后跑 `.\.venv\Scripts\python.exe demo.py`，能识别出英文句子就说明环境没问题。

### 3. 网络：git 可能需要配代理

直连 GitHub 的常见症状是 `Recv failure: Connection was reset` 或长时间无响应。
如果你本地有代理（假设端口是 7897），执行：

```powershell
git config --global http.proxy http://127.0.0.1:7897
git config --global https.proxy http://127.0.0.1:7897
# 以后想取消：
# git config --global --unset http.proxy
# git config --global --unset https.proxy
```

没有代理就别配，否则代理没开时 git 会直接连接失败。

### 你会拿到什么、不会拿到什么

| 内容 | 是否在仓库里 | 说明 |
|---|---|---|
| 代码、脚本、文档 | 有 | `faster_whisper/`、`eval_zh.py`、`transcribe.py` 等 |
| 朗读稿 + 合成音频 | 有 | `samples/reading_script.txt`、`samples/reading_script_tts.wav` |
| 团队真人录音 | 有 | `samples/speaker/`，命名 `speaker_<名字>.<后缀>` |
| 模型权重 | **没有** | 自己下载，见上面第 1 条 |
| 第一轮的私人录音 | **没有** | 在 `samples/round1/`，音频已被 `.gitignore` 排除 |
| `.venv/`、`.vscode/` | **没有** | 各自建各自的环境，互不干扰 |

## 二、标准工作流

```powershell
# 1. 克隆（不要用网页上的 Download ZIP——那样没有 .git 目录，改完无法提交和推送）
git clone https://github.com/rookie1123/faster_whisper_demo.git
cd faster_whisper_demo

# 2. 每次开始工作前，先同步主分支
git checkout main
git pull

# 3. 从最新的 main 建自己的分支（不要在 main 上直接改）
git checkout -b feat/gpu-support

# 4. 改代码……

# 5. 提交并推送
git add -A
git status                       # 务必看一眼，确认没把 .venv、models 之类加进来
git commit -m "feat: 支持 GPU 加速"
git push -u origin feat/gpu-support
```

推完之后打开仓库网页，会出现一条黄色横幅和一个 **Compare & pull request** 按钮——
点它，填写标题和描述，再点一次 **Create pull request**，到这一步 PR 才算真正创建。

> **PR 不会被自动创建，必须手动点两下。**
>
> `git push` 只是把分支传到服务器上，GitHub 顶多给一个"要不要开 PR"的提示。
> 如果你推完分支就以为完成了，仓库主人收不到任何通知，也不知道你做了什么。
>
> 如果那条黄色横幅没出现（它有时效，也可能被浏览器插件挡住），直接打开
> `https://github.com/rookie1123/faster_whisper_demo/compare/main...你的分支名`
> 手动创建，效果完全一样。

**PR 被合并之前，改动不会进入 main。**

如果 review 时被要求修改，直接在同一个分支上继续提交并推送，PR 会自动更新，不必重开。

## 三、分支与提交约定

| 前缀 | 用途 | 例子 |
|---|---|---|
| `feat/` | 新功能 | `feat/streaming-asr` |
| `fix/` | 修 bug | `fix/srt-timestamp` |
| `exp/` | 实验（结果不一定合入） | `exp/medium-model` |
| `docs/` | 只改文档 | `docs/update-readme` |

提交信息：一句话说清楚做了什么，不要写"更新""修改"这种没有信息量的内容。

```
好：fix: SRT 时间戳超过 1 小时时格式错误
差：改了一下
```

提交粒度：一个改动一个提交。不要把三天的各种杂事塞进一个 commit，
那样 review 时无从看起，出问题也无法单独回滚。

## 四、PR 检查清单

提交之前自己先过一遍：

- [ ] `git status` 里没有出现 `models/`、`.venv/`、个人录音、`eval_report.md`
- [ ] 改动只做了一件事，没有顺带改无关文件
- [ ] 如果改了脚本，本地实际跑过一次，不是"看着没问题"
- [ ] 如果改了评测逻辑，说明了它对已有结论的影响（比如 CER 数字会不会变）
- [ ] PR 描述写清楚：做了什么、为什么这么做、怎么验证的

## 五、哪些文件容易冲突

| 文件 | 风险 | 处理方式 |
|---|---|---|
| `reports/*.md` | 不会冲突 | 每次运行生成带时间戳的新文件，天然隔离 |
| `samples/*.wav` | **无法自动合并** | 二进制文件，两人同时加素材必须人工决定留哪个；加素材前先在群里说一声 |
| `EXPERIMENTS.md`、`demo_readme.md` | 中等 | 文本冲突可手工解决，注意别覆盖别人的结论 |
| `prompts.py` | 中等 | 都在同一个字典里加词表，改到相邻行才冲突 |
| `eval_zh.py`、`transcribe.py` | 中等 | 改动前先 `git pull`，缩小冲突窗口 |

`eval_report.md` 已被排除在仓库之外：它每次运行都会被覆盖，多人提交必然冲突，
现在只作为本地查看用的临时文件存在。

推送时遇到冲突，按这个流程处理：

```powershell
git checkout main
git pull
git checkout 你的分支
git rebase main                  # 把 main 的最新改动接到你的分支下面
# 手工解决冲突后
git add -A
git rebase --continue
git push --force-with-lease
```

## 六、不要做的事

- **不要直接往 `main` 推送**。分支保护已开启，会被拒绝；所有改动都走 PR。
- **不要提交模型权重、虚拟环境、个人录音**。`.gitignore` 已经挡住，但 `git add -f` 能强行绕过——
  别这么干，483 MB 的模型会让仓库体积失控，推送也会失败。
- **不要在别人的分支上继续开发**。要基于别人的改动继续做，等他合并进 main 后再 `git pull`。
- **不要提交 `eval_report.md`**。它是本地临时文件，正式记录在 `reports/` 里。
- **不要用 `git push --force`**。万不得已时用 `--force-with-lease`；
  且只能用在"还没人基于它开发"的自己的分支上。

## 七、遇到问题怎么办

先查文档：环境问题看 [demo_readme.md](demo_readme.md) 的"快速开始"，
实验方法看 [EXPERIMENTS.md](EXPERIMENTS.md)。

还是解决不了，把**完整的报错信息**贴到群里——包括执行的命令和报错最后几行。
只说"跑不起来"别人没法定位问题。
