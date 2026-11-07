"""Plane funiculars against their closed forms, and the thrust line analysis of arches."""
import numpy as np
import pytest

from funis import analysis
from funis.core import arch as A
from funis.core import plane as P
from funis.examples import EXAMPLES
from funis.model import Project

L = 10.0


def _problem(proj, actual=None, actions=(), extra=(5.0,), zB=0.0):
    s, idx = P.plane_grid(L, 2001, [a for a, _ in actions], extra)
    return P.LineProblem(s, proj, actual, actions, 0.0, zB), s, idx


def _const(c1, c3):
    def fn(x):
        if np.ndim(x) == 0:
            return np.array([c1, c3])
        return np.column_stack((np.full(len(x), c1), np.full(len(x), c3)))
    return fn


ZERO = _const(0.0, 0.0)


# ---------------------------------------------------------------- plane funiculars

def test_parabola_through_the_crown():
    lp, s, idx = _problem(_const(0.0, -1.0))
    C = lp.through_point(idx[0], 3.0)
    assert -C[0] == pytest.approx(L ** 2 / (8 * 3.0), rel=1e-12)
    assert C[1] == pytest.approx(-L / 2, rel=1e-12)
    z = lp.line(C)["z"]
    assert np.max(np.abs(z - P.parabola(s, C, -1.0))) < 1e-12


def test_catenary_through_the_crown():
    lp, s, idx = _problem(ZERO, _const(0.0, -1.0))
    C = lp.through_point(idx[0], 3.0)
    ln = lp.line(C)
    assert ln["z"][idx[0]] == pytest.approx(3.0, abs=1e-10)
    assert abs(ln["z"][-1]) < 1e-10
    assert np.max(np.abs(ln["z"] - P.catenary(s, C, 1.0))) < 1e-9
    a = -C[0]
    assert a * (np.cosh(L / (2 * a)) - 1.0) == pytest.approx(3.0, rel=1e-9)


def test_logarithmic_branch_of_appendix_b():
    lp, s, idx = _problem(_const(0.3, -1.0))
    C = lp.through_point(idx[0], 3.0)
    ln = lp.line(C)
    assert np.max(np.abs(ln["z"] - P.log_branch(s, C, 0.3, -1.0))) < 1e-10
    assert ln["F"][-1, 0] == pytest.approx(C[0] - 0.3 * L, rel=1e-12)


def test_inclined_catenary():
    lp, s, idx = _problem(ZERO, _const(0.2, -1.0))
    C = lp.through_point(idx[0], 3.0)
    z = lp.line(C)["z"]
    assert np.max(np.abs(z - P.inclined_catenary(s, C, 1.0, 0.2))) < 1e-9


def test_prescribed_thrust_reaches_the_second_support():
    lp, s, _ = _problem(ZERO, _const(0.0, -1.0), extra=(), zB=1.5)
    C = lp.through_end(6.0)
    ln = lp.line(C)
    assert C[0] == pytest.approx(-6.0)
    assert ln["z"][-1] == pytest.approx(1.5, abs=1e-10)
    assert np.max(np.abs(ln["z"] - P.catenary(s, C, 1.0))) < 1e-9


def test_funicular_polygon_of_point_loads():
    acts = [(2.5, np.array([0.0, -10.0])), (5.0, np.array([0.0, -20.0])), (7.5, np.array([0.0, -10.0]))]
    lp, s, idx = _problem(ZERO, None, acts)
    C = lp.through_point(idx[0], 3.0)
    # symmetric loads: the vertical reactions are half the load, H from the moment at the crown
    assert C[1] == pytest.approx(-20.0)
    assert -C[0] == pytest.approx((20.0 * 5.0 - 10.0 * 2.5) / 3.0)
    ln = lp.line(C)
    assert ln["F"][-1] == pytest.approx([C[0], 20.0])


def test_examples_of_the_plane_funicular():
    for name in ("Plane: catenary through a point", "Plane: parabola through a point",
                 "Plane: constant vertical and horizontal loads", "Plane: catenary under a pseudo-static action",
                 "Plane: catenary with a prescribed thrust and unequal supports"):
        res = analysis.run(EXAMPLES[name]())
        assert res.data["closed_form_error"] < 1e-9, name
        assert not res.messages


def test_a_line_that_turns_vertical_is_reported():
    p = EXAMPLES["Plane: constant vertical and horizontal loads"]()
    p.funicular.h = [-3.0, 0, 0, 0]  # F1 = -5 + 3x reaches zero at x = 5/3
    p.funicular.selection = "thrust"
    p.funicular.thrust = 5.0
    with pytest.raises(analysis.InputError):
        analysis.run(p)


# ---------------------------------------------------------------- arches

def _annulus(R, t, n, gamma=20.0):
    """Exact weights and centroids of the voussoirs of a semicircular arch (annular sectors)."""
    a = np.linspace(np.pi, 0.0, n + 1)
    ri, re = R - t / 2, R + t / 2
    d = np.abs(np.diff(a))
    mid = 0.5 * (a[1:] + a[:-1])
    area = 0.5 * d * (re ** 2 - ri ** 2)
    rc = (2.0 / 3.0) * (re ** 3 - ri ** 3) / (re ** 2 - ri ** 2) * np.sin(d / 2) / (d / 2)
    g = np.column_stack((R + rc * np.cos(mid), rc * np.sin(mid)))
    return gamma * area, g


def test_slices_of_a_semicircular_arch_are_annular_sectors():
    R, t, n = 5.0, 0.75, 40
    geo = A.build("circular", 2 * R, R, t, t, n)
    ld = A.slice_loads(geo, 20.0, 1.0)
    W, g = _annulus(R, t, n)
    assert -ld.ring[:, 1] == pytest.approx(W, rel=1e-6)
    assert np.max(np.abs(ld.ring_centroid - g)) < 1e-6
    assert geo.angle[0] == pytest.approx(-90.0) and geo.angle[-1] == pytest.approx(90.0)


def test_collapse_multiplier_equals_the_mechanism():
    R, t, n = 5.0, 0.75, 40
    geo = A.build("circular", 2 * R, R, t, t, n)
    ld = A.slice_loads(geo, 20.0, 1.0)
    P_, Q_ = A.combine(ld)
    pr = A.ThrustProblem(geo, P_, Q_, ld.inertia, ld.inertia_moment)
    y = pr.collapse()
    hinges = pr.hinges(pr.state(y))
    assert len(hinges) == 4
    assert [h[1] for h in hinges] == ["intrados", "extrados", "intrados", "extrados"]
    kin = A.mechanism_multiplier(hinges, P_, Q_, ld.inertia, ld.inertia_moment)
    assert kin == pytest.approx(y[3], rel=1e-9)
    # the same multiplier from the exact voussoir loads
    W, g = _annulus(R, t, n)
    Pe = np.column_stack((np.zeros(n), -W))
    Ve = np.column_stack((W, np.zeros(n)))
    pe = A.ThrustProblem(geo, Pe, P.cross2(g, Pe), Ve, P.cross2(g, Ve))
    assert pe.collapse()[3] == pytest.approx(y[3], rel=1e-6)
    assert y[3] == pytest.approx(0.1445067, abs=2e-7)
    # a different mechanism needs a larger multiplier (upper bound)
    moved = [hinges[0], (hinges[1][0] + 2, "extrados", geo.E[hinges[1][0] + 2])] + hinges[2:]
    assert A.mechanism_multiplier(moved, P_, Q_, ld.inertia, ld.inertia_moment) > y[3]


def test_minimum_thickness_of_the_semicircular_arch():
    res = analysis.run(EXAMPLES["Arch: semicircular arch of minimum thickness"]())
    assert res.data["minimum_thickness"] * 1.0 / 5.0 == pytest.approx(0.1075, abs=3e-4)
    hinges = res.data["minimum_thickness_hinges"]
    faces = [h[1] for h in hinges]
    assert faces == ["extrados", "intrados", "extrados", "intrados", "extrados"]
    assert abs(hinges[1][2]) == pytest.approx(54.5, abs=1.0)
    assert res.data["gsf"] > 1.0


def test_lines_of_minimum_and_maximum_thrust():
    geo = A.build("circular", 10.0, 5.0, 1.0, 1.0, 200)
    ld = A.slice_loads(geo, 20.0, 1.0)
    pr = A.ThrustProblem(geo, *A.combine(ld))
    lo, hi = pr.state(pr.thrust("min")), pr.state(pr.thrust("max"))
    assert lo["inside"] and hi["inside"]
    assert lo["H"][0] < hi["H"][0]
    assert np.allclose(lo["H"], lo["H"][0]) and np.allclose(lo["N"] <= 0, True)
    # symmetric arch and loads: symmetric lines
    assert lo["ecc"] == pytest.approx(lo["ecc"][::-1], abs=1e-7)
    # the minimum thrust line touches the extrados at the crown and the intrados at the haunches
    faces = [h[1] for h in pr.hinges(lo)]
    assert faces == ["intrados", "extrados", "intrados"]


def test_geometric_safety_factor_is_the_limit_of_feasibility():
    geo = A.build("circular", 10.0, 5.0, 1.0, 1.0, 120)
    ld = A.slice_loads(geo, 20.0, 1.0)
    pr = A.ThrustProblem(geo, *A.combine(ld))
    gsf, info = A.geometric_factor(pr)
    a = info["alpha"]
    pr.set_alpha(a * (1 + 1e-4))
    assert pr.feasible()
    pr.set_alpha(a * (1 - 1e-4))
    assert not pr.feasible()
    assert gsf == pytest.approx(1 / a)


def test_vertical_sections_cover_the_same_arch():
    for shape, f in (("circular", 2.5), ("parabolic", 3.0), ("elliptical", 3.0), ("pointed", 7.0)):
        a = A.slice_loads(A.build(shape, 10.0, f, 0.5, 0.7, 150, "normal"), 20.0, 1.0)
        b = A.slice_loads(A.build(shape, 10.0, f, 0.5, 0.7, 150, "vertical"), 20.0, 1.0)
        assert np.sum(a.ring_area) == pytest.approx(np.sum(b.ring_area), rel=1e-12), shape
        ga = np.sum(a.ring_area[:, None] * a.ring_centroid, axis=0)
        gb = np.sum(b.ring_area[:, None] * b.ring_centroid, axis=0)
        assert ga == pytest.approx(gb, rel=1e-10), shape


def test_area_of_the_ring_by_pappus():
    """Faces offset along the normal: the area is the thickness times the length of the centre line."""
    for shape, f in (("circular", 5.0), ("parabolic", 3.0), ("catenary", 4.0), ("elliptical", 3.0)):
        geo = A.build(shape, 10.0, f, 0.6, 0.6, 100)
        area = np.sum(A.slice_loads(geo, 1.0, 1.0).ring_area)
        length = np.sum(np.linalg.norm(np.diff(geo.centre, axis=0), axis=1))
        assert area == pytest.approx(0.6 * length, rel=1e-6), shape


def test_pointed_arch_is_symmetric():
    geo = A.build("pointed", 6.0, 4.5, 0.5, 0.5, 100)
    ld = A.slice_loads(geo, 20.0, 1.0)
    assert geo.mid[geo.crown, 0] == pytest.approx(3.0)
    assert geo.angle[geo.crown] == pytest.approx(0.0, abs=1e-9)
    pr = A.ThrustProblem(geo, *A.combine(ld))
    st = pr.state(pr.thrust("min"))
    assert st["ecc"] == pytest.approx(st["ecc"][::-1], abs=1e-7)


def test_fill_strip():
    chain = np.array([[0.0, 0.0], [1.0, 1.0], [2.0, 2.0]])
    A_, c = A._fill_strip(chain, 2.0)
    assert A_ == pytest.approx(2.0)
    assert c == pytest.approx([2.0 / 3.0, 2.0 - 2.0 / 3.0])
    A_, c = A._fill_strip(chain, 1.0)
    assert A_ == pytest.approx(0.5)


def test_examples_of_the_arch():
    for name, fn in EXAMPLES.items():
        if not name.startswith("Arch"):
            continue
        res = analysis.run(fn())
        if "kinematic" in res.data:
            assert res.data["kinematic"] == pytest.approx(res.data["collapse"], rel=1e-8), name
        values = [float(row[-1]) for row in res.tables["balance"].rows]
        assert max(values) < 1e-9, name
    res = analysis.run(EXAMPLES["Arch: catenary arch of finite thickness"]())
    assert res.data["three_points_inside"]
    ecc = np.abs(res.data["lines"]["points"]["ecc"])
    assert 1e-5 < np.max(ecc) < 0.01


def test_arch_input_errors():
    p = Project(task="arch")
    p.arch.shape = "pointed"
    p.arch.rise = 4.0
    with pytest.raises(analysis.InputError):
        analysis.run(p)
    p = Project(task="arch")
    p.arch.thickness = p.arch.thickness_springing = 12.0
    with pytest.raises(analysis.InputError):
        analysis.run(p)
    p = Project(task="arch")
    p.plane_points = [[30.0, 0.0, -10.0]]
    res = analysis.run(p)
    assert any("ignored" in m for m in res.messages)


def test_unsafe_arch_has_a_factor_below_one():
    p = Project(task="arch")
    p.arch.thickness = p.arch.thickness_springing = 0.4
    p.arch.variable = "none"
    res = analysis.run(p)
    assert res.data["gsf"] < 1.0
    assert res.messages and "not shown to be safe" in res.messages[0]


def _qt_available():
    """A QApplication can be created: probed in a subprocess, since a missing system library aborts Qt."""
    import os
    import subprocess
    import sys
    env = dict(os.environ, QT_QPA_PLATFORM=os.environ.get("QT_QPA_PLATFORM", "offscreen"))
    code = "from PySide6.QtWidgets import QApplication; QApplication([])"
    try:
        return subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, timeout=60).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def test_ui_round_trip_of_the_plane_examples():
    pytest.importorskip("PySide6.QtWidgets")
    if not _qt_available():
        pytest.skip("Qt cannot create an application here")
    from PySide6.QtWidgets import QApplication
    from funis.ui.panels import ModelPanel
    app = QApplication.instance() or QApplication([])
    panel = ModelPanel()
    for name, fn in EXAMPLES.items():
        p = fn()
        panel.from_project(p)
        q = panel.to_project()
        d0, d1 = p.to_dict(), q.to_dict()
        for key in ("task", "funicular", "arch", "plane_points"):
            assert d1[key] == d0[key], (name, key)
    assert app is not None


def test_exports_of_the_plane_tasks(tmp_path):
    import json

    from funis.io import dxf, project_file, report, tables
    for k, name in enumerate(("Arch: segmental arch with fill and a point load", "Plane: catenary through a point")):
        p = EXAMPLES[name]()
        res = analysis.run(p)
        tables.to_csv(res, tmp_path / ("r%d.csv" % k))
        tables.to_xlsx(res, tmp_path / ("r%d.xlsx" % k))
        tables.to_json(res, tmp_path / ("r%d.json" % k))
        dxf.write(res, tmp_path / ("r%d.dxf" % k))
        report.write(res, tmp_path / ("r%d.html" % k))
        data = json.loads((tmp_path / ("r%d.json" % k)).read_text())
        assert data["project"]["task"] == p.task
        assert (tmp_path / ("r%d.dxf" % k)).stat().st_size > 1000
        html = (tmp_path / ("r%d.html" % k)).read_text()
        assert "<html" in html[:50] and "<img" in html
        project_file.save(p, tmp_path / ("p%d.funis" % k))
        assert project_file.load(tmp_path / ("p%d.funis" % k)).to_dict() == p.to_dict()
    assert "joints" in data["tables"] or "stations" in data["tables"]
