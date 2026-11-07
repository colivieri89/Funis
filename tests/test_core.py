"""The solvers reproduce the closed forms and the values reported in the article."""
import numpy as np
import pytest

from funis.core import geometry
from funis.core.contact import (ContactProblem, critical_horizontal_circle, friction_strip,
                                minimum_preload_circle)
from funis.core.funicular import (compatibility, constant_load_curve, curvature_torsion, endpoint_jacobian,
                                  fixed_plane, free_curve, loads_for_thrust, node, plane_distance,
                                  self_weight_curve, solve_endpoint)
from funis.core.grid import derivative, integral, piecewise_grid
from funis.core.supported import preload_to_C3, supported

F0 = np.array([-3.0, -4.0, -2.0])
TARGET_C = np.array([3.58655144, 3.46958475, -0.09396228])


def circle(n=2001, nodes=()):
    return geometry.helix(2.0, -1.0, 0.0, 2 * np.pi, n, nodes)


def loads(path, h=0.0, w=1.0):
    n = len(path.s)
    return np.column_stack((np.full(n, h), np.zeros(n), np.full(n, -w)))


# ------------------------------------------------------------------ geometry

def test_helix_frame_and_grade():
    p = circle()
    assert p.L == pytest.approx(4 * np.pi)
    assert np.allclose(p.fs, -0.5) and np.allclose(p.rho, 0.5)
    assert np.allclose(np.cross(geometry.E3, p.t), p.n)
    assert np.allclose(derivative(p.xyz, p.s), p.u, atol=1e-6)


def test_ellipse_curvature_and_length():
    e = geometry.ellipse(3.0, 2.0, -1.0, 0.0, 2 * np.pi, 4001)
    assert e.L == pytest.approx(15.86544, abs=1e-4)
    th = e.theta
    g = np.sqrt(9 * np.sin(th) ** 2 + 4 * np.cos(th) ** 2)
    assert np.allclose(e.rho, 6 / g ** 3)
    assert np.allclose(derivative(e.xyz, e.s), e.u, atol=1e-5)
    arc = geometry.ellipse(3.0, 2.0, -2 * np.pi / e.L, 0.0, 2 * np.pi, 4001, mode="arc")
    assert arc.xyz[-1, 2] == pytest.approx(-2 * np.pi)
    assert np.allclose(arc.rho, e.rho)


def test_spline_path_reproduces_a_helix():
    th = np.linspace(0, np.pi, 41)
    pts = np.column_stack((2 * np.cos(th), 2 * np.sin(th), -th))
    p = geometry.spline_path(pts, 2001)
    assert p.L == pytest.approx(2 * np.pi, rel=1e-5)
    assert np.allclose(p.fs[50:-50], -0.5, atol=1e-4)
    assert np.allclose(p.rho[50:-50], 0.5, atol=1e-3)


# ------------------------------------------------------------------ supported path

@pytest.mark.parametrize("h", [0.0, 1.0, 2.0, 4.0])
def test_supported_benchmark(h):
    """S = -8 - 4 theta, r_t = 2 + h sin theta, r_n = 4 + 2 theta + h cos theta."""
    p = circle()
    st = supported(p, loads(p, h), preload_to_C3(p, 8.0))
    th = p.theta
    assert np.allclose(st["S"], -8 - 4 * th)
    assert np.allclose(st["rt"], 2 + h * np.sin(th))
    assert np.allclose(st["rn"], 4 + 2 * th + h * np.cos(th))
    assert st["N"][0] == pytest.approx(-8.94427, abs=1e-5)
    assert st["N"][-1] == pytest.approx(-37.04353, abs=1e-5)
    assert st["balance"]["force_relative"] < 1e-10
    assert st["balance"]["moment_relative"] < 1e-10


def test_horizontal_load_shifts_the_reaction_only():
    p = circle()
    a = supported(p, loads(p, 0.0), preload_to_C3(p, 8.0))
    b = supported(p, loads(p, 2.0), preload_to_C3(p, 8.0))
    assert np.allclose(a["S"], b["S"]) and np.allclose(a["F"], b["F"])
    assert np.allclose(b["r"] - a["r"], [[-2.0, 0.0, 0.0]])


def test_point_force_on_the_supported_helix():
    """G = (2, 0, -1) kN at theta = 5.7 rad: R_h = (-0.90, 1.67, 0) kN inside the cone eta = 0.6."""
    p = circle(nodes=[11.4])
    G = np.array([2.0, 0.0, -1.0])
    st = supported(p, loads(p, 1.0), preload_to_C3(p, 8.0), [(11.4, G)])
    a = st["actions"][0]
    assert a["R"] == pytest.approx([-0.8986289, 1.6694256, 0.0], abs=1e-6)
    assert a["jump"] == pytest.approx(-2.0)
    assert 0.6 * a["Rnu"] - abs(a["Rt"]) > 0
    i = a["index"]
    assert st["S"][i + 1] - st["S"][i] == pytest.approx(-2.0)
    assert st["balance"]["force_relative"] < 1e-10
    assert st["balance"]["moment_relative"] < 1e-10


def test_stationary_elevation_is_rejected():
    p = geometry.helix(2.0, 0.0, 0.0, np.pi, 201)
    with pytest.raises(ValueError):
        supported(p, loads(p), 1.0)


# ------------------------------------------------------------------ contact

def test_friction_and_strip():
    assert friction_strip(0.6, 0.8, 0.5) == (0.6, 0.8)
    assert friction_strip(0.6, 0.8, 0.0)[0] == 0.6
    assert friction_strip(0.9, 0.8, 0.5)[0] == pytest.approx(0.8)


def test_minimum_preload_and_thresholds():
    """T_min = 6.66667 kN, thresholds 2.27890 and 3.38686 kN/m, active point 1.64274 rad."""
    p = circle()
    n = len(p.s)
    prob = ContactProblem(p, loads(p, 0.0), np.column_stack((np.ones(n), np.zeros(n), np.zeros(n))), [], 0.6)
    assert prob.minimum_preload(0.0)[0] == pytest.approx(20 / 3, abs=1e-6)
    assert minimum_preload_circle(0, 0, 2, -0.5, 1, 0.6, 2 * np.pi) == pytest.approx(20 / 3)
    for T, hc in ((8.0, 2.27890), (12.0, 3.38686)):
        exact = critical_horizontal_circle(0.0, T, radius=2, grade=-0.5, weight=1, eta=0.6, theta_end=2 * np.pi)
        assert exact == pytest.approx(hc, abs=1e-5)
        assert prob.multiplier_interval(T)["hi"] == pytest.approx(exact, abs=1e-5)
    r = prob.multiplier_interval(8.0)
    assert p.theta[prob.location(r["governing_hi"])] == pytest.approx(1.64274, abs=2e-3)
    _, theta, _ = minimum_preload_circle(2.27890, 0, 2, -0.5, 1, 0.6, 2 * np.pi, details=True)
    assert theta == pytest.approx(1.64274, abs=1e-4)


@pytest.mark.parametrize("beta,expected", [(0.0, 5.67), (np.pi / 2, 5.00), (np.pi, 7.67),
                                           (np.pi + np.arctan(1 / 0.6), 8.61)])
def test_pseudo_static_preload(beta, expected):
    """gamma = 0.5: T_min = 5.67, 5.00, 7.67 and 8.61 kN."""
    p = circle()
    n = len(p.s)
    prob = ContactProblem(p, loads(p, 0.0), np.zeros((n, 3)), [], 0.6)
    value = prob.minimum_preload(0.5, np.ones(n), beta)[0]
    exact = minimum_preload_circle(0.5 * np.cos(beta), 0.5 * np.sin(beta), 2, -0.5, 1, 0.6, 2 * np.pi)
    assert value == pytest.approx(exact, abs=1e-6)
    assert value == pytest.approx(expected, abs=5e-3)


def test_admissible_region_is_convex_and_contains_the_benchmark():
    p = circle()
    n = len(p.s)
    prob = ContactProblem(p, loads(p, 0.0), np.column_stack((np.ones(n), np.zeros(n), np.zeros(n))), [], 0.6)
    poly = prob.region((0.0, 16.0), (-3.0, 3.0))
    assert len(poly) > 10
    left = poly[: len(poly) // 2]
    assert np.all(np.interp(2.0, left[:, 1], left[:, 0]) <= 8.0)
    assert prob.preload_interval(2.0)["lo"] == pytest.approx(7.05015, abs=1e-5)


# ------------------------------------------------------------------ paths without reactions

def test_exceptional_arc():
    """S = B g / (b cos theta), h = B a / (b g cos^2 theta), p3 = -B c sin theta / (b g cos^2 theta)."""
    p = geometry.helix(2.0, -1.0, np.pi + 0.15, np.pi + 1.2, 1201)
    out = fixed_plane(p, 3.0, 0.0)
    th = p.theta
    assert np.allclose(out["S"], 3 / np.cos(th))
    assert np.allclose(out["h"], 3 / (2 * np.cos(th) ** 2))
    assert np.allclose(out["p"][:, 2], 0.75 * np.sin(th) / np.cos(th) ** 2)
    assert np.allclose(out["transverse"], 0.0, atol=1e-12)
    assert np.all(out["S"] < 0)
    fit = compatibility(p, out["p"])
    assert fit["relative_error"] < 1e-9
    assert fit["C"][1] == pytest.approx(3.0)


def test_three_component_loading():
    p = circle()
    th = p.theta
    out = loads_for_thrust(p, -8 - 2 * p.s, np.full(len(p.s), -2.0))
    assert np.allclose(out["p"][:, 0], -2 * np.sin(th) + (-4 - 2 * th) * np.cos(th))
    assert np.allclose(out["p"][:, 1], 2 * np.cos(th) + (-4 - 2 * th) * np.sin(th))
    assert np.allclose(out["p"][:, 2], -1.0)
    assert compatibility(p, out["p"])["relative_error"] < 1e-9


def test_assigned_path_without_reactions_is_rejected():
    s = np.linspace(0, 5, 61)
    xyz = constant_load_curve(s, F0, np.array([0.7, 0.0, -1.0]), np.zeros(3))
    good = geometry.spline_path(xyz, 2001)
    bad_xyz = xyz.copy()
    bad_xyz[:, 2] += 0.6 * np.sin(np.pi * s / 5)
    bad = geometry.spline_path(bad_xyz, 2001)
    pg = np.tile([0.7, 0.0, -1.0], (len(good.s), 1))
    fit = compatibility(good, pg)
    assert fit["relative_error"] < 1e-4
    assert fit["C"] == pytest.approx(F0, abs=1e-3)
    assert compatibility(bad, pg)["relative_error"] > 0.05


# ------------------------------------------------------------------ free curves

def _case_c(s):
    return np.column_stack((0.7 + 0.2 * s, 0.3 * s, -np.ones_like(s)))


def test_case_c_endpoint():
    s = np.linspace(0, 5, 2001)
    c = free_curve(s, F0, _case_c(s), np.zeros(3))
    assert c["xyz"][-1] == pytest.approx(TARGET_C, abs=1e-8)
    assert np.all(c["S"] < 0) and np.all(c["N"] < 0)


def test_endpoint_correction_and_jacobian():
    s = np.linspace(0, 5, 2001)
    p = _case_c(s)
    C, history, ok = solve_endpoint(s, p, np.zeros(3), TARGET_C, [-2.5, -3.5, -1.5])
    assert ok
    assert len(history) - 1 == 4
    assert history[0]["error"] == pytest.approx(0.37, abs=0.005)
    assert history[-1]["error"] < 1e-12
    assert C == pytest.approx(F0, abs=1e-5)
    J = endpoint_jacobian(s, F0, p)
    ev = np.sort(np.linalg.eigvals(-J[:2, :2]).real)
    assert ev == pytest.approx([0.00304553, 0.693717], abs=1e-6)
    h = 1e-6
    fd = np.column_stack([(free_curve(s, F0 + h * e, p, np.zeros(3))["xyz"][-1]
                           - free_curve(s, F0 - h * e, p, np.zeros(3))["xyz"][-1]) / (2 * h) for e in np.eye(3)])
    assert np.allclose(J, fd, atol=1e-8)


def test_constant_loads_closed_form_and_planarity():
    s = np.linspace(0, 5, 2001)
    for p0, C in (([0.7, 0, -1], F0), ([0, 0, -1], F0), ([0.7, 0, 0], F0), ([0.7, 0, -1], [-3, 0, -2]),
                  ([0.5, 0.5, -1], F0)):
        p = np.tile(p0, (len(s), 1)).astype(float)
        c = free_curve(s, C, p, np.zeros(3))
        closed = constant_load_curve(s, np.asarray(C, float), np.asarray(p0, float), np.zeros(3))
        assert np.max(np.abs(c["xyz"] - closed)) < 1e-10
    pa = np.tile([0.7, 0, -1.0], (len(s), 1))
    a = free_curve(s, F0, pa, np.zeros(3))
    dist, _ = plane_distance(a["xyz"], np.zeros(3), F0, pa[0])
    assert np.max(np.abs(dist)) < 1e-12
    kappa, tau = curvature_torsion(a["F"], pa, derivative(pa, s))
    assert np.nanmax(np.abs(tau)) < 1e-12


def test_variable_loads_leave_the_plane():
    """Distance from the plane of case A: about 0.32 m for case B and 0.18 m for case C."""
    s = np.linspace(0, 5, 2001)
    pb = np.column_stack((0.7 + 0.2 * s, 0 * s, -np.ones_like(s)))
    for p, expected in ((pb, 0.32), (_case_c(s), 0.18)):
        c = free_curve(s, F0, p, np.zeros(3))
        dist, _ = plane_distance(c["xyz"], np.zeros(3), F0, np.array([0.7, 0, -1.0]))
        assert np.max(np.abs(dist)) == pytest.approx(expected, abs=0.006)


def test_catenary_under_self_weight():
    a = 4.0
    s = np.linspace(0, 5, 1001)
    c = self_weight_curve(s, [-4.0, 0.0, -4.0 * np.sinh(5 / (2 * a))], lambda v: np.ones_like(v),
                          np.zeros((len(s), 3)), np.zeros(3))
    z = a * (np.cosh(5 / (2 * a)) - np.cosh((s - 2.5) / a))
    assert np.max(np.abs(c["xyz"][:, 2] - z)) < 1e-9
    assert np.allclose(c["S"], -4.0)


def test_point_force_on_a_free_curve():
    s = piecewise_grid(5.0, 2001, [2.5])
    p = _case_c(s)
    G = np.array([0.5, 0.0, -1.0])
    c = free_curve(s, F0, p, np.zeros(3), [(2.5, G)])
    i = int(np.argmin(np.abs(s - 2.5)))
    assert c["F"][i + 1] - c["F"][i] == pytest.approx(-G)
    assert c["xyz"][i + 1] == pytest.approx(c["xyz"][i])
    force = -c["F"][0] + c["F"][-1] + integral(p, s) + G
    assert np.linalg.norm(force) < 1e-10


# ------------------------------------------------------------------ node

def test_node_equilibrium():
    a = node([-3, -2, -1], [2, 0, 0])
    b = node([-3, -2, -1], [2, 0, -1])
    assert a["angle"] == pytest.approx(12.6044, abs=1e-4)
    assert b["angle"] == pytest.approx(19.4463, abs=1e-4)
    assert b["Fp"] == pytest.approx([-5, -2, 0])
    assert b["residual"] < 1e-14
