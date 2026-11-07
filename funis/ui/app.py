"""Application entry point.

    funis [project.funis]        open the window, with a project file if given
    funis --selftest [screenshot]    open the window, run every example, save a
                                         screenshot and exit with 0 (used after a build)
"""
import os
import sys

import matplotlib


def main(argv=None):
    matplotlib.use("QtAgg")
    argv = list(sys.argv if argv is None else argv)
    selftest = "--selftest" in argv
    args = [a for a in argv[1:] if not a.startswith("--")]
    if selftest and os.environ.get("QT_QPA_PLATFORM") is None:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"

    from PySide6.QtCore import QTimer
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication

    from .. import __app_name__, __organization__
    from . import theme
    from .main_window import ASSETS, MainWindow

    app = QApplication(argv[:1])
    app.setApplicationName(__app_name__)
    app.setOrganizationName(__organization__)
    app.setApplicationDisplayName(__app_name__)
    icon = os.path.join(ASSETS, "icon.png")
    if os.path.exists(icon):
        app.setWindowIcon(QIcon(icon))
    theme.apply(app)
    window = MainWindow()
    window.show()
    if args and os.path.exists(args[0]) and not selftest:
        from ..io import project_file
        try:
            window.load_project(project_file.load(args[0]), args[0])
        except Exception as exc:
            window.status.setText("The file could not be read: %s" % exc)
    if selftest:
        QTimer.singleShot(200, lambda: _selftest(app, window, args[0] if args else None))
    return app.exec()


def _selftest(app, window, screenshot):
    from ..examples import EXAMPLES
    failures = []
    for name, fn in EXAMPLES.items():
        window.load_project(fn(), run=True)
        app.processEvents()
        if window.result is None:
            failures.append(name)
    for tab in range(window.results.count()):
        if window.results.isTabEnabled(tab):
            window.results.setCurrentIndex(tab)
            app.processEvents()
    window.results.setCurrentIndex(1)
    app.processEvents()
    if screenshot:
        window.grab().save(screenshot)
    print("selftest: %d examples, %d failures" % (len(EXAMPLES), len(failures)))
    for name in failures:
        print("  failed:", name)
    window.dirty = False
    app.exit(1 if failures else 0)
