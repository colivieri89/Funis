"""Launcher used by the packaged application and by `python run_funis.py`."""
import multiprocessing
import sys

from funis.ui.app import main

if __name__ == "__main__":
    multiprocessing.freeze_support()
    sys.exit(main())
