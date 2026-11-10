"""Screenshots of the main window for the README.

Writes docs/screenshots/*.png: the window drawn offscreen at twice the pixel
density, reduced to 256 colours. Run from the repository root with the
environment of the program:

    .venv/bin/python packaging/make_screenshots.py

The settings of the installed program are not read or written. The images in
the repository were made on macOS; on another system the fonts differ.
"""
import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_SCALE_FACTOR", "2")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "screenshots")
sys.path.insert(0, ROOT)

import matplotlib  # noqa: E402

matplotlib.use("QtAgg")
from PIL import Image  # noqa: E402
from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from funis import __app_name__  # noqa: E402
from funis.examples import EXAMPLES  # noqa: E402
from funis.ui import theme  # noqa: E402
from funis.ui.main_window import MainWindow  # noqa: E402

TABS = {"views": 1, "contact": 3, "spatial": 4}
SHOTS = [  # file name, example, tab of the results
    ("spatial_view", "Supported: Figs. 12 and 13, circular benchmark with contact", "spatial"),
    ("contact", "Supported: Figs. 12 and 13, circular benchmark with contact", "contact"),
    ("form_finding", "Form-finding: Figs. 5 and 11, case C", "views"),
    ("plane_funicular", "Plane: catenary under a pseudo-static action", "views"),
    ("arch_assessment", "Arch: semicircular arch under a horizontal action", "views"),
]
SIZE = (1480, 920)


def main():
    os.makedirs(OUT, exist_ok=True)
    app = QApplication([__app_name__])
    app.setApplicationName(__app_name__)
    theme.apply(app)
    with tempfile.TemporaryDirectory() as tmp:
        window = MainWindow()
        window.settings = QSettings(os.path.join(tmp, "settings.ini"), QSettings.IniFormat)
        window.resize(*SIZE)
        window.show()
        app.processEvents()
        for name, example, tab in SHOTS:
            window.load_project(EXAMPLES[example](), run=True)
            if window.result is None:
                raise SystemExit("the example did not solve: %s" % example)
            window.results.setCurrentIndex(TABS[tab])
            app.processEvents()
            focus = app.focusWidget()
            if focus is not None:
                focus.clearFocus()
            page = window.results.currentWidget()
            if hasattr(page, "canvas"):
                page.canvas.draw()
            app.processEvents()
            raw = os.path.join(tmp, name + ".png")
            window.grab().save(raw)
            image = Image.open(raw).convert("RGB")
            image = image.quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
            path = os.path.join(OUT, name + ".png")
            image.save(path, optimize=True)
            print("%s  %d x %d  %d kB" % (os.path.relpath(path, ROOT), image.width, image.height,
                                          os.path.getsize(path) // 1024))
        window.dirty = False
        window.hide()


if __name__ == "__main__":
    main()
