#!/usr/bin/env python3
"""P11：跑 R1（Scope → retrieve → generate）。"""
from __future__ import annotations

import runpy
import sys
from pathlib import Path

here = Path(__file__).resolve().parent
sys.argv = [str(here / "09_run_eval.py"), "--config", "R1", *sys.argv[1:]]
runpy.run_path(str(here / "09_run_eval.py"), run_name="__main__")
