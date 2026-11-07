"""Matplotlib canvases for the drawings and the spatial view."""
import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from PySide6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget

from ..drawing import ROLES
from ..render import apply_style, draw


class DrawingCanvas(QWidget):
    """One drawing with its navigation toolbar."""

    def __init__(self, parent=None):
        super().__init__(parent)
        apply_style()
        self.figure = Figure(figsize=(6, 4.5), dpi=100, facecolor="white")
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)
        self.toolbar.setStyleSheet("QToolBar { border: none; background: white; }")
        self.note = QLabel("")
        self.note.setObjectName("muted")
        self.note.setWordWrap(True)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(2)
        lay.addWidget(self.toolbar)
        lay.addWidget(self.canvas, 1)
        lay.addWidget(self.note)
        self.drawing = None
        self.grid = True

    def show_drawing(self, drawing, grid=None):
        if grid is not None:
            self.grid = grid
        self.drawing = drawing
        self.figure.clear()
        if drawing is None:
            self.note.setText("")
            self.canvas.draw_idle()
            return
        ax = self.figure.add_subplot(111)
        draw(ax, drawing, grid=self.grid)
        self.figure.subplots_adjust(left=0.1, right=0.97, top=0.9, bottom=0.12)
        self.note.setText("  ".join(drawing.notes))
        self.canvas.draw_idle()

    def clear(self):
        self.show_drawing(None)


class SpatialCanvas(QWidget):
    """Axonometric view of the spatial path with its loads and reactions."""

    def __init__(self, parent=None):
        super().__init__(parent)
        apply_style()
        self.figure = Figure(figsize=(6, 5), dpi=100, facecolor="white")
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)
        self.toolbar.setStyleSheet("QToolBar { border: none; background: white; }")
        self.note = QLabel("")
        self.note.setObjectName("muted")
        self.note.setWordWrap(True)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(2)
        lay.addWidget(self.toolbar)
        lay.addWidget(self.canvas, 1)
        lay.addWidget(self.note)

    def show_spatial(self, spatial):
        """spatial: dict with xyz, arrows [(point, vector, role)], markers [(point, role, text)], note."""
        self.figure.clear()
        if spatial is None:
            self.note.setText("")
            self.canvas.draw_idle()
            return
        ax = self.figure.add_subplot(111, projection="3d")
        X = np.asarray(spatial["xyz"], float)
        zmin = X[:, 2].min()
        ax.plot(X[:, 0], X[:, 1], np.full(len(X), zmin), color=ROLES["light"], lw=1.1)
        step = max(1, len(X) // 24)
        for p in X[::step]:
            ax.plot([p[0], p[0]], [p[1], p[1]], [zmin, p[2]], color=ROLES["light"], lw=0.5, ls=":")
        ax.plot(X[:, 0], X[:, 1], X[:, 2], color=ROLES["ink"], lw=2.0)
        pts = [X]
        for p, v, role in spatial.get("arrows", []):
            p, v = np.asarray(p, float), np.asarray(v, float)
            if np.linalg.norm(v) < 1e-12:
                continue
            if role in ("reaction", "vertical"):
                tail = p - v
            else:
                tail = p
            ax.quiver(tail[0], tail[1], tail[2], v[0], v[1], v[2], color=ROLES[role],
                      arrow_length_ratio=0.25, lw=1.2)
            pts.append(np.vstack([tail, tail + v]))
        for p, role, text in spatial.get("markers", []):
            p = np.asarray(p, float)
            ax.scatter([p[0]], [p[1]], [p[2]], color=ROLES[role], s=18, depthshade=False)
            if text:
                ax.text(p[0], p[1], p[2], "  " + text, color=ROLES[role], fontsize=8)
            pts.append(p[None, :])
        P = np.vstack(pts)
        c = 0.5 * (P.min(axis=0) + P.max(axis=0))
        half = max(np.ptp(P, axis=0).max(), 1e-6) * 0.55
        ax.set_xlim(c[0] - half, c[0] + half)
        ax.set_ylim(c[1] - half, c[1] + half)
        ax.set_zlim(c[2] - half, c[2] + half)
        ax.set_box_aspect((1, 1, 1))
        ax.set_xlabel("x₁ [m]", fontsize=8)
        ax.set_ylabel("x₂ [m]", fontsize=8)
        ax.set_zlabel("x₃ [m]", fontsize=8)
        ax.tick_params(labelsize=7)
        ax.view_init(elev=26, azim=-60)
        ax.xaxis.pane.set_facecolor("#f7f9fb")
        ax.yaxis.pane.set_facecolor("#f7f9fb")
        ax.zaxis.pane.set_facecolor("#ffffff")
        self.figure.subplots_adjust(left=0.0, right=1.0, top=1.0, bottom=0.0)
        self.note.setText("Drag to rotate, right-drag to zoom. " + spatial.get("note", ""))
        self.canvas.draw_idle()
