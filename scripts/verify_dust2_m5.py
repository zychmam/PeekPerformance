"""Compatibility command for the shared real-map verification harness."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.verify_profile_m5 import main

if __name__ == "__main__":
    main("de_dust2")
