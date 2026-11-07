"""Application entry point.

    funis [project.funis]        open the window, with a project file if given
    funis --selftest [screenshot]    open the window, run every example, save a
                                         screenshot and exit with 0 (used after a build)

The self-test also writes its report to a file next to the screenshot, with the
extension .log: a windowed program on Windows has no console. Any error ends it
with a non-zero exit code instead of an error window that nobody could close.
"""
import os
import sys
import traceback

import matplotlib


def _log_path(screenshot):
    return os.path.splitext(screenshot)[0] + ".log" if screenshot else None


def _report(screenshot, text):
    """Print a line of the self-test report and append it to the log file."""
    print(text)
    path = _log_path(screenshot)
    if path:
        try:
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(text + "\n")
        except OSError:
            pass


def main(argv=None):
    argv = list(sys.argv if argv is None else argv)
    if "--selftest" not in argv:
        return _start(argv)
    args = [a for a in argv[1:] if not a.startswith("--")]
    screenshot = args[0] if args else None
    path = _log_path(screenshot)
    if path and os.path.exists(path):
        os.remove(path)
    try:
        return _start(argv)
    except Exception:
        _report(screenshot, "selftest: the program did not start\n" + traceback.format_exc())
        return 2


def _start(argv):
    matplotlib.use("QtAgg")
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
    try:
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
        _report(screenshot, "selftest: %d examples, %d failures" % (len(EXAMPLES), len(failures)))
        for name in failures:
            _report(screenshot, "  failed: %s" % name)
        code = 1 if failures else 0
    except Exception:
        _report(screenshot, "selftest: error\n" + traceback.format_exc())
        code = 2
    window.dirty = False
    app.exit(code)
