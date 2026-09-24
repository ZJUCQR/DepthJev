<div align="center">
  <h1>DepthJev：将深度感知转化为文本的具身导航</h1>
  <p>
    <img src="https://img.shields.io/badge/python-3.11-blue" alt="Python 3.11">
    <img src="https://img.shields.io/badge/license-Apache--2.0-green" alt="Apache-2.0">
    <img src="https://img.shields.io/badge/EB--Navigation-46.7%25-orange" alt="EB-Navigation 成功率 46.7%">
    <img src="https://img.shields.io/badge/latency-0.76%20s%2Fstep-lightgrey" alt="每步 0.76 s">
  </p>
  <p><a href="README.md">English</a> | <b>简体中文</b></p>
</div>

🧭 **DepthJev** 是 EmbodiedBench EB-Navigation 上的导航智能体。它把原始视觉输入和基于文本的推理连接起来，用 **Depth Anything 3** 把 RGB 帧转成米制深度，用 **OWLv2** 检测目标，再把几何约束翻译成简短的文字事实。**Jev** 读这些事实，给出可靠的导航动作。


## ✨ 亮点

- 📈 **有竞争力的表现。** Jev 从头到尾不看图像，DepthJev 在 EB-Navigation 全部 300 题上的成功率仍有 46.7%。按 EmbodiedBench 论文报告的结果，这高于 Claude-3.5-Sonnet 的 44.7%，比不看图的 GPT-4o 的 17.4% 高 29 个点。
- 📏 **米制感知。** Jev 按米而不是按像素推理距离。五个扇区的可走距离、下一步 0.25 m 的碰撞检查和目标距离，都来自单目米制深度。
- ⚡ **快。** 单张 H100 上每步 0.76 s，其中 DA3 0.15 s，OWLv2 0.22 s，Jev 0.34 s。

## 🏗️ 工作原理

<p align="center">
  <img src="assets/how-it-works.png" width="1100" alt="DepthJev 流程：RGB 观测、任务与历史 → 米制深度与目标检测 → 文本事实 → Jev 导航动作 → 下一次观测">
</p>

1. **感知。** Depth Anything 3 估计米制深度；OWLv2 定位目标物体。
2. **描述。** 将几何信息与动作历史整理成文本事实，描述可走空间、目标距离和移动约束。
3. **行动。** Jev 读取事实，从八个导航动作中选择下一步，并根据新的观测重复这一过程。

## 🚀 快速开始

所有命令都在仓库根目录执行。

**1. 克隆依赖仓库**

```bash
git clone https://github.com/EmbodiedBench/EmbodiedBench.git repos/EmbodiedBench
git clone https://github.com/ByteDance-Seed/Depth-Anything-3.git repos/Depth-Anything-3
```

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
pip install -r requirements-eval.txt
```

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
|---|---|---|
| `RUN_NAME` | `smoke` | 运行名 |
| `--sets` | `base` | 逗号分隔的子集，或 `all` |
| `--ratio` | `0.05` | EmbodiedBench 的 `down_sample_ratio`，1 表示全部题目 |
| `--gpus` | 可见的 GPU | 服务用的 CUDA 设备 |
| `--parallel` | 关 | 每个子集一个服务 + 一个评测 |

<details>
<summary>服务和评测分两个终端跑</summary>

```bash
DEPTHJEV_RUN_NAME=dev bash scripts/server.sh
SERVER_URL=http://127.0.0.1:23333/process bash scripts/eval.sh exp_name=dev eval_sets=[base] down_sample_ratio=0.05
```
</details>

服务默认监听 `127.0.0.1`。评测在另一台机器上运行时，使用 `bash scripts/server.sh --host 0.0.0.0` 启动服务，并将 `SERVER_URL` 设置为服务所在机器的地址。

## ⚙️ 配置

配置位于 [config.json](config.json)。

| 键 | 默认值 |
|---|---|
| `server_env`、`eval_env` | `envs/depthjev`、`envs/depthjev-eval` |
| `da3_dir`、`owlv2_dir` | `checkpoints/...` |
| `jev_model`、`jev_timeout` | `jev-latest`、`20` |
| `port`、`detection_threshold` | `23333`、`0.1` |

## 📊 实验结果

在一张 **H100** 上评测 EB-Navigation **全部 300 个回合**。运行命令：`bash scripts/run.sh full --sets all --ratio 1`。

耗时对应单路运行，端到端耗时包含 AI2-THOR 软件渲染。

<details>
<summary>详细结果：各子集导航表现与各阶段耗时</summary>

**导航表现**

| 子集 | 成功回合 | 成功率 | 平均步数 / 回合 | 目标类型解析正确 |
|---|---:|---:|---:|---:|
| base | 32/60 | 0.533 | 15.2 | 60/60 |
| common_sense | 31/60 | 0.517 | 15.4 | 58/60 |
| complex_instruction | 30/60 | 0.500 | 15.3 | 60/60 |
| visual_appearance | 22/60 | 0.367 | 16.9 | 25/60 |
| long_horizon | 25/60 | 0.417 | 17.3 | 60/60 |
| **全部** | **140/300** | **0.467** | 16.0 | 263/300 |

**服务端耗时**

均值、p50 和 p90 对应单路运行；最后一列对应三个运行共用一张 GPU，单位均为秒。

| 阶段 | 均值 | p50 | p90 | 一卡三路均值 |
|---|---:|---:|---:|---:|
| DA3 深度 | 0.15 | 0.13 | 0.23 | 0.27 |
| OWLv2 检测 | 0.22 | 0.21 | 0.22 | 0.32 |
| Jev 决策 | 0.34 | 0.27 | 0.51 | 0.38 |
| 目标类型解析，每回合一次 | 0.82 | 0.61 | 1.63 | 1.42 |
| **一步合计** | **0.76** | **0.64** | **1.04** | **1.06** |

包含 AI2-THOR 软件渲染时，单路运行平均每回合约 21 秒。

</details>

### 示例与失败分析

<details>
<summary>成功示例：9 步到达目标锅具</summary>

在一个 `common_sense` 任务中，"I need a vessel to boil pasta for dinner" 被解析为 **Pot**。以下为部分步骤：

```text
s0 vis=T center d=2.70 fwd=clear -> move_ahead p=1.00
s4 vis=T center d=1.72 fwd=clear -> move_ahead p=1.00
s5 vis=T left   d=1.47 fwd=clear -> move_ahead p=0.91
s7 vis=T left   d=0.89 fwd=clear -> move_left  p=0.67
s8 vis=T center d=0.84 fwd=clear -> move_ahead p=1.00   (成功)
```

</details>

<details>
<summary>文本事实：Jev 选择动作前读到了什么</summary>

取自 `base` 第 21 题第 0 步的部分字段，目标为 **GarbageCan**：

```json
{
  "task": {"target_object": "garbage can", "step": 1, "steps_left": 20},
  "target": {"visible": true, "sector": "right", "distance": "1 to 2 m"},
  "free_distance_ahead_by_sector": {
    "far_left": "1 to 2 m",
    "left": "1 to 2 m",
    "center": "over 2 m",
    "right": "0.5 to 1 m",
    "far_right": "0.5 to 1 m"
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

**决策：** `move_ahead` · 概率 0.95 · 1,513 个输入 token · 0.22 秒。

</details>

<details>
<summary>失败分析：160 个未成功回合</summary>

| 失败类型 | 回合数 |
|---|---:|
| 目标很少被检测到或目标类型错误 | 51 |
| 左右横移来回震荡 | 40 |
| 被障碍卡住反复撞 | 32 |
| 距离低估或目标误检 | 27 |
| 其他 | 10 |

- **目标检测。** 第一类包含 17 个目标类型解析错误的 `visual_appearance` 回合。开发样本中，为 GarbageCan 添加 "trash can" 和 "bin" 后，成功数从 0/5 提升到 5/5；低分检测（0.1–0.2）仍是常见错误来源。
- **动作约束。** 将约束直接附在动作选项上，比写成通用规则更能避免反复执行 `look_down`。
- **场景难度。** 同一组 60 个场景和目标中，12 个在五种指令下都成功，22 个都失败；`long_horizon` 还将起始朝向旋转了 180°。

</details>

## 📁 项目结构

```
depthjev/
├── server.py         # Flask /process + /health，每个请求写一行 JSONL
├── policy.py         # 一步：解析 → 深度 → 检测 → 事实 → Jev → EmbodiedBench JSON
├── prompt_parse.py   # 从 EmbodiedBench 的 prompt 里取指令和动作历史
├── depth.py          # DA3METRIC-LARGE → 米制深度
├── detect.py         # OWLv2 目标检测
├── geometry.py       # 反投影、地面估计、扇区距离、前进碰撞
├── facts.py          # Jev 读的状态、移动检查、搜索状态
├── jev_client.py     # 三个 Jev Choice、规则、iTHOR 类型表、检测别名
├── actions.py        # EB-Navigation 的 8 个动作
├── config.py         # config.json → shell 变量
├── eb_launch.py      # 在评测环境里启动 EmbodiedBench
└── report.py         # 延迟、成功率和逐回合表
scripts/
├── run.sh            # 端到端评测，单路或 --parallel
├── server.sh         # 只起服务
└── eval.sh           # 只跑评测
```

## 🙏 致谢

- [EmbodiedBench](https://github.com/EmbodiedBench/EmbodiedBench) 提供 EB-Navigation
- [Depth Anything 3](https://github.com/ByteDance-Seed/Depth-Anything-3) 提供米制深度
- [OWLv2](https://huggingface.co/google/owlv2-base-patch16-ensemble) 提供开放词表检测
- [TypeSafe Jev](https://docs.typesafe.ai) 提供决策模型
- [AI2-THOR](https://ai2thor.allenai.org) 提供模拟器和物体类型表
