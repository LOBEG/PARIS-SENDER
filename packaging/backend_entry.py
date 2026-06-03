"""Frozen entrypoint for the PyInstaller backend bundle.

Kept as a thin wrapper around :func:`backend.server.main` so PyInstaller has a
single, import-light script to analyze. All server logic lives in
``backend/server.py``.
"""

from __future__ import annotations

import multiprocessing

from backend.server import main

if __name__ == "__main__":
    # Required so frozen executables do not re-spawn the app when libraries use
    # multiprocessing internally.
    multiprocessing.freeze_support()
    main()
