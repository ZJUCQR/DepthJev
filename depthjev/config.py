"""Print config.json settings as shell code for the launch scripts.

Key k becomes the exported variable DEPTHJEV_<K>; a variable already set in the environment keeps its value. Path settings, the keys ending in _env, _dir or _file, are made absolute: ~ expands to the home directory and relative paths are taken from the repository root. Uses only the standard library and works in both Python environments.
"""

from __future__ import annotations

import json
import shlex
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CONFIG = REPO / "config.json"
PATH_SUFFIXES = ("_env", "_dir", "_file")


def shell_lines(settings: dict) -> list[str]:
    lines = []
    for key, value in settings.items():
        if key.endswith(PATH_SUFFIXES):
            value = REPO / Path(value).expanduser()
        name = f"DEPTHJEV_{key.upper()}"
        lines.append(f"{name}=${{{name}:-{shlex.quote(str(value))}}}; export {name}")
    return lines


def main():
    with open(CONFIG, encoding="utf-8") as f:
        settings = json.load(f)
    print("\n".join(shell_lines(settings)))


if __name__ == "__main__":
    main()
