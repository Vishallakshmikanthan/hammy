#!/usr/bin/env python3
"""
HAMMY — World Worker Launcher Script (`scripts/run_world_worker.py`).
"""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from services.world_worker.worker import main

if __name__ == "__main__":
    main()

