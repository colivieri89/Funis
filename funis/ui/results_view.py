"""Presentation of the results: summary, views to scale, graphs, contact or admissible thrusts, spatial view
and tables."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QFrame, QGridLayout, QHBoxLayout,
                               QHeaderView, QLabel, QScrollArea, QSizePolicy, QTableWidget,
                               QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure

from ..diagrams import GROUPS
from ..render import apply_style, draw
from .canvas import SpatialCanvas


def _clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        w = item.widget()
        if w is not None:
            w.hide()
            w.setParent(None)
            w.deleteLater()


class MultiCanvas(QWidget):
    """Several drawings in one figure, or one of them enlarged."""

    def __init__(self, parent=None):
        super().__init__(parent)
        apply_style()
        self.figure = Figure(figsize=(8, 6), dpi=100, facecolor="white")
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)
        self.toolbar.setStyleSheet("QToolBar { border: none; background: white; }")
        self.selector = QComboBox()
        self.selector.setMinimumWidth(240)
        self.selector.currentIndexChanged.connect(lambda *_: self._redraw())
        top = QHBoxLayout()
        top.setContentsMargins(6, 4, 6, 0)
        top.addWidget(QLabel("Show"))
        top.addWidget(self.selector)
        top.addStretch(1)
        top.addWidget(self.toolbar)
        self.note = QLabel("")
        self.note.setObjectName("muted")
        self.note.setWordWrap(True)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(2)
        lay.addLayout(top)
        lay.addWidget(self.canvas, 1)
        lay.addWidget(self.note)
        self.drawings = []

    def set_drawings(self, drawings):
        """drawings: list of (key, Drawing)."""
        self.drawings = list(drawings)
        self.selector.blockSignals(True)
        self.selector.clear()
        self.selector.addItem("All diagrams", None)
        for key, d in self.drawings:
            self.selector.addItem(d.name, key)
        self.selector.blockSignals(False)
        self._redraw()

    def _redraw(self):
        self.figure.clear()
        key = self.selector.currentData()
        if not self.drawings:
            self.note.setText("")
            self.canvas.draw_idle()
            return
        if key is None:
            n = len(self.drawings)
            cols = 1 if n == 1 else 2
            rows = (n + cols - 1) // cols
            notes = []
            for k, (_, d) in enumerate(self.drawings):
                ax = self.figure.add_subplot(rows, cols, k + 1)
                draw(ax, d, grid=True, font_size=8.5)
                notes.extend(d.notes)
            self.figure.subplots_adjust(left=0.07, right=0.98, top=0.94, bottom=0.08, wspace=0.22,
                                        hspace=0.32 if rows < 3 else 0.55)
            self.note.setText("  ".join(dict.fromkeys(notes)))
        else:
            d = dict(self.drawings)[key]
            ax = self.figure.add_subplot(111)
            draw(ax, d, grid=True, font_size=9.5)
            self.figure.subplots_adjust(left=0.08, right=0.98, top=0.93, bottom=0.09)
            self.note.setText("  ".join(d.notes))
        self.canvas.draw_idle()

    def current_figure(self):
        return self.figure


class SummaryView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        self.lay = QVBoxLayout(inner)
        self.lay.setContentsMargins(16, 16, 16, 16)
        self.lay.setSpacing(10)
        self.title = QLabel("No results yet")
        self.title.setObjectName("heading")
        self.subtitle = QLabel("Fill in the model and press Run, or open an example from the toolbar.")
        self.subtitle.setObjectName("muted")
        self.subtitle.setWordWrap(True)
        self.notes = QLabel("")
        self.notes.setWordWrap(True)
        self.messages = QVBoxLayout()
        self.messages.setSpacing(6)
        self.card = QFrame()
        self.card.setObjectName("summary")
        self.grid = QGridLayout(self.card)
        self.grid.setContentsMargins(14, 10, 14, 10)
        self.grid.setHorizontalSpacing(18)
        self.grid.setVerticalSpacing(5)
        self.lay.addWidget(self.title)
        self.lay.addWidget(self.subtitle)
        self.lay.addWidget(self.notes)
        self.lay.addLayout(self.messages)
        self.lay.addWidget(self.card)
        self.lay.addStretch(1)
        scroll.setWidget(inner)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        self.card.hide()

    def _clear_messages(self):
        _clear_layout(self.messages)

    def show_result(self, result):
        p = result.project
        self.title.setText(p.name)
        self.subtitle.setText(p.task_label)
        self.notes.setText(p.notes)
        self.notes.setVisible(bool(p.notes))
        self._clear_messages()
        for m in result.messages:
            l = QLabel(m)
            l.setObjectName("warning")
            l.setWordWrap(True)
            self.messages.addWidget(l)
        _clear_layout(self.grid)
        for r, (k, v) in enumerate(result.summary):
            lk = QLabel(str(k))
            lk.setStyleSheet("font-weight: 600;")
            lv = QLabel(str(v))
            lv.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self.grid.addWidget(lk, r, 0, alignment=Qt.AlignRight | Qt.AlignTop)
            self.grid.addWidget(lv, r, 1)
        self.grid.setColumnStretch(1, 1)
        self.card.show()

    def show_error(self, text, project=None):
        if project is not None:
            self.title.setText(project.name)
            self.subtitle.setText(project.task_label)
        self.notes.hide()
        self._clear_messages()
        l = QLabel(text)
        l.setObjectName("error")
        l.setWordWrap(True)
        self.messages.addWidget(l)
        self.card.hide()


class TableView(QTableWidget):
    def __init__(self, table, parent=None):
        super().__init__(len(table.rows), len(table.columns), parent)
        self.setHorizontalHeaderLabels(table.columns)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(22)
        for r, row in enumerate(table.rows):
            for c, v in enumerate(row):
                text = ("%.4f" % v) if isinstance(v, float) else str(v)
                it = QTableWidgetItem(text)
                it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.setItem(r, c, it)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.horizontalHeader().setStretchLastSection(True)


class TablesView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.addWidget(self.tabs)

    def show_result(self, result):
        self.tabs.clear()
        for key, table in result.tables.items():
            w = QWidget()
            l = QVBoxLayout(w)
            l.setContentsMargins(4, 6, 4, 4)
            l.addWidget(TableView(table))
            if table.note:
                n = QLabel(table.note)
                n.setObjectName("muted")
                n.setWordWrap(True)
                l.addWidget(n)
            self.tabs.addTab(w, table.name)


VIEW_KEYS = GROUPS["views"]
GRAPH_KEYS = GROUPS["graphs"]
CONTACT_KEYS = GROUPS["contact"]


class ResultsView(QTabWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDocumentMode(True)
        self.summary = SummaryView()
        self.views = MultiCanvas()
        self.graphs = MultiCanvas()
        self.contact = MultiCanvas()
        self.spatial = SpatialCanvas()
        self.tables = TablesView()
        self.addTab(self.summary, "Summary")
        self.addTab(self.views, "Views")
        self.addTab(self.graphs, "Graphs")
        self.addTab(self.contact, "Contact")
        self.addTab(self.spatial, "Spatial view")
        self.addTab(self.tables, "Tables")
        self.result = None
        self._set_enabled(True, False, False)

    def _set_enabled(self, graphs, contact, spatial):
        self.setTabEnabled(2, graphs)
        self.setTabEnabled(3, contact)
        self.setTabEnabled(4, spatial)

    def show_result(self, result):
        self.result = result
        self.summary.show_result(result)
        views = [(k, result.drawings[k]) for k in VIEW_KEYS if k in result.drawings]
        self.views.set_drawings(views)
        graphs = [(k, result.drawings[k]) for k in GRAPH_KEYS if k in result.drawings]
        self.graphs.set_drawings(graphs)
        contact = [(k, result.drawings[k]) for k in CONTACT_KEYS if k in result.drawings]
        self.contact.set_drawings(contact)
        titles = result.data.get("group_titles", {}) if isinstance(result.data, dict) else {}
        self.setTabText(3, titles.get("contact", "Contact"))
        has3d = result.spatial is not None
        self.spatial.show_spatial(result.spatial)
        self.tables.show_result(result)
        self._set_enabled(bool(graphs), bool(contact), has3d)
        if self.currentIndex() in (2, 3, 4) and not self.isTabEnabled(self.currentIndex()):
            self.setCurrentIndex(1)

    def show_error(self, text, project=None):
        self.summary.show_error(text, project)
        self.setCurrentIndex(0)
