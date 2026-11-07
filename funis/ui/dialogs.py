"""Dialogs: export of drawings, about, user guide."""
import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog,
                               QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QRadioButton,
                               QTextBrowser, QVBoxLayout)

from .. import __app_name__, __tagline__, __version__
from .widgets import IntSpin, Spin, form


class ExportDrawingsDialog(QDialog):
    """Choice of the drawings, the format and the size or the scale."""

    def __init__(self, result, folder, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Export drawings")
        self.result = result
        lay = QVBoxLayout(self)
        box = QGroupBox("Drawings")
        bl = QVBoxLayout(box)
        self.checks = {}
        for key, d in result.drawings.items():
            c = QCheckBox(d.name)
            c.setChecked(True)
            bl.addWidget(c)
            self.checks[key] = c
        lay.addWidget(box)
        box = QGroupBox("Output")
        f = form()
        self.fmt = QComboBox()
        for k in ("pdf", "svg", "png"):
            self.fmt.addItem(k.upper(), k)
        f.addRow("Format", self.fmt)
        self.fit = QRadioButton("Fit to a width")
        self.fit.setChecked(True)
        self.width = Spin(14.0, 2.0, 100.0, 1.0, 1, "cm")
        self.to_scale = QRadioButton("Views to scale, without axes")
        self.length_scale = Spin(1.0, 0.001, 1000.0, 0.1, 3, "cm/m")
        self.force_scale = Spin(0.5, 0.0001, 1000.0, 0.01, 4, "cm/kN")
        self.dpi = IntSpin(300, 50, 1200)
        f.addRow(self.fit, self.width)
        f.addRow(self.to_scale, QLabel("one scale for plans and elevations, one for diagrams in kN or kN/m;\ngraphs along the path are fitted to the width"))
        f.addRow("Length scale", self.length_scale)
        f.addRow("Force scale", self.force_scale)
        f.addRow("Resolution (PNG)", self.dpi)
        self.base = QLineEdit(os.path.join(folder, _safe(result.project.name)))
        browse = QPushButton("Browse")
        browse.clicked.connect(self._browse)
        row = QHBoxLayout()
        row.addWidget(self.base, 1)
        row.addWidget(browse)
        f.addRow("File name base", row)
        f.addRow(QLabel("Each drawing is written as <base>_<diagram>.<format>."))
        box.setLayout(f)
        lay.addWidget(box)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)
        self.fit.toggled.connect(self._switch)
        self._switch()

    def _switch(self):
        fit = self.fit.isChecked()
        self.width.setEnabled(fit)
        self.length_scale.setEnabled(not fit)
        self.force_scale.setEnabled(not fit)

    def _browse(self):
        path, _ = QFileDialog.getSaveFileName(self, "File name base", self.base.text())
        if path:
            self.base.setText(os.path.splitext(path)[0])

    def options(self):
        keys = [k for k, c in self.checks.items() if c.isChecked()]
        return dict(keys=keys, fmt=self.fmt.currentData(), width=self.width.value(),
                    to_scale=self.to_scale.isChecked(), length_scale=self.length_scale.value(),
                    force_scale=self.force_scale.value(), dpi=self.dpi.value(), base=self.base.text())


def _safe(name):
    keep = "".join(c if c.isalnum() or c in "-_ " else "_" for c in name).strip()
    return keep.replace(" ", "_")[:60] or "funis"


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About %s" % __app_name__)
        lay = QVBoxLayout(self)
        t = QLabel("<h2>%s %s</h2><p>%s.</p>" % (__app_name__, __version__, __tagline__))
        t.setTextFormat(Qt.RichText)
        lay.addWidget(t)
        body = QLabel(
            "<p>Analytical Linear Arch Static Analysis (LASA) of continuous spatial compression "
            "paths under vertical and horizontal loads: supported paths with their lateral "
            "reactions and contact conditions, paths without reactions, form-finding of free "
            "curves and node equilibrium under concentrated forces. In the plane: the funicular "
            "line under vertical and horizontal loads (catenary, parabola, funicular polygon) and "
            "the thrust line assessment of arches of finite thickness.</p>"
            "<p>The equations follow C. Olivieri, <i>Equilibrium and form-finding of spatial "
            "compression paths under multidirectional loading through Linear Arch Static "
            "Analysis</i>.</p>"
            "<p>Units: lengths in m, forces in kN, densities in kN per metre of projected length. "
            "Tension positive, compression S ≤ 0.</p>"
            "<p>Released under the MIT License. Copyright (c) 2026 Carlo Olivieri.</p>")
        body.setWordWrap(True)
        body.setTextFormat(Qt.RichText)
        lay.addWidget(body)
        b = QDialogButtonBox(QDialogButtonBox.Close)
        b.rejected.connect(self.reject)
        b.accepted.connect(self.accept)
        lay.addWidget(b)


class GuideDialog(QDialog):
    def __init__(self, html, parent=None):
        super().__init__(parent)
        self.setWindowTitle("%s user guide" % __app_name__)
        self.resize(760, 640)
        lay = QVBoxLayout(self)
        view = QTextBrowser()
        view.setOpenExternalLinks(True)
        view.setHtml(html)
        lay.addWidget(view)
        b = QDialogButtonBox(QDialogButtonBox.Close)
        b.rejected.connect(self.reject)
        b.accepted.connect(self.accept)
        lay.addWidget(b)
