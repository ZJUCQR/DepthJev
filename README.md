<div align="center">

<h1>🧭 DepthJev</h1>

<h3>Turning Depth into Text for Embodied Navigation</h3>

<p>
  <a href="https://zjucqr.github.io/DepthJev/"><img src="https://img.shields.io/badge/project-page-0ea5e9?logo=githubpages&logoColor=white" alt="Project page"></a>
  <a href="https://github.com/ZJUCQR/DepthJev/actions/workflows/lint.yml"><img src="https://github.com/ZJUCQR/DepthJev/actions/workflows/lint.yml/badge.svg" alt="lint"></a>
  <img src="https://img.shields.io/badge/python-3.11-3776AB?logo=python&logoColor=white" alt="Python 3.11">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-green" alt="Apache-2.0"></a>
  <img src="https://img.shields.io/badge/EB--Navigation-46.7%25-orange" alt="EB-Navigation success 46.7%">
  <img src="https://img.shields.io/badge/latency-0.76%20s%2Fstep-blueviolet" alt="0.76 s per step">
</p>

<p>
  <a href="https://zjucqr.github.io/DepthJev/"><b>Project page</b></a> ·
  <a href="#how-it-works">How it works</a> ·
  <a href="#getting-started">Getting started</a> ·
  <a href="#results">Results</a> ·
  <a href="#citation">Citation</a>
</p>

<p><b>English</b> | <a href="README_zh.md">简体中文</a></p>

</div>

<p align="center">
  <img src="assets/teaser.gif" width="100%" alt="DepthJev on a recorded EB-Navigation episode: the camera frame with the detected pot, Depth Anything 3 metric depth sweeping across it in five sectors, and the text facts Jev reads at each step">
</p>

**DepthJev** is a navigation agent for [EmbodiedBench](https://github.com/EmbodiedBench/EmbodiedBench) EB-Navigation. It converts each RGB frame into metric depth with **Depth Anything 3**, detects the target with **OWLv2**, and turns the geometry into short text facts. The **Jev** decision model reads only these facts, never the image, and picks the next action.

## ✨ Highlights

- 📈 **Strong without pixels.** 46.7% success on all 300 EB-Navigation episodes, above Claude-3.5-Sonnet (44.7%) and 29.3 points above text-only GPT-4o (17.4%) as reported by EmbodiedBench.
- 🧭 **Holds up on long horizons.** 41.7% on `long_horizon`, second only to GPT-4o (55.0%); Claude-3.5-Sonnet reaches 26.7% and Gemini-2.0-flash 13.3%.
- 📏 **Metric grounding.** Free space in five sectors, a collision check for the next 0.25 m step and the target distance all come from monocular metric depth, so Jev reasons in metres, not pixels.
- ⚡ **Fast.** 0.76 s per step on one H100: DA3 0.15 s, OWLv2 0.22 s, Jev 0.34 s.

### 🏆 Where it stands

Success rate (%) on EB-Navigation. DepthJev's decision model reads only text; every baseline except text-only GPT-4o also sees the image.

| Agent | Decision model reads | Avg | Base | Common | Complex | Visual | Long |
| --- | --- | :---: | :---: | :---: | :---: | :---: | :---: |
| GPT-4o | image + text | **57.7** | 55.0 | 60.0 | **58.3** | **60.0** | **55.0** |
| Gemini-2.0-flash | image + text | 48.7 | 63.3 | **65.0** | 50.0 | 51.7 | 13.3 |
| **DepthJev (ours)** | **text facts only** | **46.7** | **53.3** | **51.7** | **50.0** | **36.7** | **41.7** |
| Claude-3.5-Sonnet | image + text | 44.7 | **66.7** | 51.7 | 41.7 | 36.7 | 26.7 |
| InternVL2.5-78B | image + text | 30.7 | 36.7 | 38.3 | 33.3 | 21.7 | 23.3 |
| Qwen2-VL-72B | image + text | 21.2 | 26.7 | 30.0 | 28.3 | 16.0 | 5.0 |
| GPT-4o | text only | 17.4 | 21.7 | 21.7 | 26.7 | 16.7 | 0.0 |

<sub>Baselines are from Table 3 of the EmbodiedBench paper; bold marks DepthJev and the best baseline per column. The <a href="https://zjucqr.github.io/DepthJev/">project page</a> compares all 15 models.</sub>

<a id="how-it-works"></a>

## 🏗️ How it works

<p align="center">
  <img src="assets/how-it-works.png" width="100%" alt="DepthJev pipeline: RGB observation, task and history → metric depth and target detection → text facts → Jev navigation action → next observation">
</p>

Each step runs through three stages, and each stage is one sub-package of [`depthjev/`](depthjev):

1. **👁️ Perceive** ([`perception/`](depthjev/perception)). Depth Anything 3 estimates metric depth; OWLv2 finds the target. The depth map is back-projected, levelled against the floor and cut into five sectors.
2. **📝 Describe** ([`language/`](depthjev/language)). Free space, target distance and the action history become text facts in four distance bins: under 0.5 m, 0.5 to 1 m, 1 to 2 m and over 2 m.
3. **🎯 Act** ([`decision/`](depthjev/decision)). Jev reads the facts and selects one of eight navigation actions, and the loop repeats with the next observation.

### 🍝 Example

“*I need a vessel to boil pasta for dinner. Can you navigate to that object and stay close?*” DepthJev resolves the target to **Pot** and reaches it in 9 steps. Boxes are OWLv2 detections, distances come from DA3.

<p align="center"><img src="assets/example-pot.jpg" width="100%" alt="DepthJev reaching a pot in 9 steps: frames of steps 0, 3, 6, 7 and 8 with the detected pot and its distance"></p>

<details>
<summary><b>What Jev reads at step 0</b></summary>

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

**Decision:** `move_ahead` · probability 1.00 · 1,491 input tokens · 0.37 s.

</details>

<a id="getting-started"></a>

## 🚀 Getting started

DepthJev runs in two Python environments: the **server** (Python 3.11, one GPU) runs the models, and the **evaluator** (Python 3.9, CPU) runs EmbodiedBench and AI2-THOR. All commands run from the repository root.

**1. Clone with the pinned dependencies**

```bash
git clone --recursive https://github.com/ZJUCQR/DepthJev.git && cd DepthJev
```

EmbodiedBench and Depth Anything 3 are git submodules in `third_party/`, pinned to the commits behind the results. In an existing clone, run `git submodule update --init`.

**2. Server environment**

```bash
conda create -y -p envs/depthjev python=3.11 pip
conda activate ./envs/depthjev
pip install -r requirements.txt
hf download depth-anything/DA3METRIC-LARGE --local-dir checkpoints/DA3METRIC-LARGE
hf download google/owlv2-base-patch16-ensemble --local-dir checkpoints/owlv2-base-patch16-ensemble
```

**3. Evaluation environment**

```bash
conda create -y -p envs/depthjev-eval python=3.9.21 pip
conda activate ./envs/depthjev-eval
pip install -r requirements.txt
```

The same `requirements.txt` serves both environments: environment markers select the packages by Python version.

**4. Headless rendering for AI2-THOR**

```bash
sudo apt-get install -y --no-install-recommends xvfb x11-utils libgl1-mesa-dri libgl1-mesa-glx \
    libglu1-mesa libxcursor1 libxrandr2 libxinerama1 libxi6 libxxf86vm1
```

**5. Jev API key**

```bash
cp .env.example .env    # then fill in TYPESAFE_API_KEY
```

**6. Run**

```bash
bash scripts/run.sh                                       # smoke test, 3 base episodes
bash scripts/run.sh full --sets all --ratio 1             # all 300 episodes, about 2.2 h
bash scripts/run.sh full --sets all --ratio 1 --parallel  # one server per subset, add --gpus 0 to share one card
```

| Option | Default | Description |
| --- | --- | --- |
| `RUN_NAME` | `smoke` | name of the run |
| `--sets` | `base` | comma-separated subsets, or `all` |
| `--ratio` | `0.05` | EmbodiedBench `down_sample_ratio`, 1 runs every task |
| `--gpus` | visible GPUs | CUDA devices for the servers |
| `--parallel` | off | one server + evaluator per subset |

Each request is logged to `logs/RUN_NAME.jsonl`, next to the server and evaluator output, and EmbodiedBench writes the episodes, frames included, to `third_party/EmbodiedBench/running/eb_nav/depthjev_RUN_NAME/`. The run prints its report at the end; `python -m depthjev.evaluation.report RUN_NAME --ratio R` prints it again from these files.

<details>
<summary><b>Server and evaluator in separate terminals</b></summary>

```bash
DEPTHJEV_RUN_NAME=dev bash scripts/server.sh
SERVER_URL=http://127.0.0.1:23333/process bash scripts/eval.sh exp_name=dev eval_sets=[base] down_sample_ratio=0.05
```

The server listens on `127.0.0.1` by default. For an evaluator on another machine, start it with `bash scripts/server.sh --host 0.0.0.0` and point `SERVER_URL` at the server.

</details>

## ⚙️ Configuration

There is no configuration file. Server settings are flags of `python -m depthjev.server` (`bash scripts/server.sh --help`), and each flag can also be set as an environment variable: `--jev-model` as `DEPTHJEV_JEV_MODEL`, and so on.

| Flag | Default | Description |
| --- | --- | --- |
| `--da3-dir` | `checkpoints/DA3METRIC-LARGE` | Depth Anything 3 checkpoint |
| `--owlv2-dir` | `checkpoints/owlv2-base-patch16-ensemble` | OWLv2 checkpoint |
| `--device` | `cuda` | torch device for both models |
| `--detection-threshold` | `0.1` | OWLv2 score threshold |
| `--jev-model` | `jev-latest` | Jev model name |
| `--jev-timeout` | `20` | seconds per Jev request; the SDK retries twice on top |
| `--host`, `--port` | `127.0.0.1`, `23333` | address the server listens on |
| `--log-dir`, `--run-name` | `logs`, a timestamp | the request log is `<log-dir>/<run-name>.jsonl` |

The scripts also read `DEPTHJEV_SERVER_ENV` and `DEPTHJEV_EVAL_ENV`, the two environments (default `envs/depthjev` and `envs/depthjev-eval`), and `DEPTHJEV_PORT`.

<a id="results"></a>

## 📊 Results

All **300 EB-Navigation episodes** on one **H100**, run with `bash scripts/run.sh full --sets all --ratio 1`.

| Subset | Successes | Success rate | Steps / episode | Target type correct |
| --- | :---: | :---: | :---: | :---: |
| base | 32/60 | 0.533 | 15.2 | 60/60 |
| common_sense | 31/60 | 0.517 | 15.4 | 58/60 |
| complex_instruction | 30/60 | 0.500 | 15.3 | 60/60 |
| visual_appearance | 22/60 | 0.367 | 16.9 | 25/60 |
| long_horizon | 25/60 | 0.417 | 17.3 | 60/60 |
| **All** | **140/300** | **0.467** | 16.0 | 263/300 |

<details>
<summary><b>⏱️ Server latency</b></summary>

Mean, p50 and p90 are for one run; the last column shows three runs sharing one GPU. All values are in seconds.

| Stage | Mean | p50 | p90 | Mean, 3 runs/GPU |
| --- | :---: | :---: | :---: | :---: |
| DA3 depth | 0.15 | 0.13 | 0.23 | 0.27 |
| OWLv2 detection | 0.22 | 0.21 | 0.22 | 0.32 |
| Jev decision | 0.34 | 0.27 | 0.51 | 0.38 |
| Target resolution, once per episode | 0.82 | 0.61 | 1.63 | 1.42 |
| **Whole step** | **0.76** | **0.64** | **1.04** | **1.06** |

With AI2-THOR software rendering, a single run averages about 21 s per episode.

</details>

<details>
<summary><b>🔍 Failure analysis: 160 unsuccessful episodes</b></summary>

| Pattern | Episodes |
| --- | :---: |
| Target rarely detected or incorrectly identified | 51 |
| Sidestepping left and right without progress | 40 |
| Stuck against obstacles | 32 |
| Distance underestimated or false target detection | 27 |
| Other | 10 |

- **Detection.** The first group includes 17 `visual_appearance` episodes with an incorrect target type. Adding "trash can" and "bin" improved GarbageCan success from 0/5 to 5/5 on a development sample; low-score detections (0.1–0.2) remain a common source of errors.
- **Action constraints.** Attaching constraints directly to action options prevented repeated `look_down` actions more effectively than a general rule.
- **Scene difficulty.** Across the same 60 scenes and targets, 12 succeeded under all five instruction variants and 22 failed under all five. `long_horizon` also changes the starting orientation by 180°.

</details>

## 📁 Project structure

```
DepthJev/
├── depthjev/                # the agent: one sub-package per stage of a step
│   ├── perception/          # 👁️ the frame becomes metres
│   │   ├── depth.py         #    Depth Anything 3 metric depth
│   │   ├── detection.py     #    OWLv2 open-vocabulary detection
│   │   └── geometry.py      #    back-projection, floor, free space per sector, step collision, target range
│   ├── language/            # 📝 metres and history become the text Jev reads
│   │   ├── prompt.py        #    instruction and action history from the EmbodiedBench prompt
│   │   ├── facts.py         #    distance bins, move checks, search status, the JSON state
│   │   ├── actions.py       #    the eight EB-Navigation actions
│   │   └── objects.py       #    the 125 iTHOR object types and detector aliases
│   ├── decision/            # 🎯 the text becomes an action
│   │   ├── jev.py           #    Jev client and its three questions
│   │   └── policy.py        #    one step: parse → depth → detect → facts → Jev → reply
│   ├── server.py            # Flask /process and /health, one JSON line per request
│   └── evaluation/          # runs in the Python 3.9 evaluation environment
│       ├── launch.py        #    starts EmbodiedBench against the server
│       └── report.py        #    latency, success and per-episode tables
├── scripts/
│   ├── run.sh               # end to end: server, evaluator and report, single or --parallel
│   ├── server.sh            # server only
│   └── eval.sh              # evaluator only
├── third_party/             # git submodules: EmbodiedBench, Depth-Anything-3
├── assets/                  # README figures
└── requirements.txt         # both environments, selected by Python version
```

Setup and runs add `envs/`, `checkpoints/` and `logs/`, which git ignores.

<a id="citation"></a>

## 📝 Citation

If DepthJev helps your research, please cite it:

```bibtex
@misc{depthjev2026,
  title        = {DepthJev: Turning Depth into Text for Embodied Navigation},
  author       = {ZJUCQR},
  year         = {2026},
  howpublished = {\url{https://github.com/ZJUCQR/DepthJev}}
}
```

## 🙏 Acknowledgements

- [EmbodiedBench](https://github.com/EmbodiedBench/EmbodiedBench) for EB-Navigation
- [Depth Anything 3](https://github.com/ByteDance-Seed/Depth-Anything-3) for metric depth
- [OWLv2](https://huggingface.co/google/owlv2-base-patch16-ensemble) for open-vocabulary detection
- [TypeSafe Jev](https://docs.typesafe.ai) for the decision model
- [AI2-THOR](https://ai2thor.allenai.org) for the simulator and its object types

## 📄 License

DepthJev is released under the [Apache-2.0 License](LICENSE).
