#!/usr/bin/env python3
"""One-click launcher for the Nayro Studio web interface.

Double-click ``start.bat`` (Windows) or ``start.sh`` (macOS/Linux), or run::

    python run.py
"""

from nayro_studio.web import main

if __name__ == "__main__":
    raise SystemExit(main())
