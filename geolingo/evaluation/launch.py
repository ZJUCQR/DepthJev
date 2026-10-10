"""Run EmbodiedBench EB-Navigation against the GeoLingo server without changing the EmbodiedBench repo.

It sets server_url (read by embodiedbench/planner/custom_model.py at import time), switches AI2-THOR to the Linux64 build when asked (EBNavEnv hard-codes CloudRendering, which needs a Vulkan driver; replacing the class in ai2thor.platform before EmbodiedBench imports it is enough), and runs embodiedbench.main the way python -m would, passing the remaining arguments through as hydra overrides. scripts/eval.sh is the normal entry point. It runs in the evaluation environment (Python 3.9), so this module must stay 3.9-compatible and must not import anything outside geolingo.evaluation. By hand, from the repo root:

    python -m geolingo.evaluation.launch --server-url http://HOST:23333/process --platform Linux64 env=eb-nav model_name=geolingo model_type=custom exp_name=smoke eval_sets=[base] down_sample_ratio=0.05
"""

import argparse
import importlib.util
import os
import sys
import types

from geolingo.evaluation import embodiedbench_root


def stub_lmdeploy():
    """Stand in for lmdeploy, which planner/remote_model.py imports at module level (via nav_planner.py).

    lmdeploy is a multi-GB local-inference stack that model_type=custom never calls, so an empty module
    with the three names EmbodiedBench imports is enough; using any of them raises.
    """
    if importlib.util.find_spec("lmdeploy") is not None:
        return

    def unavailable(*args, **kwargs):
        raise RuntimeError("lmdeploy is not installed; GeoLingo runs EmbodiedBench with model_type=custom")

    module = types.ModuleType("lmdeploy")
    module.pipeline = module.GenerationConfig = module.PytorchEngineConfig = unavailable
    sys.modules["lmdeploy"] = module


def main():
    parser = argparse.ArgumentParser(
        prog="python -m geolingo.evaluation.launch",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--server-url",
        default=os.environ.get("server_url"),
        help="GeoLingo endpoint, e.g. http://127.0.0.1:23333/process",
    )
    parser.add_argument(
        "--platform",
        choices=["CloudRendering", "Linux64"],
        default="Linux64",
    )
    args, hydra_overrides = parser.parse_known_args()
    if not args.server_url:
        parser.error("--server-url (or env server_url) is required")
    os.environ["server_url"] = args.server_url

    import ai2thor.platform as thor_platform

    if args.platform == "Linux64":
        thor_platform.CloudRendering = thor_platform.Linux64  # EBNavEnv: from ai2thor.platform import CloudRendering
        if not os.environ.get("DISPLAY"):
            parser.error("--platform Linux64 needs DISPLAY (start Xvfb first, see scripts/eval.sh)")

    stub_lmdeploy()
    eb_root = embodiedbench_root()
    os.chdir(eb_root)  # embodiedbench.main opens embodiedbench/configs/<env>.yaml relative to the cwd
    sys.path.insert(0, str(eb_root))
    sys.argv = [sys.argv[0]] + hydra_overrides
    # hydra resolves @hydra.main(config_path="./configs") relative to the *__main__* module's file, so
    # embodiedbench.main must run exactly as `python -m embodiedbench.main` does (importing it and
    # calling main() makes hydra look for a package "embodiedbench...configs" and fail).
    import runpy

    runpy.run_module("embodiedbench.main", run_name="__main__", alter_sys=True)


if __name__ == "__main__":
    main()
