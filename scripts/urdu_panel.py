"""Resolve Scripts entry point.

The installer copies this file into DaVinci Resolve's Utility scripts folder.
Resolve runs it with its bundled Python; we add the plugin package to sys.path
(via the URDU_SUBTITLES_HOME env var written by the installer) and launch the
panel.
"""

import os
import sys

_home = os.environ.get("URDU_SUBTITLES_HOME")
if _home and _home not in sys.path:
    sys.path.insert(0, _home)

try:
    from urdu_subtitles.resolve.panel import main
except ImportError as exc:
    print("[UrduSubtitles] Could not import the plugin package.")
    print("Set URDU_SUBTITLES_HOME to the folder containing 'urdu_subtitles/'.")
    print(f"Details: {exc}")
else:
    main()
