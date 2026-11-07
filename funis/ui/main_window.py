"""Main window: model panel on the left, results on the right."""
import os
import traceback

from PySide6.QtCore import QSettings, Qt, QTimer
from PySide6.QtGui import QAction, QIcon, QKeySequence
from PySide6.QtWidgets import (QDockWidget, QFileDialog, QLabel, QMainWindow, QMenu, QMessageBox,
                               QToolBar, QToolButton, QWidget)

from .. import __app_name__, __version__, analysis
from ..examples import EXAMPLES
from ..io import dxf, project_file, report, tables
from ..model import Project
from ..render import figure_for
from .dialogs import AboutDialog, ExportDrawingsDialog, GuideDialog
from .panels import ModelPanel
from .results_view import ResultsView

ASSETS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
DEFAULT_EXAMPLE = "Supported: Figs. 11 and 12, circular benchmark with contact"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(__app_name__)
        self.resize(1480, 920)
        self.settings = QSettings("Funis", "Funis")
        self.path = None
        self.result = None
        self.dirty = False
        icon = os.path.join(ASSETS, "icon.png")
        if os.path.exists(icon):
            self.setWindowIcon(QIcon(icon))

        self.panel = ModelPanel()
        dock = QDockWidget("Model", self)
        dock.setObjectName("model_dock")
        dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        dock.setWidget(self.panel)
        dock.setMinimumWidth(480)
        self.addDockWidget(Qt.LeftDockWidgetArea, dock)
        self.results = ResultsView()
        self.setCentralWidget(self.results)

        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(350)
        self.timer.timeout.connect(self.run)
        self.panel.changed.connect(self._on_changed)

        self._build_actions()
        self._build_menus()
        self._build_toolbar()
        self.status = QLabel("Ready")
        self.statusBar().addWidget(self.status, 1)
        self.version_label = QLabel("%s %s" % (__app_name__, __version__))
        self.version_label.setObjectName("muted")
        self.statusBar().addPermanentWidget(self.version_label)
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
        self.load_project(EXAMPLES[DEFAULT_EXAMPLE](), run=True)
        self.path = None

    # ------------------------------------------------------------ actions and menus
    def _build_actions(self):
        self.act_new = QAction("New project", self, shortcut=QKeySequence.New, triggered=self.new_project)
        self.act_open = QAction("Open…", self, shortcut=QKeySequence.Open, triggered=self.open_project)
        self.act_save = QAction("Save", self, shortcut=QKeySequence.Save, triggered=self.save_project)
        self.act_save_as = QAction("Save as…", self, shortcut=QKeySequence.SaveAs, triggered=self.save_project_as)
        self.act_quit = QAction("Quit", self, shortcut=QKeySequence.Quit, triggered=self.close)
        self.act_run = QAction("Run", self, shortcut="F5", triggered=self.run)
        self.act_auto = QAction("Run automatically", self, checkable=True)
        self.act_auto.setChecked(self.settings.value("auto_run", "true") == "true")
        self.act_auto.toggled.connect(lambda v: self.settings.setValue("auto_run", "true" if v else "false"))
        self.act_export_drawings = QAction("Drawings (PDF, SVG, PNG)…", self, triggered=self.export_drawings)
        self.act_export_dxf = QAction("Drawings as DXF…", self, triggered=self.export_dxf)
        self.act_export_csv = QAction("Tables as CSV…", self, triggered=lambda: self.export_tables("csv"))
        self.act_export_xlsx = QAction("Tables as Excel…", self, triggered=lambda: self.export_tables("xlsx"))
        self.act_export_json = QAction("Results as JSON…", self, triggered=lambda: self.export_tables("json"))
        self.act_export_report = QAction("Report (HTML)…", self, triggered=self.export_report)
        self.act_guide = QAction("User guide", self, shortcut=QKeySequence.HelpContents, triggered=self.show_guide)
        self.act_about = QAction("About %s" % __app_name__, self, triggered=lambda: AboutDialog(self).exec())

    def _examples_menu(self):
        menu = QMenu("Examples", self)
        group = None
        for name, fn in EXAMPLES.items():
            prefix = name.split(":")[0]
            if prefix != group:
                if group is not None:
                    menu.addSeparator()
                group = prefix
            act = menu.addAction(name)
            act.triggered.connect(lambda checked=False, f=fn: self.load_example(f))
        return menu

    def _build_menus(self):
        bar = self.menuBar()
        m = bar.addMenu("File")
        m.addAction(self.act_new)
        m.addAction(self.act_open)
        m.addMenu(self._examples_menu())
        m.addSeparator()
        m.addAction(self.act_save)
        m.addAction(self.act_save_as)
        m.addSeparator()
        ex = m.addMenu("Export")
        for a in (self.act_export_drawings, self.act_export_dxf, self.act_export_csv, self.act_export_xlsx,
                  self.act_export_json, self.act_export_report):
            ex.addAction(a)
        m.addSeparator()
        m.addAction(self.act_quit)
        m = bar.addMenu("Analysis")
        m.addAction(self.act_run)
        m.addAction(self.act_auto)
        m = bar.addMenu("Help")
        m.addAction(self.act_guide)
        m.addAction(self.act_about)

    def _build_toolbar(self):
        tb = QToolBar("Main")
        tb.setObjectName("main_toolbar")
        tb.setMovable(False)
        tb.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.addToolBar(tb)
        tb.addAction(self.act_new)
        tb.addAction(self.act_open)
        tb.addAction(self.act_save)
        tb.addSeparator()
        b = QToolButton()
        b.setText("Examples")
        b.setPopupMode(QToolButton.InstantPopup)
        b.setMenu(self._examples_menu())
        tb.addWidget(b)
        tb.addSeparator()
        tb.addAction(self.act_run)
        tb.addAction(self.act_auto)
        tb.addSeparator()
        b = QToolButton()
        b.setText("Export")
        b.setPopupMode(QToolButton.InstantPopup)
        menu = QMenu(b)
        for a in (self.act_export_drawings, self.act_export_dxf, self.act_export_csv, self.act_export_xlsx,
                  self.act_export_json, self.act_export_report):
            menu.addAction(a)
        b.setMenu(menu)
        tb.addWidget(b)
        spacer = QWidget()
        spacer.setSizePolicy(spacer.sizePolicy().horizontalPolicy().Expanding, spacer.sizePolicy().verticalPolicy())
        tb.addWidget(spacer)
        tb.addAction(self.act_guide)

    # ------------------------------------------------------------ project handling
    def _on_changed(self):
        self.dirty = True
        self._update_title()
        if self.act_auto.isChecked():
            self.timer.start()

    def _update_title(self):
        name = os.path.basename(self.path) if self.path else "untitled"
        self.setWindowTitle("%s%s – %s" % (name, "*" if self.dirty else "", __app_name__))

    def load_project(self, project, path=None, run=True):
        self.panel.from_project(project)
        self.path = path
        self.dirty = False
        self._update_title()
        if run:
            self.run()

    def load_example(self, fn):
        if not self._confirm_discard():
            return
        self.load_project(fn())

    def new_project(self):
        if not self._confirm_discard():
            return
        self.load_project(Project(name="Untitled"), run=False)
        self.results.show_error("New project: fill in the model and press Run.", self.panel.to_project())

    def _confirm_discard(self):
        if not self.dirty:
            return True
        r = QMessageBox.question(self, __app_name__, "The project has unsaved changes. Discard them?",
                                 QMessageBox.Discard | QMessageBox.Cancel)
        return r == QMessageBox.Discard

    def _folder(self):
        return self.settings.value("folder", os.path.expanduser("~"))

    def _remember(self, path):
        self.settings.setValue("folder", os.path.dirname(path))

    def open_project(self):
        if not self._confirm_discard():
            return
        path, _ = QFileDialog.getOpenFileName(self, "Open project", self._folder(),
                                              "Funis project (*.funis *.json)")
        if not path:
            return
        try:
            project = project_file.load(path)
        except Exception as exc:
            QMessageBox.critical(self, __app_name__, "The file could not be read:\n%s" % exc)
            return
        self._remember(path)
        self.load_project(project, path)

    def save_project(self):
        if self.path is None:
            return self.save_project_as()
        try:
            project_file.save(self.panel.to_project(), self.path)
        except Exception as exc:
            QMessageBox.critical(self, __app_name__, "The project could not be saved:\n%s" % exc)
            return False
        self.dirty = False
        self._update_title()
        self.status.setText("Saved %s" % self.path)
        return True

    def save_project_as(self):
        base = self.path or os.path.join(self._folder(), "project" + project_file.EXTENSION)
        path, _ = QFileDialog.getSaveFileName(self, "Save project", base, "Funis project (*.funis)")
        if not path:
            return False
        if not path.endswith(project_file.EXTENSION):
            path += project_file.EXTENSION
        self.path = path
        self._remember(path)
        return self.save_project()

    # ------------------------------------------------------------ analysis
    def run(self):
        self.timer.stop()
        try:
            project = self.panel.to_project()
        except ValueError as exc:
            self.results.show_error("Input error: %s" % exc)
            self.status.setText("Input error")
            return
        try:
            self.result = analysis.run(project)
        except analysis.InputError as exc:
            self.result = None
            self.results.show_error(str(exc), project)
            self.status.setText("The task could not be solved: %s" % exc)
            return
        except Exception as exc:
            self.result = None
            self.results.show_error("Unexpected error: %s\n%s" % (exc, traceback.format_exc()), project)
            self.status.setText("Unexpected error")
            return
        self.results.show_result(self.result)
        n = len(self.result.messages)
        self.status.setText("%s solved%s" % (project.task_label, ", %d warning%s" % (n, "s" if n > 1 else "") if n else ""))

    # ------------------------------------------------------------ exports
    def _need_result(self):
        if self.result is None:
            QMessageBox.information(self, __app_name__, "Run the analysis first.")
            return False
        return True

    def export_drawings(self):
        if not self._need_result():
            return
        dlg = ExportDrawingsDialog(self.result, self._folder(), self)
        if dlg.exec() != dlg.Accepted:
            return
        o = dlg.options()
        if not o["keys"]:
            return
        written = []
        try:
            for key in o["keys"]:
                d = self.result.drawings[key]
                if o["to_scale"] and d.aspect == "equal":
                    scale = o["length_scale"] if d.unit == "m" else o["force_scale"]
                    fig = figure_for(d, scale=scale, dpi=o["dpi"])
                else:
                    fig = figure_for(d, width_cm=o["width"], dpi=o["dpi"])
                path = "%s_%s.%s" % (o["base"], key, o["fmt"])
                fig.savefig(path, dpi=o["dpi"], facecolor="white")
                written.append(path)
        except Exception as exc:
            QMessageBox.critical(self, __app_name__, "Export failed:\n%s" % exc)
            return
        self._remember(written[0])
        self.status.setText("Written %d file%s in %s" % (len(written), "s" if len(written) > 1 else "",
                                                          os.path.dirname(written[0])))

    def export_dxf(self):
        if not self._need_result():
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export DXF", os.path.join(self._folder(), "drawings.dxf"),
                                              "DXF (*.dxf)")
        if not path:
            return
        try:
            dxf.write(self.result, path, force_scale=0.1)
        except Exception as exc:
            QMessageBox.critical(self, __app_name__, "Export failed:\n%s" % exc)
            return
        self._remember(path)
        self.status.setText("Written %s (views to scale; diagrams in kN or kN/m at 0.1 drawing units per unit)" % path)

    def export_tables(self, kind):
        if not self._need_result():
            return
        names = {"csv": ("CSV (*.csv)", tables.to_csv), "xlsx": ("Excel workbook (*.xlsx)", tables.to_xlsx),
                 "json": ("JSON (*.json)", tables.to_json)}
        filt, writer = names[kind]
        path, _ = QFileDialog.getSaveFileName(self, "Export", os.path.join(self._folder(), "results." + kind), filt)
        if not path:
            return
        try:
            writer(self.result, path)
        except Exception as exc:
            QMessageBox.critical(self, __app_name__, "Export failed:\n%s" % exc)
            return
        self._remember(path)
        self.status.setText("Written %s" % path)

    def export_report(self):
        if not self._need_result():
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export report", os.path.join(self._folder(), "report.html"),
                                              "HTML (*.html)")
        if not path:
            return
        try:
            report.write(self.result, path)
        except Exception as exc:
            QMessageBox.critical(self, __app_name__, "Export failed:\n%s" % exc)
            return
        self._remember(path)
        self.status.setText("Written %s" % path)

    # ------------------------------------------------------------ help and closing
    def show_guide(self):
        guide = os.path.join(ASSETS, "user_guide.html")
        if os.path.exists(guide):
            with open(guide, "r", encoding="utf-8") as fh:
                html = fh.read()
        else:
            html = "<p>The user guide is not available in this installation.</p>"
        GuideDialog(html, self).exec()

    def closeEvent(self, event):
        if not self._confirm_discard():
            event.ignore()
            return
        self.settings.setValue("geometry", self.saveGeometry())
        event.accept()
