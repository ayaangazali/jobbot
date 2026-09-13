#!/usr/bin/env python3
"""Start jobbot dashboard server on port 8765."""

import sys
from pathlib import Path

# Ensure jobbot package is importable
sys.path.insert(0, str(Path(__file__).parent))

from jobbot.dashboard import serve

if __name__ == "__main__":
    serve(
        data_dir="data",
        profile="config/profile.yaml",
        port=8765,
        open_browser=False,
        host="127.0.0.1",
        tailscale=False,
    )
