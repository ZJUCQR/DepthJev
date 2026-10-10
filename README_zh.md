<div align="center">

<h1>🧭 DepthJev</h1>

<h3>将深度感知转化为文本的具身导航</h3>

<p>
  <a href="https://zjucqr.github.io/DepthJev/"><img src="https://img.shields.io/badge/project-page-0ea5e9?logo=githubpages&logoColor=white" alt="Project page"></a>
  <a href="https://github.com/ZJUCQR/DepthJev/actions/workflows/lint.yml"><img src="https://github.com/ZJUCQR/DepthJev/actions/workflows/lint.yml/badge.svg" alt="lint"></a>
  <img src="https://img.shields.io/badge/python-3.11-3776AB?logo=python&logoColor=white" alt="Python 3.11">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-green" alt="Apache-2.0"></a>
  <img src="https://img.shields.io/badge/EB--Navigation-46.7%25-orange" alt="EB-Navigation 成功率 46.7%">
  <img src="https://img.shields.io/badge/latency-0.76%20s%2Fstep-blueviolet" alt="每步 0.76 s">
</p>

<p>
  <a href="https://zjucqr.github.io/DepthJev/"><b>项目主页</b></a> ·
  <a href="#how-it-works">工作原理</a> ·
  <a href="#getting-started">快速开始</a> ·
  <a href="#results">实验结果</a> ·
  <a href="#citation">引用</a>
</p>

<p><a href="README.md">English</a> | <b>简体中文</b></p>

</div>

<p align="center">
  <img src="assets/teaser.gif" width="100%" alt="DepthJev 在一个 EB-Navigation 回合上的记录：带检测框的相机画面、按五个扇区扫过的 Depth Anything 3 米制深度，以及每一步 Jev 读到的文本事实">
</p>

**DepthJev** 是 [EmbodiedBench](https://github.com/EmbodiedBench/EmbodiedBench) EB-Navigation 上的导航智能体。它用 **Depth Anything 3** 把每帧 RGB 转成米制深度，用 **OWLv2** 检测目标，再把几何信息写成简短的文字事实。**Jev** 决策模型只读这些事实、从不看图像，据此选出下一个动作。

<p align="center">
  <img src="assets/how-it-works.png" width="100%" alt="DepthJev 流程：RGB 观测、任务与历史 → 米制深度与目标检测 → 文本事实 → Jev 导航动作 → 下一次观测">
</p>

## ✨ 亮点

- 📈 **不看图也能打。** EB-Navigation 全部 300 题成功率 46.7%。按 EmbodiedBench 论文的结果，高于 Claude-3.5-Sonnet 的 44.7%，比不看图的 GPT-4o（17.4%）高 29.3 个点。
- 🧭 **长程任务稳得住。** `long_horizon` 子集 41.7%，仅次于 GPT-4o（55.0%）；Claude-3.5-Sonnet 为 26.7%，Gemini-2.0-flash 为 13.3%。
- 📏 **米制感知。** 五个扇区的可走距离、下一步 0.25 m 的碰撞检查和目标距离都来自单目米制深度，Jev 按米而不是按像素推理。
- ⚡ **快。** 单张 H100 上每步 0.76 s，其中 DA3 0.15 s，OWLv2 0.22 s，Jev 0.34 s。

### 🏆 横向对比

EB-Navigation 成功率（%）。DepthJev 的决策模型只读文本；除纯文本 GPT-4o 外，其余基线都能看到图像。

| 智能体 | 决策模型的输入 | 平均 | Base | Common | Complex | Visual | Long |
| --- | --- | :---: | :---: | :---: | :---: | :---: | :---: |
| GPT-4o | 图像 + 文本 | **57.7** | 55.0 | 60.0 | **58.3** | **60.0** | **55.0** |
| Gemini-2.0-flash | 图像 + 文本 | 48.7 | 63.3 | **65.0** | 50.0 | 51.7 | 13.3 |
| **DepthJev（本项目）** | **仅文本事实** | **46.7** | **53.3** | **51.7** | **50.0** | **36.7** | **41.7** |
| Claude-3.5-Sonnet | 图像 + 文本 | 44.7 | **66.7** | 51.7 | 41.7 | 36.7 | 26.7 |
| InternVL2.5-78B | 图像 + 文本 | 30.7 | 36.7 | 38.3 | 33.3 | 21.7 | 23.3 |
| Qwen2-VL-72B | 图像 + 文本 | 21.2 | 26.7 | 30.0 | 28.3 | 16.0 | 5.0 |
| GPT-4o | 仅文本 | 17.4 | 21.7 | 21.7 | 26.7 | 16.7 | 0.0 |

<sub>基线数字取自 EmbodiedBench 论文表 3；加粗为 DepthJev 和每列最好的基线。<a href="https://zjucqr.github.io/DepthJev/">项目主页</a>列出了全部 15 个模型。</sub>

<a id="how-it-works"></a>

## 🏗️ 工作原理

每一步分三个阶段，每个阶段对应 [`depthjev/`](depthjev) 下的一个子包：

1. **👁️ 感知**（[`perception/`](depthjev/perception)）。Depth Anything 3 估计米制深度；OWLv2 定位目标。深度图经反投影、按地面校平后切成五个扇区。
2. **📝 描述**（[`language/`](depthjev/language)）。可走空间、目标距离和动作历史整理成文本事实，距离分为四档：under 0.5 m、0.5 to 1 m、1 to 2 m 和 over 2 m。
3. **🎯 行动**（[`decision/`](depthjev/decision)）。Jev 读取事实，从八个导航动作中选一个，再根据新观测重复。

### 🍝 示例

“*I need a vessel to boil pasta for dinner. Can you navigate to that object and stay close?*” DepthJev 把目标解析为 **Pot**，9 步到达。框是 OWLv2 的检测结果，距离来自 DA3。

<p align="center"><img src="assets/example-pot.jpg" width="100%" alt="DepthJev 9 步到达锅具：第 0、3、6、7、8 步画面，标出检测到的锅和距离"></p>

<details>
<summary><b>第 0 步 Jev 读到的内容</b></summary>

```json
{
  "task": {
    "instruction": "I need a vessel to boil pasta for dinner. Can you navigate to that object and stay close?",
    "target_object": "pot",
    "success_rule": "the episode succeeds as soon as the robot stands within 1 m of the target object",
    "step": 1,
    "steps_left": 20
  },
  "target": {
    "visible": true,
    "sector": "center",
    "distance": "over 2 m"
  },
  "free_distance_ahead_by_sector": {
    "far_left": "1 to 2 m",
    "left": "over 2 m",
    "center": "over 2 m",
    "right": "1 to 2 m",
    "far_right": "under 0.5 m"
  },
  "move_check": {
    "move_ahead": "clear",
    "move_back": "unknown",
    "move_left": "unknown",
    "move_right": "unknown"
  },
  "move_ahead_check_saw_the_floor": false,
  "camera_pitch": "level",
  "recent_actions": []
}
```

**决策：** `move_ahead` · 概率 1.00 · 1,491 个输入 token · 0.37 秒。

</details>

<a id="getting-started"></a>

## 🚀 快速开始

DepthJev 用两个 Python 环境：**服务端**（Python 3.11，一张 GPU）跑模型，**评测端**（Python 3.9，CPU）跑 EmbodiedBench 和 AI2-THOR。所有命令都在仓库根目录执行。

**1. 克隆仓库及锁定版本的依赖**

```bash
git clone --recursive https://github.com/ZJUCQR/DepthJev.git && cd DepthJev
```

EmbodiedBench 和 Depth Anything 3 是 `third_party/` 下的 git 子模块，锁定在复现结果所用的提交上。已经克隆过的仓库执行 `git submodule update --init`。

**2. 服务端环境**

```bash
conda create -y -p envs/depthjev python=3.11 pip
conda activate ./envs/depthjev
pip install -r requirements.txt
hf download depth-anything/DA3METRIC-LARGE --local-dir checkpoints/DA3METRIC-LARGE
hf download google/owlv2-base-patch16-ensemble --local-dir checkpoints/owlv2-base-patch16-ensemble
```

**3. 评测端环境**

```bash
conda create -y -p envs/depthjev-eval python=3.9.21 pip
conda activate ./envs/depthjev-eval
pip install -r requirements.txt
```

两个环境共用同一个 `requirements.txt`，由环境标记按 Python 版本选择各自的依赖。

**4. AI2-THOR 无头渲染**

```bash
sudo apt-get install -y --no-install-recommends xvfb x11-utils libgl1-mesa-dri libgl1-mesa-glx \
    libglu1-mesa libxcursor1 libxrandr2 libxinerama1 libxi6 libxxf86vm1
```

**5. Jev API key**

```bash
cp .env.example .env    # 然后填上 TYPESAFE_API_KEY
```

**6. 运行**

```bash
bash scripts/run.sh                                       # 冒烟测试，base 3 题
bash scripts/run.sh full --sets all --ratio 1             # 全部 300 题，约 2.2 h
bash scripts/run.sh full --sets all --ratio 1 --parallel  # 每个子集一个服务，加 --gpus 0 共用一张卡
```

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `RUN_NAME` | `smoke` | 运行名 |
| `--sets` | `base` | 逗号分隔的子集，或 `all` |
| `--ratio` | `0.05` | EmbodiedBench 的 `down_sample_ratio`，1 表示全部题目 |
| `--gpus` | 可见的 GPU | 服务用的 CUDA 设备 |
| `--parallel` | 关 | 每个子集一个服务 + 一个评测 |

每个请求记录在 `logs/RUN_NAME.jsonl`（同目录下还有服务端和评测端的输出），EmbodiedBench 把各回合结果（含画面）写到 `third_party/EmbodiedBench/running/eb_nav/depthjev_RUN_NAME/`。运行结束时会打印报告；之后可以用 `python -m depthjev.evaluation.report RUN_NAME --ratio R` 从这些文件重新生成。

<details>
<summary><b>服务和评测分两个终端跑</b></summary>

```bash
DEPTHJEV_RUN_NAME=dev bash scripts/server.sh
SERVER_URL=http://127.0.0.1:23333/process bash scripts/eval.sh exp_name=dev eval_sets=[base] down_sample_ratio=0.05
```

服务默认监听 `127.0.0.1`。评测在另一台机器上时，用 `bash scripts/server.sh --host 0.0.0.0` 启动服务，并把 `SERVER_URL` 指向服务所在机器。

</details>

## ⚙️ 配置

仓库没有配置文件。服务端设置都是 `python -m depthjev.server` 的命令行参数（见 `bash scripts/server.sh --help`），每个参数也可以用环境变量设置：`--jev-model` 对应 `DEPTHJEV_JEV_MODEL`，其余依此类推。

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `--da3-dir` | `checkpoints/DA3METRIC-LARGE` | Depth Anything 3 权重 |
| `--owlv2-dir` | `checkpoints/owlv2-base-patch16-ensemble` | OWLv2 权重 |
| `--device` | `cuda` | 两个模型使用的 torch 设备 |
| `--detection-threshold` | `0.1` | OWLv2 分数阈值 |
| `--jev-model` | `jev-latest` | Jev 模型名 |
| `--jev-timeout` | `20` | 每次 Jev 请求的超时秒数，SDK 另外重试两次 |
| `--host`、`--port` | `127.0.0.1`、`23333` | 服务监听地址 |
| `--log-dir`、`--run-name` | `logs`、时间戳 | 请求日志为 `<log-dir>/<run-name>.jsonl` |

脚本还会读取 `DEPTHJEV_SERVER_ENV` 和 `DEPTHJEV_EVAL_ENV` 这两个环境路径（默认 `envs/depthjev` 和 `envs/depthjev-eval`），以及 `DEPTHJEV_PORT`。

<a id="results"></a>

## 📊 实验结果

在一张 **H100** 上评测 EB-Navigation **全部 300 个回合**，命令为 `bash scripts/run.sh full --sets all --ratio 1`。

| 子集 | 成功回合 | 成功率 | 平均步数 / 回合 | 目标类型解析正确 |
| --- | :---: | :---: | :---: | :---: |
| base | 32/60 | 0.533 | 15.2 | 60/60 |
| common_sense | 31/60 | 0.517 | 15.4 | 58/60 |
| complex_instruction | 30/60 | 0.500 | 15.3 | 60/60 |
| visual_appearance | 22/60 | 0.367 | 16.9 | 25/60 |
| long_horizon | 25/60 | 0.417 | 17.3 | 60/60 |
| **全部** | **140/300** | **0.467** | 16.0 | 263/300 |

<details>
<summary><b>⏱️ 服务端耗时</b></summary>

均值、p50 和 p90 对应单路运行；最后一列为三路共用一张 GPU，单位均为秒。

| 阶段 | 均值 | p50 | p90 | 一卡三路均值 |
| --- | :---: | :---: | :---: | :---: |
| DA3 深度 | 0.15 | 0.13 | 0.23 | 0.27 |
| OWLv2 检测 | 0.22 | 0.21 | 0.22 | 0.32 |
| Jev 决策 | 0.34 | 0.27 | 0.51 | 0.38 |
| 目标类型解析，每回合一次 | 0.82 | 0.61 | 1.63 | 1.42 |
| **一步合计** | **0.76** | **0.64** | **1.04** | **1.06** |

包含 AI2-THOR 软件渲染时，单路运行平均每回合约 21 秒。

</details>

<details>
<summary><b>🔍 失败分析：160 个未成功回合</b></summary>

| 失败类型 | 回合数 |
| --- | :---: |
| 目标很少被检测到或目标类型错误 | 51 |
| 左右横移来回震荡 | 40 |
| 被障碍卡住反复撞 | 32 |
| 距离低估或目标误检 | 27 |
| 其他 | 10 |

- **目标检测。** 第一类包含 17 个目标类型解析错误的 `visual_appearance` 回合。开发样本中，为 GarbageCan 添加 "trash can" 和 "bin" 后，成功数从 0/5 提升到 5/5；低分检测（0.1–0.2）仍是常见错误来源。
- **动作约束。** 把约束直接附在动作选项上，比写成通用规则更能避免反复 `look_down`。
- **场景难度。** 同一组 60 个场景和目标中，12 个在五种指令下都成功，22 个都失败；`long_horizon` 还把起始朝向旋转了 180°。

</details>

## 📁 项目结构

```
DepthJev/
├── depthjev/                # 智能体：每个子包对应一步中的一个阶段
│   ├── perception/          # 👁️ 画面变成米制量
│   │   ├── depth.py         #    Depth Anything 3 米制深度
│   │   ├── detection.py     #    OWLv2 开放词表检测
│   │   └── geometry.py      #    反投影、地面估计、各扇区可走距离、前进碰撞、目标距离
│   ├── language/            # 📝 米制量和历史变成 Jev 读的文本
│   │   ├── prompt.py        #    从 EmbodiedBench 的 prompt 里取指令和动作历史
│   │   ├── facts.py         #    距离分档、移动检查、搜索状态、JSON 状态
│   │   ├── actions.py       #    EB-Navigation 的 8 个动作
│   │   └── objects.py       #    125 个 iTHOR 物体类型和检测别名
│   ├── decision/            # 🎯 文本变成动作
│   │   ├── jev.py           #    Jev 客户端和三个问题
│   │   └── policy.py        #    一步：解析 → 深度 → 检测 → 事实 → Jev → 回复
│   ├── server.py            # Flask /process 和 /health，每个请求写一行 JSON
│   └── evaluation/          # 在 Python 3.9 评测环境里运行
│       ├── launch.py        #    启动 EmbodiedBench 并连到服务
│       └── report.py        #    延迟、成功率和逐回合表
├── scripts/
│   ├── run.sh               # 端到端：服务、评测和报告，单路或 --parallel
│   ├── server.sh            # 只起服务
│   └── eval.sh              # 只跑评测
├── third_party/             # git 子模块：EmbodiedBench、Depth-Anything-3
├── assets/                  # README 用图
└── requirements.txt         # 两个环境共用，按 Python 版本选择
```

安装和运行会生成 `envs/`、`checkpoints/` 和 `logs/`，它们都在 git 忽略列表里。

<a id="citation"></a>

## 📝 引用

如果 DepthJev 对你的研究有帮助，请引用：

```bibtex
@misc{depthjev2026,
  title        = {DepthJev: Turning Depth into Text for Embodied Navigation},
  author       = {ZJUCQR},
  year         = {2026},
  howpublished = {\url{https://github.com/ZJUCQR/DepthJev}}
}
```

## 🙏 致谢

- [EmbodiedBench](https://github.com/EmbodiedBench/EmbodiedBench) 提供 EB-Navigation
- [Depth Anything 3](https://github.com/ByteDance-Seed/Depth-Anything-3) 提供米制深度
- [OWLv2](https://huggingface.co/google/owlv2-base-patch16-ensemble) 提供开放词表检测
- [TypeSafe Jev](https://docs.typesafe.ai) 提供决策模型
- [AI2-THOR](https://ai2thor.allenai.org) 提供模拟器和物体类型表

## 📄 许可证

DepthJev 以 [Apache-2.0 许可证](LICENSE) 发布。
