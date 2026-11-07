"""Reusable input widgets."""
from PySide6.QtCore import QLocale, Qt, Signal
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QDoubleSpinBox, QFormLayout,
                               QHBoxLayout, QHeaderView, QLabel, QPushButton, QSpinBox,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)


class Spin(QDoubleSpinBox):
    """Spin box that shows up to `decimals` digits without trailing zeros."""

    def __init__(self, value=0.0, lo=-1e9, hi=1e9, step=0.1, decimals=6, suffix="", parent=None):
        super().__init__(parent)
        self.setLocale(QLocale.c())
        self.setRange(lo, hi)
        self.setDecimals(max(decimals, 6))
        self.setSingleStep(step)
        self.setValue(value)
        self.setKeyboardTracking(False)
        self.setAlignment(Qt.AlignRight)
        if suffix:
            self.setSuffix(" " + suffix)
        self.setMinimumWidth(90)

    def textFromValue(self, value):
        text = ("%.*f" % (self.decimals(), value)).rstrip("0").rstrip(".")
        return text if text not in ("", "-") else "0"


class IntSpin(QSpinBox):
    def __init__(self, value=1, lo=1, hi=100000, parent=None):
        super().__init__(parent)
        self.setLocale(QLocale.c())
        self.setRange(lo, hi)
        self.setValue(value)
        self.setKeyboardTracking(False)
        self.setAlignment(Qt.AlignRight)
        self.setMinimumWidth(96)


class Combo(QComboBox):
    """Combo box whose items carry keys."""

    def __init__(self, items, parent=None):
        super().__init__(parent)
        for key, label in items:
            self.addItem(label, key)

    def key(self):
        return self.currentData()

    def set_key(self, key):
        idx = self.findData(key)
        if idx >= 0:
            self.setCurrentIndex(idx)


class ArrayTable(QWidget):
    """Table of numbers with row tools, read as a list of rows."""

    changed = Signal()

    def __init__(self, columns, rows=0, row_label="row", first_index=0, fixed_rows=False,
                 decimals=4, parent=None, help_text=""):
        super().__init__(parent)
        self.columns = list(columns)
        self.first_index = first_index
        self.row_label = row_label
        self.decimals = decimals
        self.table = QTableWidget(rows, len(columns))
        self.table.setHorizontalHeaderLabels(self.columns)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setDefaultSectionSize(22)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.AllEditTriggers)
        self.table.itemChanged.connect(self._on_item_changed)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        if help_text:
            h = QLabel(help_text)
            h.setObjectName("muted")
            h.setWordWrap(True)
            lay.addWidget(h)
        lay.addWidget(self.table)
        tools = QHBoxLayout()
        tools.setSpacing(4)
        self.fixed_rows = fixed_rows
        if not fixed_rows:
            add = QPushButton("Add row")
            rem = QPushButton("Remove")
            add.clicked.connect(self.add_row)
            rem.clicked.connect(self.remove_rows)
            tools.addWidget(add)
            tools.addWidget(rem)
        fill = QPushButton("Fill column")
        fill.setToolTip("Copy the value of the selected cell to the whole column")
        fill.clicked.connect(self.fill_column)
        tools.addWidget(fill)
        tools.addStretch(1)
        lay.addLayout(tools)
        self._block = False
        self._relabel()
        self.table.setMinimumHeight(min(max(rows, 3), 10) * 22 + 28)

    def _relabel(self):
        for r in range(self.table.rowCount()):
            self.table.setVerticalHeaderItem(r, QTableWidgetItem("%s %d" % (self.row_label, r + self.first_index)))

    def _on_item_changed(self, item):
        if not self._block:
            self.changed.emit()

    def set_rows(self, rows):
        """Rows as lists of floats."""
        self._block = True
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c in range(len(self.columns)):
                v = row[c] if c < len(row) else 0.0
                self.table.setItem(r, c, self._item(v))
        self._relabel()
        self._block = False

    def _item(self, v):
        it = QTableWidgetItem(("%.10g" % float(v)) if v != "" else "")
        it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        return it

    def rows(self):
        out = []
        for r in range(self.table.rowCount()):
            row = []
            for c in range(len(self.columns)):
                it = self.table.item(r, c)
                text = it.text().strip().replace(",", ".") if it is not None else ""
                try:
                    row.append(float(text) if text else 0.0)
                except ValueError:
                    raise ValueError("Row %d, column %s: '%s' is not a number"
                                     % (r + self.first_index, self.columns[c], text))
            out.append(row)
        return out

    def resize_rows(self, n, fill=0.0):
        """Keep the first n rows, padding with the last row or with fill."""
        current = self.rows()
        if len(current) == n:
            return
        if len(current) > n:
            current = current[:n]
        else:
            pad = current[-1] if current else [fill] * len(self.columns)
            current = current + [list(pad) for _ in range(n - len(current))]
        self.set_rows(current)
        self.changed.emit()

    def add_row(self):
        rows = self.rows()
        rows.append(list(rows[-1]) if rows else [0.0] * len(self.columns))
        self.set_rows(rows)
        self.changed.emit()

    def remove_rows(self):
        sel = sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True)
        if not sel:
            sel = [self.table.rowCount() - 1]
        rows = self.rows()
        for r in sel:
            if 0 <= r < len(rows) and len(rows) > 1:
                rows.pop(r)
        self.set_rows(rows)
        self.changed.emit()

    def fill_column(self):
        idx = self.table.selectedIndexes()
        if not idx:
            return
        r, c = idx[0].row(), idx[0].column()
        it = self.table.item(r, c)
        value = it.text() if it is not None else "0"
        self._block = True
        for rr in range(self.table.rowCount()):
            self.table.setItem(rr, c, self._item(float(value.replace(",", ".") or 0.0)))
        self._block = False
        self.changed.emit()


class VectorEdit(QWidget):
    """Row of spin boxes for a vector."""

    changed = Signal()

    def __init__(self, labels, values, step=0.1, decimals=6, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        self.spins = []
        for lab, v in zip(labels, values):
            l = QLabel(lab)
            l.setObjectName("muted")
            s = Spin(v, step=step, decimals=decimals)
            s.setMinimumWidth(58)
            s.valueChanged.connect(lambda *_: self.changed.emit())
            lay.addWidget(l)
            lay.addWidget(s)
            self.spins.append(s)

    def values(self):
        return [s.value() for s in self.spins]

    def set_values(self, values):
        for s, v in zip(self.spins, values):
            s.blockSignals(True)
            s.setValue(float(v))
            s.blockSignals(False)


def form(parent=None):
    f = QFormLayout()
    f.setRowWrapPolicy(QFormLayout.WrapLongRows)
    f.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
    f.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
    f.setHorizontalSpacing(10)
    f.setVerticalSpacing(6)
    f.setContentsMargins(4, 4, 4, 4)
    return f


def help_label(text):
    l = QLabel(text)
    l.setObjectName("muted")
    l.setWordWrap(True)
    return l
