<div align="center">

<img src="assets/logo.svg" width="88" alt="GeoLingo logo">

<h1>GeoLingo</h1>

<h3>将几何翻译为语言的具身导航</h3>

<p>
  <a href="https://github.com/ZJUCQR/GeoLingo/actions/workflows/lint.yml"><img src="https://github.com/ZJUCQR/GeoLingo/actions/workflows/lint.yml/badge.svg" alt="lint"></a>
  <img src="https://img.shields.io/badge/python-3.11-3776AB?logo=python&logoColor=white" alt="Python 3.11">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-green" alt="Apache-2.0"></a>
  <img src="https://img.shields.io/badge/EB--Navigation-46.7%25-orange" alt="EB-Navigation 成功率 46.7%">
  <img src="https://img.shields.io/badge/latency-0.76%20s%2Fstep-blueviolet" alt="每步 0.76 s">
</p>

<p>
  <a href="https://zjucqr.github.io/GeoLingo/"><b>项目主页</b></a> ·
  <a href="#how-it-works">工作原理</a> ·
  <a href="#getting-started">快速开始</a> ·
  <a href="#results">实验结果</a> ·
  <a href="#citation">引用</a>
</p>

<p><a href="README.md">English</a> | <b>简体中文</b></p>

</div>

<p align="center">
  <img src="assets/teaser.gif" width="100%" alt="GeoLingo 在一个 EB-Navigation 回合上的记录：带检测框的相机画面、按五个扇区扫过的 Depth Anything 3 米制深度，以及每一步 Jev 读到的文本事实">
</p>

**GeoLingo** 是 [EmbodiedBench](https://github.com/EmbodiedBench/EmbodiedBench) EB-Navigation 上的导航智能体。它用 **Depth Anything 3** 把每帧 RGB 转成米制深度，用 **OWLv2** 检测目标，再把几何信息写成简短的文字事实。**Jev** 决策模型只读这些事实、从不看图像，据此选出下一个动作。

## ✨ 亮点

- 📈 **不看图也能打。** EB-Navigation 全部 300 题成功率 46.7%，决策模型全程不看图像。
- 🧭 **长程任务稳得住。** `long_horizon` 子集成功率 41.7%，这个子集的起始朝向转了 180°，目标通常在机器人身后。
- 📏 **米制感知。** 五个扇区的可走距离、下一步 0.25 m 的碰撞检查和目标距离都来自单目米制深度，Jev 按米而不是按像素推理。
- ⚡ **快。** 单张 H100 上每步 0.76 s，其中 DA3 0.15 s，OWLv2 0.22 s，Jev 0.34 s。

<a id="how-it-works"></a>

## 🏗️ 工作原理

<p align="center">
  <img src="assets/how-it-works.png" width="100%" alt="GeoLingo 流程：RGB 观测、任务与历史 → 米制深度与目标检测 → 文本事实 → Jev 导航动作 → 下一次观测">
</p>

每一步分三个阶段，每个阶段对应 [`geolingo/`](geolingo) 下的一个子包：

1. **👁️ 感知**（[`perception/`](geolingo/perception)）。Depth Anything 3 估计米制深度，OWLv2 定位目标。深度图经反投影、按地面校平后切成五个扇区。
2. **📝 描述**（[`language/`](geolingo/language)）。可走空间、目标距离和动作历史整理成文本事实，距离分为四档：under 0.5 m、0.5 to 1 m、1 to 2 m 和 over 2 m。
3. **🎯 行动**（[`decision/`](geolingo/decision)）。Jev 读取事实，从八个导航动作中选一个，再根据新观测重复。

### 🍝 示例

“*I need a vessel to boil pasta for dinner. Can you navigate to that object and stay close?*” GeoLingo 把目标解析为 **Pot**，9 步到达。框是 OWLv2 的检测结果，距离来自 DA3。

<p align="center"><img src="assets/example-pot.jpg" width="100%" alt="GeoLingo 9 步到达锅具：第 0、3、6、7、8 步画面，标出检测到的锅和距离"></p>

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

GeoLingo 用两个 Python 环境：**服务端**（Python 3.11，一张 GPU）跑模型，**评测端**（Python 3.9，CPU）跑 EmbodiedBench 和 AI2-THOR。所有命令都在仓库根目录执行。

**1. 克隆仓库**

```bash
git clone https://github.com/ZJUCQR/GeoLingo.git && cd GeoLingo
```

**2. 服务端环境**

```bash
conda create -y -p envs/geolingo python=3.11 pip
conda activate ./envs/geolingo
pip install -r requirements.txt
hf download depth-anything/DA3METRIC-LARGE --local-dir checkpoints/DA3METRIC-LARGE
hf download google/owlv2-base-patch16-ensemble --local-dir checkpoints/owlv2-base-patch16-ensemble
```

**3. 评测端环境**

```bash
conda create -y -p envs/geolingo-eval python=3.9.21 pip
conda activate ./envs/geolingo-eval
pip install -r requirements.txt
pip install --no-deps -e /path/to/EmbodiedBench
```

两个环境共用同一个 `requirements.txt`，由环境标记按 Python 版本选择各自的依赖。EB-Navigation 由 [EmbodiedBench](https://github.com/EmbodiedBench/EmbodiedBench) 提供，细节见它的仓库。脚本通过这次安装找到你克隆的 EmbodiedBench，也可以用 `EMBODIEDBENCH_DIR` 指定。

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

每个请求记录在 `logs/RUN_NAME.jsonl`（同目录下还有服务端和评测端的输出），EmbodiedBench 把各回合结果（含画面）写到 EmbodiedBench 目录下的 `running/eb_nav/geolingo_RUN_NAME/`。运行结束时会打印报告，之后可以用 `python -m geolingo.evaluation.report RUN_NAME --ratio R` 从这些文件重新生成。

## ⚙️ 配置

仓库没有配置文件。服务端设置都是 `python -m geolingo.server` 的命令行参数（见 `bash scripts/server.sh --help`），每个参数也可以用环境变量设置：`--jev-model` 对应 `GEOLINGO_JEV_MODEL`，其余依此类推。

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

脚本还会读取 `GEOLINGO_SERVER_ENV` 和 `GEOLINGO_EVAL_ENV` 这两个环境路径（默认 `envs/geolingo` 和 `envs/geolingo-eval`），以及 `GEOLINGO_PORT` 和 `EMBODIEDBENCH_DIR`。

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

## 📁 项目结构

```
GeoLingo/
├── geolingo/                # 智能体：每个子包对应一步中的一个阶段
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
├── assets/                  # README 用图
└── requirements.txt         # 两个环境共用，按 Python 版本选择
```

<a id="citation"></a>

## 📝 引用

如果 GeoLingo 对你的研究有帮助，请引用：

```bibtex
@misc{geolingo2026,
  title        = {GeoLingo: Translating Geometry into Language for Embodied Navigation},
  author       = {ZJUCQR},
  year         = {2026},
  howpublished = {\url{https://github.com/ZJUCQR/GeoLingo}}
}
```

## 🙏 致谢

- [EmbodiedBench](https://github.com/EmbodiedBench/EmbodiedBench) 提供 EB-Navigation
- [Depth Anything 3](https://github.com/ByteDance-Seed/Depth-Anything-3) 提供米制深度
- [OWLv2](https://huggingface.co/google/owlv2-base-patch16-ensemble) 提供开放词表检测
- [TypeSafe Jev](https://docs.typesafe.ai) 提供决策模型
- [AI2-THOR](https://ai2thor.allenai.org) 提供模拟器和物体类型表

## 📄 许可证

GeoLingo 以 [Apache-2.0 许可证](LICENSE) 发布。
