"""Input panels: one section per part of the project."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QGroupBox, QLineEdit, QScrollArea, QStackedWidget,
                               QVBoxLayout, QWidget)

from ..model import (ArchSpec, ContactSpec, EllipseSpec, FormSpec, FunicularSpec, GeometrySpec, HelixSpec,
                     LoadSpec, NodeSpec, OutputSpec, PointAction, Project, ReactionFreeSpec, SupportSpec, TASKS)
from .widgets import ArrayTable, Combo, IntSpin, Spin, VectorEdit, form, help_label

COEFFS = ["a₀", "a₁", "a₂", "a₃"]


class Section(QGroupBox):
    changed = Signal()

    def __init__(self, title, parent=None):
        super().__init__(title, parent)
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(6, 4, 6, 6)
        self.body.setSpacing(6)

    def watch(self, *widgets):
        for w in widgets:
            if hasattr(w, "valueChanged"):
                w.valueChanged.connect(lambda *_: self.changed.emit())
            elif hasattr(w, "currentIndexChanged"):
                w.currentIndexChanged.connect(lambda *_: self.changed.emit())
            elif hasattr(w, "toggled"):
                w.toggled.connect(lambda *_: self.changed.emit())
            elif hasattr(w, "changed"):
                w.changed.connect(self.changed.emit)
            elif hasattr(w, "textChanged"):
                w.textChanged.connect(lambda *_: self.changed.emit())


def _poly_edit(values=(0.0, 0.0, 0.0, 0.0)):
    v = list(values) + [0.0] * 4
    return VectorEdit(COEFFS, v[:4], step=0.1, decimals=10)


class GeometrySection(Section):
    def __init__(self, parent=None):
        super().__init__("Geometry of the path", parent)
        self.kind = Combo([("helix", "Circular helix"), ("ellipse", "Elliptical helix"),
                           ("points", "Smooth path through points")])
        self.samples = IntSpin(2001, 101, 20001)
        f = form()
        f.addRow("Generator", self.kind)
        f.addRow("Samples along s", self.samples)
        self.body.addLayout(f)
        self.stack = QStackedWidget()
        self.body.addWidget(self.stack)
        # helix
        w = QWidget()
        f = form()
        self.radius = Spin(2.0, 0.001, 1e6, 0.1, 10, "m")
        self.pitch = Spin(-1.0, -1e6, 1e6, 0.1, 10, "m/rad")
        self.theta0 = Spin(0.0, -1e5, 1e5, 15.0, 10, "°")
        self.theta1 = Spin(360.0, -1e5, 1e5, 15.0, 10, "°")
        f.addRow("Radius R", self.radius)
        f.addRow("Pitch c (rise per radian)", self.pitch)
        f.addRow("Start angle θ₀", self.theta0)
        f.addRow("End angle θ₁", self.theta1)
        f.addRow(help_label("x* = (R cos θ, R sin θ, c (θ − θ₀)), s = R (θ − θ₀), grade f,s = c / R. "
                            "A negative pitch descends. θ increases, so the plan turns counterclockwise."))
        w.setLayout(f)
        self.stack.addWidget(w)
        # ellipse
        w = QWidget()
        f = form()
        self.ea = Spin(3.0, 0.001, 1e6, 0.1, 3, "m")
        self.eb = Spin(2.0, 0.001, 1e6, 0.1, 3, "m")
        self.emode = Combo([("angle", "f = c (θ − θ₀)"), ("arc", "f = k_s s (constant grade)")])
        self.epitch = Spin(-1.0, -1e6, 1e6, 0.1, 10)
        self.etheta0 = Spin(0.0, -1e5, 1e5, 15.0, 10, "°")
        self.etheta1 = Spin(360.0, -1e5, 1e5, 15.0, 10, "°")
        f.addRow("Semi-axis a (along x₁)", self.ea)
        f.addRow("Semi-axis b (along x₂)", self.eb)
        f.addRow("Elevation", self.emode)
        f.addRow("c [m/rad] or k_s [–]", self.epitch)
        f.addRow("Start angle θ₀", self.etheta0)
        f.addRow("End angle θ₁", self.etheta1)
        f.addRow(help_label("Plan (a cos θ, b sin θ), projected curvature ρ = ab / g³ with "
                            "g = √(a² sin²θ + b² cos²θ)."))
        w.setLayout(f)
        self.stack.addWidget(w)
        # points
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        self.points = ArrayTable(["x₁ [m]", "x₂ [m]", "x₃ [m]"], 4, "point", 0,
                                 help_text="A cubic spline through the points, re-parametrized by the "
                                           "projected length. The plan must not stop or turn back.")
        lay.addWidget(self.points)
        self.stack.addWidget(w)
        self.kind.currentIndexChanged.connect(self._switch)
        self.watch(self.kind, self.samples, self.radius, self.pitch, self.theta0, self.theta1, self.ea,
                   self.eb, self.emode, self.epitch, self.etheta0, self.etheta1, self.points)

    def _switch(self):
        self.stack.setCurrentIndex(self.kind.currentIndex())

    def to_spec(self):
        return GeometrySpec(kind=self.kind.key(),
                            helix=HelixSpec(self.radius.value(), self.pitch.value(), self.theta0.value(),
                                            self.theta1.value()),
                            ellipse=EllipseSpec(self.ea.value(), self.eb.value(), self.epitch.value(),
                                                self.emode.key(), self.etheta0.value(), self.etheta1.value()),
                            points=self.points.rows(), samples=self.samples.value())

    def from_spec(self, s):
        for w in (self.kind, self.samples, self.radius, self.pitch, self.theta0, self.theta1, self.ea, self.eb,
                  self.emode, self.epitch, self.etheta0, self.etheta1):
            w.blockSignals(True)
        self.kind.set_key(s.kind)
        self.samples.setValue(int(s.samples))
        h, e = s.helix, s.ellipse
        self.radius.setValue(h.radius)
        self.pitch.setValue(h.pitch)
        self.theta0.setValue(h.theta_start)
        self.theta1.setValue(h.theta_end)
        self.ea.setValue(e.a)
        self.eb.setValue(e.b)
        self.emode.set_key(e.mode)
        self.epitch.setValue(e.pitch)
        self.etheta0.setValue(e.theta_start)
        self.etheta1.setValue(e.theta_end)
        for w in (self.kind, self.samples, self.radius, self.pitch, self.theta0, self.theta1, self.ea, self.eb,
                  self.emode, self.epitch, self.etheta0, self.etheta1):
            w.blockSignals(False)
        self.points.set_rows(s.points)
        self._switch()


class FormSection(Section):
    def __init__(self, parent=None):
        super().__init__("Free curve", parent)
        f = form()
        self.length = Spin(5.0, 1e-3, 1e6, 0.5, 4, "m")
        self.samples = IntSpin(2001, 101, 20001)
        self.start = VectorEdit(["x₁", "x₂", "x₃"], [0.0, 0.0, 0.0], decimals=10)
        self.mode = Combo([("initial", "Prescribed initial force"), ("endpoint", "Prescribed second support")])
        self.force = VectorEdit(["C₁", "C₂", "C₃"], [-3.0, -4.0, -2.0], decimals=10)
        self.target = VectorEdit(["x₁", "x₂", "x₃"], [3.58655144, 3.46958475, -0.09396228], decimals=10)
        self.guess = VectorEdit(["C₁", "C₂", "C₃"], [-2.5, -3.5, -1.5], decimals=10)
        f.addRow("Projected length L", self.length)
        f.addRow("Samples along s", self.samples)
        f.addRow("Start x*(0) [m]", self.start)
        f.addRow("Task", self.mode)
        f.addRow("Initial force C [kN]", self.force)
        f.addRow("Second support x*(L) [m]", self.target)
        f.addRow("Estimate of C [kN]", self.guess)
        f.addRow(help_label("F = C − P(s) and x*,s = −F / Q, Q = |F_h| > 0. With a prescribed second support "
                            "the initial force is corrected by a damped Newton iteration from the estimate."))
        self.body.addLayout(f)
        self.mode.currentIndexChanged.connect(self._switch)
        self.watch(self.length, self.samples, self.start, self.mode, self.force, self.target, self.guess)
        self._switch()

    def _switch(self):
        end = self.mode.key() == "endpoint"
        self.force.setEnabled(not end)
        self.target.setEnabled(end)
        self.guess.setEnabled(end)

    def to_spec(self):
        return FormSpec(length=self.length.value(), start=self.start.values(), mode=self.mode.key(),
                        force=self.force.values(), target=self.target.values(), guess=self.guess.values(),
                        samples=self.samples.value())

    def from_spec(self, s):
        for w in (self.length, self.samples, self.mode):
            w.blockSignals(True)
        self.length.setValue(s.length)
        self.samples.setValue(int(s.samples))
        self.mode.set_key(s.mode)
        for w in (self.length, self.samples, self.mode):
            w.blockSignals(False)
        self.start.set_values(s.start)
        self.force.set_values(s.force)
        self.target.set_values(s.target)
        self.guess.set_values(s.guess)
        self._switch()


class LoadsSection(Section):
    def __init__(self, parent=None):
        super().__init__("Distributed loads (per metre of projected length)", parent)
        f = form()
        self.vmode = Combo([("density", "w(s) per projected metre"), ("actual", "w(s) per metre of actual length"),
                            ("table", "Table of w(s)")])
        self.w = _poly_edit((1.0,))
        self.wtable = ArrayTable(["s [m]", "w [kN/m]"], 2, "row", 1)
        f.addRow("Vertical load p₃ = −w", self.vmode)
        f.addRow("w = a₀ + a₁ s + a₂ s² + a₃ s³", self.w)
        self.body.addLayout(f)
        self.body.addWidget(self.wtable)
        f = form()
        self.hmode = Combo([("none", "None"), ("fixed", "h(s) in a fixed direction β"),
                            ("fixed_table", "Table of h(s) in a fixed direction β"),
                            ("pseudo", "Pseudo-static, h = γ |p₃| along β"),
                            ("components", "Components p₁(s), p₂(s)")])
        self.h = _poly_edit((1.0,))
        self.beta = Spin(0.0, -360.0, 360.0, 15.0, 4, "°")
        self.gamma = Spin(0.2, -100.0, 100.0, 0.05, 4)
        self.p1 = _poly_edit()
        self.p2 = _poly_edit()
        self.lam = Spin(1.0, -1e6, 1e6, 0.1, 4)
        f.addRow("Horizontal load", self.hmode)
        f.addRow("h = a₀ + a₁ s + a₂ s² + a₃ s³", self.h)
        self.body.addLayout(f)
        self.htable = ArrayTable(["s [m]", "h [kN/m]"], 2, "row", 1)
        self.body.addWidget(self.htable)
        f = form()
        f.addRow("Direction β (from e₁ toward e₂)", self.beta)
        f.addRow("Coefficient γ", self.gamma)
        f.addRow("p₁ = a₀ + a₁ s + …", self.p1)
        f.addRow("p₂ = a₀ + a₁ s + …", self.p2)
        f.addRow("Multiplier λ of the horizontal load", self.lam)
        self.forms = f
        self.body.addLayout(f)
        self.body.addWidget(help_label("Densities in kN per metre of projected length s. A table is "
                                       "interpolated linearly and held constant beyond its ends."))
        self.vmode.currentIndexChanged.connect(self._switch)
        self.hmode.currentIndexChanged.connect(self._switch)
        self.watch(self.vmode, self.w, self.wtable, self.hmode, self.h, self.htable, self.beta, self.gamma,
                   self.p1, self.p2, self.lam)
        self._switch()

    def _switch(self):
        v, h = self.vmode.key(), self.hmode.key()
        self.w.setEnabled(v != "table")
        self.wtable.setVisible(v == "table")
        self.h.setEnabled(h == "fixed")
        self.htable.setVisible(h == "fixed_table")
        self.beta.setEnabled(h in ("fixed", "fixed_table", "pseudo"))
        self.gamma.setEnabled(h == "pseudo")
        self.p1.setEnabled(h == "components")
        self.p2.setEnabled(h == "components")
        self.lam.setEnabled(h != "none")

    def to_spec(self):
        return LoadSpec(vertical_mode=self.vmode.key(), w=self.w.values(), w_table=self.wtable.rows(),
                        horizontal_mode=self.hmode.key(), h=self.h.values(), h_table=self.htable.rows(),
                        beta=self.beta.value(), gamma=self.gamma.value(), p1=self.p1.values(),
                        p2=self.p2.values(), multiplier=self.lam.value())

    def from_spec(self, s):
        for w in (self.vmode, self.hmode, self.beta, self.gamma, self.lam):
            w.blockSignals(True)
        self.vmode.set_key(s.vertical_mode)
        self.hmode.set_key(s.horizontal_mode)
        self.beta.setValue(s.beta)
        self.gamma.setValue(s.gamma)
        self.lam.setValue(s.multiplier)
        for w in (self.vmode, self.hmode, self.beta, self.gamma, self.lam):
            w.blockSignals(False)
        self.w.set_values((list(s.w) + [0.0] * 4)[:4])
        self.h.set_values((list(s.h) + [0.0] * 4)[:4])
        self.p1.set_values((list(s.p1) + [0.0] * 4)[:4])
        self.p2.set_values((list(s.p2) + [0.0] * 4)[:4])
        self.wtable.set_rows(s.w_table)
        self.htable.set_rows(s.h_table)
        self._switch()


class PointActionsSection(Section):
    def __init__(self, parent=None):
        super().__init__("Point actions", parent)
        self.table = ArrayTable(["s [m]", "G₁ [kN]", "G₂ [kN]", "G₃ [kN]"], 0, "G", 1,
                                help_text="Concentrated forces at the projected abscissa s. On a supported "
                                          "path they take a horizontal point reaction, on a free curve the "
                                          "force jumps by −G.")
        self.body.addWidget(self.table)
        self.watch(self.table)

    def to_list(self):
        return [PointAction(*r[:4]) for r in self.table.rows()]

    def from_list(self, actions):
        self.table.set_rows([[a.s, a.G1, a.G2, a.G3] for a in actions])


class SupportSection(Section):
    def __init__(self, parent=None):
        super().__init__("Support of the line", parent)
        f = form()
        self.preload = Spin(8.0, -1e6, 1e6, 0.5, 4, "kN")
        self.wall = Combo([("right", "On the right of the direction of travel"),
                           ("left", "On the left of the direction of travel")])
        f.addRow("Preload T = −S(0)", self.preload)
        f.addRow("Wall", self.wall)
        f.addRow(help_label("Compressive end thrust supplied at the start of the path. The lateral support "
                            "supplies horizontal reactions only (r₃ = 0). r_ν = r_n for a wall on the right, "
                            "−r_n on the left."))
        self.body.addLayout(f)
        self.watch(self.preload, self.wall)

    def to_spec(self):
        return SupportSpec(preload=self.preload.value(), wall=self.wall.key())

    def from_spec(self, s):
        for w in (self.preload, self.wall):
            w.blockSignals(True)
        self.preload.setValue(s.preload)
        self.wall.set_key(s.wall)
        for w in (self.preload, self.wall):
            w.blockSignals(False)


class ContactSection(Section):
    def __init__(self, parent=None):
        super().__init__("Contact with the wall", parent)
        f = form()
        self.enabled = QCheckBox("Check the contact cone")
        self.mu = Spin(0.6, 0.0, 100.0, 0.05, 4)
        self.strip = Spin(0.8, 0.0, 1e6, 0.05, 4, "m")
        self.delta = Spin(0.0, 0.0, 1e6, 0.05, 4, "m")
        self.Tmax = Spin(0.0, 0.0, 1e9, 1.0, 4, "kN")
        self.lmax = Spin(0.0, 0.0, 1e9, 0.5, 4)
        f.addRow(self.enabled)
        f.addRow("Friction coefficient μ", self.mu)
        f.addRow("Width of the centred strip L_sw", self.strip)
        f.addRow("Distance of the wall δ (0: no strip)", self.delta)
        f.addRow("Largest T of the diagrams (0: auto)", self.Tmax)
        f.addRow("Largest λ of the diagrams (0: auto)", self.lmax)
        f.addRow(help_label("r_ν ≥ 0 and |r_t| ≤ η r_ν with η = min(μ, φ), φ = L_sw / (2δ)."))
        self.body.addLayout(f)
        self.enabled.toggled.connect(self._switch)
        self.watch(self.enabled, self.mu, self.strip, self.delta, self.Tmax, self.lmax)

    def _switch(self):
        on = self.enabled.isChecked()
        for w in (self.mu, self.strip, self.delta, self.Tmax, self.lmax):
            w.setEnabled(on)

    def to_spec(self):
        return ContactSpec(enabled=self.enabled.isChecked(), mu=self.mu.value(), strip=self.strip.value(),
                           delta=self.delta.value(), T_max=self.Tmax.value(), lam_max=self.lmax.value())

    def from_spec(self, s):
        ws = (self.enabled, self.mu, self.strip, self.delta, self.Tmax, self.lmax)
        for w in ws:
            w.blockSignals(True)
        self.enabled.setChecked(bool(s.enabled))
        self.mu.setValue(s.mu)
        self.strip.setValue(s.strip)
        self.delta.setValue(s.delta)
        self.Tmax.setValue(s.T_max)
        self.lmax.setValue(s.lam_max)
        for w in ws:
            w.blockSignals(False)
        self._switch()


class ReactionFreeSection(Section):
    def __init__(self, parent=None):
        super().__init__("Path without reactions", parent)
        f = form()
        self.mode = Combo([("check", "Check the loads below"),
                           ("fixed_plane", "Loads in a fixed vertical plane"),
                           ("thrust", "Loads for a prescribed thrust S(s)")])
        self.B = Spin(3.0, -1e6, 1e6, 0.5, 4, "kN")
        self.beta = Spin(0.0, -360.0, 360.0, 15.0, 4, "°")
        self.thrust = _poly_edit((-8.0, -2.0))
        f.addRow("Task", self.mode)
        f.addRow("Conserved component B = F · m", self.B)
        f.addRow("Plane direction β", self.beta)
        f.addRow("S = a₀ + a₁ s + a₂ s² + a₃ s³ [kN]", self.thrust)
        f.addRow(help_label("Check: least-squares initial force of F = C − P parallel to the tangent. Fixed "
                            "plane: loads in the plane of e₃ and d(β) conserve F · m = B, m = e₃ × d, so "
                            "S = B / (t · m). Prescribed thrust: p = −(S u),s."))
        self.body.addLayout(f)
        self.mode.currentIndexChanged.connect(self._switch)
        self.watch(self.mode, self.B, self.beta, self.thrust)
        self._switch()

    def _switch(self):
        m = self.mode.key()
        self.B.setEnabled(m == "fixed_plane")
        self.beta.setEnabled(m == "fixed_plane")
        self.thrust.setEnabled(m == "thrust")

    def to_spec(self):
        return ReactionFreeSpec(mode=self.mode.key(), B=self.B.value(), beta=self.beta.value(),
                                thrust=self.thrust.values())

    def from_spec(self, s):
        for w in (self.mode, self.B, self.beta):
            w.blockSignals(True)
        self.mode.set_key(s.mode)
        self.B.setValue(s.B)
        self.beta.setValue(s.beta)
        for w in (self.mode, self.B, self.beta):
            w.blockSignals(False)
        self.thrust.set_values((list(s.thrust) + [0.0] * 4)[:4])
        self._switch()


class NodeSection(Section):
    def __init__(self, parent=None):
        super().__init__("Node", parent)
        f = form()
        self.Fm = VectorEdit(["F₁", "F₂", "F₃"], [-3.0, -2.0, -1.0], decimals=10)
        self.G = VectorEdit(["G₁", "G₂", "G₃"], [2.0, 0.0, -1.0], decimals=10)
        self.R = VectorEdit(["R₁", "R₂", "R₃"], [0.0, 0.0, 0.0], decimals=10)
        self.segment = Spin(2.0, 1e-3, 1e6, 0.5, 4, "m")
        f.addRow("Force before the node F⁻ [kN]", self.Fm)
        f.addRow("Point force G [kN]", self.G)
        f.addRow("Point reaction R [kN]", self.R)
        f.addRow("Length of the drawn members", self.segment)
        f.addRow(help_label("F⁺ = F⁻ − G − R, members along T = −F / |F| (compression)."))
        self.body.addLayout(f)
        self.watch(self.Fm, self.G, self.R, self.segment)

    def to_spec(self):
        return NodeSpec(force_before=self.Fm.values(), load=self.G.values(), reaction=self.R.values(),
                        segment=self.segment.value())

    def from_spec(self, s):
        self.Fm.set_values(s.force_before)
        self.G.set_values(s.load)
        self.R.set_values(s.reaction)
        self.segment.blockSignals(True)
        self.segment.setValue(s.segment)
        self.segment.blockSignals(False)


class OutputSection(Section):
    def __init__(self, parent=None):
        super().__init__("Output", parent)
        f = form()
        self.abscissa = Combo([("theta", "Angle θ, when the path has one"), ("s", "Projected length s")])
        self.stations = IntSpin(41, 2, 2001)
        f.addRow("Abscissa of the graphs", self.abscissa)
        f.addRow("Stations in the tables", self.stations)
        self.body.addLayout(f)
        self.watch(self.abscissa, self.stations)

    def to_spec(self):
        return OutputSpec(abscissa=self.abscissa.key(), stations=self.stations.value())

    def from_spec(self, s):
        for w in (self.abscissa, self.stations):
            w.blockSignals(True)
        self.abscissa.set_key(s.abscissa)
        self.stations.setValue(int(s.stations))
        for w in (self.abscissa, self.stations):
            w.blockSignals(False)


class FunicularSection(Section):
    def __init__(self, parent=None):
        super().__init__("Plane funicular", parent)
        f = form()
        self.span = Spin(10.0, 1e-3, 1e6, 0.5, 4, "m")
        self.zB = Spin(0.0, -1e6, 1e6, 0.1, 10, "m")
        self.samples = IntSpin(2001, 101, 20001)
        self.selection = Combo([("point", "Through a point and the second support"),
                                ("thrust", "Prescribed thrust and the second support"),
                                ("initial", "Prescribed initial force")])
        self.through = VectorEdit(["x_c", "z_c"], [5.0, 3.0], decimals=10)
        self.thrust = Spin(4.0, 1e-9, 1e9, 0.5, 10, "kN")
        self.force = VectorEdit(["F₁", "F₃"], [-4.0, -2.5], decimals=10)
        f.addRow("Span L (supports A = (0, 0), B = (L, z_B))", self.span)
        f.addRow("Height z_B of the second support", self.zB)
        f.addRow("Samples along x", self.samples)
        f.addRow("Line", self.selection)
        f.addRow("Point (x_c, z_c) [m]", self.through)
        f.addRow("Thrust H_A = −F₁(0)", self.thrust)
        f.addRow("Initial force F(0) [kN]", self.force)
        f.addRow(help_label("F' + p = 0 and f' = F₃ / F₁ in the vertical plane of e₁ and e₃, with x the "
                            "projected length. Compression: F₁ < 0. A weight per metre of actual length gives "
                            "the catenary, a load per metre of x the parabola."))
        self.body.addLayout(f)
        self.selection.currentIndexChanged.connect(self._switch)
        self.watch(self.span, self.zB, self.samples, self.selection, self.through, self.thrust, self.force)
        self._switch()

    def _switch(self):
        m = self.selection.key()
        self.through.setEnabled(m == "point")
        self.thrust.setEnabled(m == "thrust")
        self.force.setEnabled(m == "initial")
        self.zB.setEnabled(m != "initial")

    def apply(self, spec):
        spec.span, spec.end_height, spec.samples = self.span.value(), self.zB.value(), self.samples.value()
        spec.selection, spec.through = self.selection.key(), self.through.values()
        spec.thrust, spec.force = self.thrust.value(), self.force.values()

    def from_spec(self, s):
        ws = (self.span, self.zB, self.samples, self.selection, self.thrust)
        for w in ws:
            w.blockSignals(True)
        self.span.setValue(s.span)
        self.zB.setValue(s.end_height)
        self.samples.setValue(int(s.samples))
        self.selection.set_key(s.selection)
        self.thrust.setValue(s.thrust)
        for w in ws:
            w.blockSignals(False)
        self.through.set_values(s.through)
        self.force.set_values(s.force)
        self._switch()


class PlaneLoadsSection(Section):
    def __init__(self, parent=None):
        super().__init__("Loads on the line", parent)
        f = form()
        self.vmode = Combo([("actual", "w(x) per metre of actual length (catenary)"),
                            ("density", "w(x) per metre of x (parabola)"), ("table", "Table of w(x) per metre of x")])
        self.w = _poly_edit((1.0,))
        self.wtable = ArrayTable(["x [m]", "w [kN/m]"], 2, "row", 1)
        f.addRow("Vertical load p₃ = −w", self.vmode)
        f.addRow("w = a₀ + a₁ x + a₂ x² + a₃ x³", self.w)
        self.body.addLayout(f)
        self.body.addWidget(self.wtable)
        f = form()
        self.hmode = Combo([("none", "None"), ("density", "p₁ = h(x) per metre of x"),
                            ("proportional", "Pseudo-static, p₁ = γ w")])
        self.h = _poly_edit((0.2,))
        self.gamma = Spin(0.1, -100.0, 100.0, 0.05, 6)
        f.addRow("Horizontal load (along e₁)", self.hmode)
        f.addRow("h = a₀ + a₁ x + a₂ x² + a₃ x³", self.h)
        f.addRow("Coefficient γ", self.gamma)
        f.addRow(help_label("Densities in kN/m. The pseudo-static load has the measure of w: per metre of "
                            "actual length for a catenary, so that the total load keeps a fixed direction."))
        self.body.addLayout(f)
        self.vmode.currentIndexChanged.connect(self._switch)
        self.hmode.currentIndexChanged.connect(self._switch)
        self.watch(self.vmode, self.w, self.wtable, self.hmode, self.h, self.gamma)
        self._switch()

    def _switch(self):
        v, h = self.vmode.key(), self.hmode.key()
        self.w.setEnabled(v != "table")
        self.wtable.setVisible(v == "table")
        self.h.setEnabled(h == "density")
        self.gamma.setEnabled(h == "proportional")

    def apply(self, spec):
        spec.vertical_mode, spec.w, spec.w_table = self.vmode.key(), self.w.values(), self.wtable.rows()
        spec.horizontal_mode, spec.h, spec.gamma = self.hmode.key(), self.h.values(), self.gamma.value()

    def from_spec(self, s):
        for w in (self.vmode, self.hmode, self.gamma):
            w.blockSignals(True)
        self.vmode.set_key(s.vertical_mode)
        self.hmode.set_key(s.horizontal_mode)
        self.gamma.setValue(s.gamma)
        for w in (self.vmode, self.hmode, self.gamma):
            w.blockSignals(False)
        self.w.set_values((list(s.w) + [0.0] * 4)[:4])
        self.h.set_values((list(s.h) + [0.0] * 4)[:4])
        self.wtable.set_rows(s.w_table)
        self._switch()


class PlanePointsSection(Section):
    def __init__(self, parent=None):
        super().__init__("Point loads", parent)
        self.table = ArrayTable(["x [m]", "G₁ [kN]", "G₃ [kN]"], 0, "G", 1,
                                help_text="Concentrated forces at the abscissa x: on the line of a funicular, "
                                          "on the extrados of an arch. G₃ < 0 acts downward.")
        self.body.addWidget(self.table)
        self.watch(self.table)

    def to_list(self):
        return [list(r[:3]) for r in self.table.rows()]

    def from_list(self, rows):
        self.table.set_rows([list(r)[:3] for r in rows])


class ArchSection(Section):
    def __init__(self, parent=None):
        super().__init__("Arch", parent)
        f = form()
        self.shape = Combo([("circular", "Circular (segmental or semicircular)"), ("pointed", "Pointed (two-centred)"),
                            ("elliptical", "Elliptical"), ("parabolic", "Parabolic"), ("catenary", "Catenary"),
                            ("points", "Centre line through points")])
        self.span = Spin(10.0, 1e-3, 1e6, 0.5, 6, "m")
        self.rise = Spin(5.0, 1e-3, 1e6, 0.25, 6, "m")
        self.tc = Spin(1.0, 1e-4, 1e6, 0.05, 6, "m")
        self.ts = Spin(1.0, 1e-4, 1e6, 0.05, 6, "m")
        self.depth = Spin(1.0, 1e-4, 1e6, 0.1, 6, "m")
        self.gamma = Spin(20.0, 0.0, 1e6, 1.0, 6, "kN/m³")
        f.addRow("Shape of the centre line", self.shape)
        f.addRow("Span L between the centres of the springings", self.span)
        f.addRow("Rise f of the centre line", self.rise)
        self.body.addLayout(f)
        self.points = ArrayTable(["x [m]", "z [m]"], 5, "point", 0,
                                 help_text="A cubic spline through the points of the centre line, from the first "
                                           "springing to the second.")
        self.body.addWidget(self.points)
        f = form()
        f.addRow("Thickness at the crown t", self.tc)
        f.addRow("Thickness at the springings", self.ts)
        f.addRow("Depth b (normal to the plane)", self.depth)
        f.addRow("Unit weight of the masonry", self.gamma)
        f.addRow(help_label("The faces are offset from the centre line along its normal; the thickness varies "
                            "linearly along the centre line from the crown to the springings."))
        self.body.addLayout(f)
        self.shape.currentIndexChanged.connect(self._switch)
        self.watch(self.shape, self.span, self.rise, self.points, self.tc, self.ts, self.depth, self.gamma)
        self._switch()

    def _switch(self):
        pts = self.shape.key() == "points"
        self.points.setVisible(pts)
        self.span.setEnabled(not pts)
        self.rise.setEnabled(not pts)

    def apply(self, spec):
        spec.shape, spec.span, spec.rise, spec.points = self.shape.key(), self.span.value(), self.rise.value(), \
            self.points.rows()
        spec.thickness, spec.thickness_springing = self.tc.value(), self.ts.value()
        spec.depth, spec.unit_weight = self.depth.value(), self.gamma.value()

    def from_spec(self, s):
        ws = (self.shape, self.span, self.rise, self.tc, self.ts, self.depth, self.gamma)
        for w in ws:
            w.blockSignals(True)
        self.shape.set_key(s.shape)
        self.span.setValue(s.span)
        self.rise.setValue(s.rise)
        self.tc.setValue(s.thickness)
        self.ts.setValue(s.thickness_springing)
        self.depth.setValue(s.depth)
        self.gamma.setValue(s.unit_weight)
        for w in ws:
            w.blockSignals(False)
        self.points.set_rows(s.points)
        self._switch()


class FillSection(Section):
    def __init__(self, parent=None):
        super().__init__("Fill and surcharge", parent)
        f = form()
        self.enabled = QCheckBox("Fill above the extrados")
        self.level = Spin(6.0, -1e6, 1e6, 0.25, 6, "m")
        self.weight = Spin(18.0, 0.0, 1e6, 1.0, 6, "kN/m³")
        self.inertia = QCheckBox("Horizontal action also on the fill")
        self.surcharge = Spin(0.0, 0.0, 1e9, 1.0, 6, "kN/m²")
        f.addRow(self.enabled)
        f.addRow("Level x₃ of the fill", self.level)
        f.addRow("Unit weight of the fill", self.weight)
        f.addRow(self.inertia)
        f.addRow("Uniform surcharge q", self.surcharge)
        f.addRow(help_label("The fill and the surcharge load the extrados vertically, column by column, and "
                            "have no strength of their own."))
        self.body.addLayout(f)
        self.enabled.toggled.connect(self._switch)
        self.watch(self.enabled, self.level, self.weight, self.inertia, self.surcharge)
        self._switch()

    def _switch(self):
        on = self.enabled.isChecked()
        for w in (self.level, self.weight, self.inertia):
            w.setEnabled(on)

    def apply(self, spec):
        spec.fill, spec.fill_level, spec.fill_weight = self.enabled.isChecked(), self.level.value(), self.weight.value()
        spec.fill_inertia, spec.surcharge = self.inertia.isChecked(), self.surcharge.value()

    def from_spec(self, s):
        ws = (self.enabled, self.level, self.weight, self.inertia, self.surcharge)
        for w in ws:
            w.blockSignals(True)
        self.enabled.setChecked(bool(s.fill))
        self.level.setValue(s.fill_level)
        self.weight.setValue(s.fill_weight)
        self.inertia.setChecked(bool(s.fill_inertia))
        self.surcharge.setValue(s.surcharge)
        for w in ws:
            w.blockSignals(False)
        self._switch()


class AssessmentSection(Section):
    def __init__(self, parent=None):
        super().__init__("Thrust line assessment", parent)
        f = form()
        self.joints = Combo([("normal", "Normal to the centre line (voussoir joints)"),
                             ("vertical", "Vertical sections (projected abscissa)")])
        self.count = IntSpin(200, 4, 2000)
        self.lam = Spin(0.0, 0.0, 1e3, 0.05, 6)
        self.direction = Combo([("right", "Along +e₁"), ("left", "Along −e₁")])
        self.variable = Combo([("horizontal", "The horizontal action"), ("points", "The point loads"),
                               ("none", "None")])
        self.friction = Spin(0.0, 0.0, 100.0, 0.05, 6)
        self.line = Combo([("min", "Minimum thrust"), ("max", "Maximum thrust"),
                           ("points", "Through three points")])
        self.ecc = VectorEdit(["A", "crown", "B"], [0.0, 0.0, 0.0], step=0.05, decimals=6)
        self.thin = QCheckBox("Minimum thickness, with the loads recomputed")
        f.addRow("Joints", self.joints)
        f.addRow("Number of slices", self.count)
        f.addRow("Horizontal action λ (of the weights)", self.lam)
        f.addRow("Direction of the horizontal action", self.direction)
        f.addRow("Collapse multiplier of", self.variable)
        f.addRow("Friction coefficient (0: no sliding)", self.friction)
        f.addRow("Line in the tables", self.line)
        f.addRow("e / t of the three points", self.ecc)
        f.addRow(self.thin)
        f.addRow(help_label("A line is admissible where its centre of pressure lies on every joint between "
                            "the intrados and the extrados (Heyman's safe theorem). e / t from −1/2 (intrados) "
                            "to 1/2 (extrados), at the springing A, the crown and the springing B."))
        self.body.addLayout(f)
        self.line.currentIndexChanged.connect(self._switch)
        self.watch(self.joints, self.count, self.lam, self.direction, self.variable, self.friction, self.line,
                   self.ecc, self.thin)
        self._switch()

    def _switch(self):
        self.ecc.setEnabled(self.line.key() == "points")

    def apply(self, spec):
        spec.joints, spec.count, spec.lam = self.joints.key(), self.count.value(), self.lam.value()
        spec.direction, spec.variable, spec.friction = self.direction.key(), self.variable.key(), self.friction.value()
        spec.line, spec.eccentricities, spec.minimum_thickness = self.line.key(), self.ecc.values(), self.thin.isChecked()

    def from_spec(self, s):
        ws = (self.joints, self.count, self.lam, self.direction, self.variable, self.friction, self.line, self.thin)
        for w in ws:
            w.blockSignals(True)
        self.joints.set_key(s.joints)
        self.count.setValue(int(s.count))
        self.lam.setValue(s.lam)
        self.direction.set_key(s.direction)
        self.variable.set_key(s.variable)
        self.friction.setValue(s.friction)
        self.line.set_key(s.line)
        self.thin.setChecked(bool(s.minimum_thickness))
        for w in ws:
            w.blockSignals(False)
        self.ecc.set_values((list(s.eccentricities) + [0.0] * 3)[:3])
        self._switch()


VISIBLE = {
    "supported": ("geometry", "loads", "points", "support", "contact", "output"),
    "reaction_free": ("geometry", "reaction_free", "loads", "points", "output"),
    "form_finding": ("form", "loads", "points", "output"),
    "node": ("node",),
    "plane_funicular": ("funicular", "plane_loads", "plane_points", "output"),
    "arch": ("arch", "fill", "assessment", "plane_points", "output"),
}
ORDER = ("geometry", "form", "reaction_free", "funicular", "arch", "fill", "assessment", "loads", "plane_loads",
         "points", "plane_points", "support", "contact", "node", "output")


class ModelPanel(QWidget):
    """All the input of a project."""

    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(8)
        head = QGroupBox("Problem")
        f = form()
        self.name = QLineEdit("Untitled")
        self.task = Combo(list(TASKS.items()))
        f.addRow("Name", self.name)
        f.addRow("Task", self.task)
        head.setLayout(f)
        outer.addWidget(head)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        inner = QWidget()
        self.inner = QVBoxLayout(inner)
        self.inner.setContentsMargins(0, 0, 4, 0)
        self.inner.setSpacing(8)
        self.sections = {"geometry": GeometrySection(), "form": FormSection(),
                         "reaction_free": ReactionFreeSection(), "loads": LoadsSection(),
                         "points": PointActionsSection(), "support": SupportSection(),
                         "contact": ContactSection(), "node": NodeSection(), "output": OutputSection(),
                         "funicular": FunicularSection(), "plane_loads": PlaneLoadsSection(),
                         "plane_points": PlanePointsSection(), "arch": ArchSection(), "fill": FillSection(),
                         "assessment": AssessmentSection()}
        for key in ORDER:
            self.inner.addWidget(self.sections[key])
            self.sections[key].changed.connect(self.changed.emit)
        self.inner.addStretch(1)
        scroll.setWidget(inner)
        outer.addWidget(scroll, 1)
        self.task.currentIndexChanged.connect(self._update_visibility)
        self.sections["reaction_free"].mode.currentIndexChanged.connect(lambda *_: self._update_visibility())
        self.name.textChanged.connect(lambda *_: self.changed.emit())
        self._loading = False
        self._update_visibility()

    def _update_visibility(self):
        task = self.task.key()
        keys = VISIBLE.get(task, ())
        for key, sec in self.sections.items():
            sec.setVisible(key in keys)
        if task == "reaction_free":
            check = self.sections["reaction_free"].mode.key() == "check"
            self.sections["loads"].setVisible(check)
            self.sections["points"].setVisible(check)
        if not self._loading:
            self.changed.emit()

    _notes = ""

    def to_project(self):
        s = self.sections
        funicular, arch = FunicularSpec(), ArchSpec()
        s["funicular"].apply(funicular)
        s["plane_loads"].apply(funicular)
        for key in ("arch", "fill", "assessment"):
            s[key].apply(arch)
        return Project(name=self.name.text().strip() or "Untitled", task=self.task.key(),
                       geometry=s["geometry"].to_spec(), loads=s["loads"].to_spec(),
                       point_actions=s["points"].to_list(), support=s["support"].to_spec(),
                       contact=s["contact"].to_spec(), reaction_free=s["reaction_free"].to_spec(),
                       form=s["form"].to_spec(), node=s["node"].to_spec(), funicular=funicular, arch=arch,
                       plane_points=s["plane_points"].to_list(), output=s["output"].to_spec(),
                       notes=self._notes)

    def from_project(self, p):
        self._loading = True
        self.blockSignals(True)
        try:
            s = self.sections
            self.name.setText(p.name)
            self._notes = p.notes
            self.task.blockSignals(True)
            self.task.set_key(p.task)
            self.task.blockSignals(False)
            s["geometry"].from_spec(p.geometry)
            s["form"].from_spec(p.form)
            s["reaction_free"].from_spec(p.reaction_free)
            s["loads"].from_spec(p.loads)
            s["points"].from_list(p.point_actions)
            s["support"].from_spec(p.support)
            s["contact"].from_spec(p.contact)
            s["node"].from_spec(p.node)
            s["funicular"].from_spec(p.funicular)
            s["plane_loads"].from_spec(p.funicular)
            s["plane_points"].from_list(p.plane_points)
            for key in ("arch", "fill", "assessment"):
                s[key].from_spec(p.arch)
            s["output"].from_spec(p.output)
            self._update_visibility()
        finally:
            self.blockSignals(False)
            self._loading = False
