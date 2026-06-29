#!/usr/bin/env python3
"""Quick entry point: python run.py <command> [args]"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
from src.cli import main
main()
