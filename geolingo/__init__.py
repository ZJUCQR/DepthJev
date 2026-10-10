"""GeoLingo: an EB-Navigation agent that turns metric depth and detections into text facts for the Jev decision model.

One step runs through three layers, each a sub-package that only imports the layers above it in this list:

    perception/   Perceive: the frame becomes metric depth, a target box and free-space measurements
    language/     Describe: measurements and the action history become the text state Jev reads
    decision/     Act: Jev picks one of the eight actions; policy.py runs the whole step

server.py serves the agent to EmbodiedBench over HTTP. evaluation/ runs the benchmark and reports the results
from the separate Python 3.9 evaluation environment.
"""

__version__ = "0.1.0"
