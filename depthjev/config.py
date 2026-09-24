"""Print the [tool.depthjev] settings of pyproject.toml as shell code, for eval "$(python3 -m depthjev.config)" run from the repo root.

Key k becomes the exported variable DEPTHJEV_<K>; a variable already set in the environment keeps its value. Path settings, the keys ending in _env, _dir or _file, are made absolute: ~ expands to the home directory and relative paths are taken from the repository root. Works with Python 3.11+ (tomllib) and with older Python 3 interpreters that have tomli or pip, which vendors tomli.
"""

from __future__ import annotations

import shlex
from pathlib import Path

try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        from pip._vendor import tomli as tomllib

REPO = Path(__file__).resolve().parents[1]
PYPROJECT = REPO / "pyproject.toml"
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
    with open(PYPROJECT, "rb") as f:
        settings = tomllib.load(f)["tool"]["depthjev"]
    print("\n".join(shell_lines(settings)))


if __name__ == "__main__":
    main()
