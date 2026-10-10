"""EB-Navigation runs and reports. Runs in the Python 3.9 evaluation environment: no imports from the rest of the package."""

import importlib.metadata
import json
import os
from pathlib import Path
from urllib.parse import unquote, urlparse


def embodiedbench_root():
    """The EmbodiedBench checkout: $EMBODIEDBENCH_DIR, else the folder `pip install -e` installed into this environment."""
    if os.environ.get("EMBODIEDBENCH_DIR"):
        return Path(os.environ["EMBODIEDBENCH_DIR"]).expanduser().resolve()
    try:
        record = importlib.metadata.distribution("embodiedbench").read_text("direct_url.json") or "{}"
    except importlib.metadata.PackageNotFoundError:
        record = "{}"
    url = json.loads(record).get("url", "")
    if not url.startswith("file://"):
        raise SystemExit("EmbodiedBench not found: pip install -e it into this environment or set EMBODIEDBENCH_DIR")
    return Path(unquote(urlparse(url).path))
