"""Thrust line analysis of plane arches of finite thickness.

The arch is the region between the intrados and the extrados, divided by
joints: segments from the intrados (end I) to the extrados (end E), normal
to the centre line as in a voussoir arch, or vertical, as the sections at
constant x of the projected abscissa of the article. The first and the last
joint are the springings. Between two joints lies a slice, which carries its
own weight at its centroid, the fill above its extrados, a surcharge and the
point loads applied on its extrados.

The part of the arch on the left of joint j is in equilibrium under the
reaction R_A = -C on the first joint, the loads on it and the force F_j that
the rest of the arch exerts on it:

    F_j = C - P_j,     M_j = M_0 - Q_j,

with C = F(0), M_0 the moment of C about the origin along its line of action,
P_j the resultant of the loads on the left of the joint and Q_j its moment
(moments about e2, x1 F3 - x3 F1). The line of action of F_j crosses the
joint between I_j and E_j, that is the centre of pressure lies in the
masonry and the joint is compressed, when

    g_I = M_j - I_j x F_j >= 0   and   g_E = M_j - E_j x F_j <= 0.

Both are affine in (C, M_0) and in a load multiplier, so that the lines of
minimum and maximum thrust, the collapse multiplier and the geometric
safety factor are linear programmes: Heyman's hypotheses (no tensile
strength, no sliding unless a friction limit is given, unlimited
compressive strength) and the safe theorem. The centre of pressure is
I + g_I / (g_I - g_E) (E - I), and the hinges of a collapse mechanism are
the joints where it reaches a face.
"""
from dataclasses import dataclass

import numpy as np
from scipy.integrate import cumulative_simpson
from scipy.interpolate import CubicSpline
from scipy.optimize import brentq, linprog

from .plane import cross2

EPS = 1e-12
SHAPES = ("circular", "pointed", "elliptical", "parabolic", "catenary", "points")


# ---------------------------------------------------------------- geometry

@dataclass
class ArchGeometry:
    intrados: np.ndarray
    extrados: np.ndarray
    centre: np.ndarray
    ia: np.ndarray
    ea: np.ndarray
    joints: str
    crown: int
    radius: float = None
    description: str = ""

    @property
    def n(self):
        """Number of slices (one less than the number of joints)."""
        return len(self.ia) - 1

    @property
    def I(self):
        return _at(self.intrados, self.ia)

    @property
    def E(self):
        return _at(self.extrados, self.ea)

    @property
    def mid(self):
        return 0.5 * (self.I + self.E)

    @property
    def length(self):
        return np.linalg.norm(self.E - self.I, axis=1)

    @property
    def direction(self):
        d = self.E - self.I
        return d / np.linalg.norm(d, axis=1)[:, None]

    @property
    def angle(self):
        """Angle of every joint from the vertical, degrees, positive when its extrados end leans to e1."""
        d = self.direction
        return np.degrees(np.arctan2(d[:, 0], d[:, 1]))

    @property
    def position(self):
        """Distance along the line of the joint centres, from the first springing (m)."""
        m = self.mid
        return np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(m, axis=0), axis=1))]


def _lengths(P):
    return np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]


def _at(P, a):
    """Points at the arc-length parameters a of the polyline P."""
    c = _lengths(P)
    a = np.asarray(a, dtype=float)
    return np.column_stack((np.interp(a, c, P[:, 0]), np.interp(a, c, P[:, 1])))


def _between(P, c, a0, a1):
    """Vertices of the polyline P from the parameter a0 to a1, both ends included."""
    p0 = np.array([np.interp(a0, c, P[:, 0]), np.interp(a0, c, P[:, 1])])
    p1 = np.array([np.interp(a1, c, P[:, 0]), np.interp(a1, c, P[:, 1])])
    i0 = int(np.searchsorted(c, a0, side="right"))
    i1 = int(np.searchsorted(c, a1, side="left"))
    return np.vstack([p0[None, :], P[i0:i1], p1[None, :]])


def _thickness(sigma, total, t_crown, t_spring):
    """Linear from the crown (middle of the centre line) to the springings."""
    return t_crown + (t_spring - t_crown) * np.abs(2.0 * sigma / total - 1.0)


def centre_line(shape, span, rise, points=None):
    """The centre line as (curve, phi0, phi1, radius): curve(phi) returns points and derivatives."""
    L, f = float(span), float(rise)
    if L <= 0 or (shape != "points" and f <= 0):
        raise ValueError("The span and the rise must be positive")
    if shape == "circular":
        R = (L ** 2 / 4.0 + f ** 2) / (2.0 * f)
        alpha = np.arctan2(L / 2.0, R - f)

        def curve(phi):
            return (np.column_stack((L / 2 + R * np.sin(phi), f - R + R * np.cos(phi))),
                    np.column_stack((R * np.cos(phi), -R * np.sin(phi))))
        return curve, -alpha, alpha, R
    if shape == "elliptical":
        def curve(phi):
            return (np.column_stack((L / 2 - L / 2 * np.cos(phi), f * np.sin(phi))),
                    np.column_stack((L / 2 * np.sin(phi), f * np.cos(phi))))
        return curve, 0.0, np.pi, None
    if shape == "parabolic":
        def curve(x):
            return (np.column_stack((x, 4 * f * x * (L - x) / L ** 2)),
                    np.column_stack((np.ones_like(x), 4 * f * (L - 2 * x) / L ** 2)))
        return curve, 0.0, L, None
    if shape == "catenary":
        a = brentq(lambda a: a * (np.cosh(L / (2 * a)) - 1.0) - f, L / 1400.0, 1e6 * L, xtol=1e-14 * L,
                   maxiter=500)

        def curve(x):
            return (np.column_stack((x, a * (np.cosh(L / (2 * a)) - np.cosh((x - L / 2) / a)))),
                    np.column_stack((np.ones_like(x), -np.sinh((x - L / 2) / a))))
        return curve, 0.0, L, None
    if shape == "points":
        P = np.asarray(points, dtype=float)
        if P.ndim != 2 or P.shape[0] < 3 or P.shape[1] < 2:
            raise ValueError("A centre line through points needs at least three points (x, z)")
        P = P[:, :2]
        c = _lengths(P)
        if np.any(np.diff(c) <= 0):
            raise ValueError("Two consecutive points of the centre line coincide")
        sp = CubicSpline(c, P, bc_type="natural")
        d = sp.derivative()

        def curve(u):
            return sp(u), d(u)
        return curve, 0.0, float(c[-1]), None
    raise ValueError("Unknown shape %s" % shape)


def _smooth(shape, span, rise, t_crown, t_spring, n, points=None, resolution=6000):
    curve, p0, p1, R = centre_line(shape, span, rise, points)
    phi = np.linspace(p0, p1, 20001)
    _, d = curve(phi)
    sig = cumulative_simpson(np.linalg.norm(d, axis=1), x=phi, initial=0)
    total = float(sig[-1])
    sub = max(4, int(np.ceil(resolution / n)))
    s_fine = np.linspace(0.0, total, n * sub + 1)
    ph = np.interp(s_fine, sig, phi)
    c, d = curve(ph)
    tau = d / np.linalg.norm(d, axis=1)[:, None]
    nu = np.column_stack((-tau[:, 1], tau[:, 0]))
    t = _thickness(s_fine, total, t_crown, t_spring)
    intr = c - 0.5 * t[:, None] * nu
    extr = c + 0.5 * t[:, None] * nu
    _offset_check(intr, tau, "intrados")
    _offset_check(extr, tau, "extrados")
    idx = np.arange(0, n * sub + 1, sub)
    return intr, extr, c, _lengths(intr)[idx], _lengths(extr)[idx], R


def _offset_check(P, tau, name):
    seg = np.diff(P, axis=0)
    t = 0.5 * (tau[1:] + tau[:-1])
    if np.any(np.sum(seg * t, axis=1) <= 0):
        raise ValueError("The %s folds back: the thickness exceeds twice the radius of curvature of the "
                         "centre line somewhere. Reduce the thickness." % name)


def _pointed(span, rise, t_crown, t_spring, n, resolution=6000):
    """Two-centred arch: circular halves with centres on the springing line and a vertical crown joint."""
    L, f = float(span), float(rise)
    if f <= L / 2:
        raise ValueError("A pointed arch needs a rise larger than half the span")
    R = (L ** 2 / 4.0 + f ** 2) / L
    ta = np.arccos((L / 2 - R) / R)
    half = R * (np.pi - ta)
    total = 2 * half

    def t_of(theta):
        return _thickness(R * (np.pi - theta), total, t_crown, t_spring)

    def point(theta, side):
        k = R + side * 0.5 * t_of(theta)
        return np.column_stack((R + k * np.cos(theta), k * np.sin(theta)))

    # the intrados halves meet below the apex (before the apex angle), the extrados halves above it
    th_i = brentq(lambda th: point(np.array([th]), -1)[0, 0] - L / 2, ta, np.pi, xtol=1e-15)
    th_e = brentq(lambda th: point(np.array([th]), 1)[0, 0] - L / 2, 1e-12, ta, xtol=1e-15)
    m = max(n // 2, 2)
    sub = max(4, int(np.ceil(resolution / (2 * m))))
    th = np.linspace(np.pi, th_i, (m - 1) * sub + 1)
    intr_l = point(th, -1)
    extr_l = point(th, 1)
    wedge = np.linspace(th_i, th_e, sub + 1)[1:]
    extr_l = np.vstack([extr_l, point(wedge, 1)])
    intr_l[-1, 0] = L / 2
    extr_l[-1, 0] = L / 2
    cen_th = np.linspace(np.pi, ta, (m - 1) * sub + 1)
    cen_l = np.column_stack((R + R * np.cos(cen_th), R * np.sin(cen_th)))

    def mirror(P):
        Q = P[::-1].copy()
        Q[:, 0] = L - Q[:, 0]
        return Q
    intr = np.vstack([intr_l, mirror(intr_l)[1:]])
    extr = np.vstack([extr_l, mirror(extr_l)[1:]])
    centre = np.vstack([cen_l, mirror(cen_l)[1:]])
    ci, ce = _lengths(intr), _lengths(extr)
    ki = np.r_[np.arange(0, (m - 1) * sub + 1, sub), (m - 1) * sub]
    ke = np.r_[np.arange(0, (m - 1) * sub + 1, sub), len(extr_l) - 1]
    ni, ne = len(intr) - 1, len(extr) - 1
    ia = np.r_[ci[ki], ci[ni - ki[::-1][1:]]]
    ea = np.r_[ce[ke], ce[ne - ke[::-1][1:]]]
    return intr, extr, centre, ia, ea, R


def _monotonic(X, name):
    """Indices (i0, i1) of the part of a chain that advances along e1, and the abscissae beyond its ends.

    Near a springing with a vertical tangent and a thickness that grows toward
    it, a face may recede by a little before it advances; the sections start
    beyond that receding part, so that each crosses the face once.
    """
    d = np.diff(X)
    bad = np.where(d <= 0)[0]
    m = len(X)
    head, tail = bad[bad < m // 3], bad[bad >= m - m // 3]
    if len(bad) > len(head) + len(tail):
        raise ValueError("Vertical sections need an %s that advances along e1 (no horseshoe shape)" % name)
    i0 = int(head.max()) + 1 if len(head) else 0
    i1 = int(tail.min()) if len(tail) else m - 1
    return i0, i1, float(X[:i0 + 1].max()), float(X[i1:].min())


def _vertical(intr, extr, n):
    """Vertical sections between the springing joints, evenly spaced in x."""
    ci, ce = _lengths(intr), _lengths(extr)
    a0, a1, lo_i, hi_i = _monotonic(intr[:, 0], "intrados")
    b0, b1, lo_e, hi_e = _monotonic(extr[:, 0], "extrados")
    lo = max(lo_i, lo_e)
    hi = min(hi_i, hi_e)
    if hi <= lo:
        raise ValueError("The arch has no vertical section between its springings")
    xs = np.linspace(lo, hi, max(n - 1, 2))
    ia = np.r_[0.0, np.interp(xs, intr[a0:a1 + 1, 0], ci[a0:a1 + 1]), ci[-1]]
    ea = np.r_[0.0, np.interp(xs, extr[b0:b1 + 1, 0], ce[b0:b1 + 1]), ce[-1]]
    keep = np.r_[True, np.diff(ia) > 1e-12 * ci[-1]] | np.r_[True, np.diff(ea) > 1e-12 * ce[-1]]
    return ia[keep], ea[keep]


def build(shape="circular", span=10.0, rise=5.0, t_crown=1.0, t_spring=None, n=200, joints="normal",
          points=None, resolution=6000):
    """Geometry of the arch: intrados, extrados, centre line and joints."""
    t_spring = t_crown if t_spring is None else t_spring
    if t_crown <= 0 or t_spring <= 0:
        raise ValueError("The thickness must be positive")
    n = int(max(n, 4))
    if shape == "pointed":
        intr, extr, centre, ia, ea, R = _pointed(span, rise, t_crown, t_spring, n, resolution)
    else:
        intr, extr, centre, ia, ea, R = _smooth(shape, span, rise, t_crown, t_spring, n, points, resolution)
    if joints == "vertical":
        ia, ea = _vertical(intr, extr, n)
    elif joints != "normal":
        raise ValueError("Unknown joints %s" % joints)
    geo = ArchGeometry(intr, extr, centre, ia, ea, joints, 0, R)
    m = geo.mid
    geo.crown = int(np.argmax(m[:, 1]))
    return geo


# ---------------------------------------------------------------- loads

def _polygon(P):
    """Area and centroid of a polygon (counterclockwise positive)."""
    x, y = P[:, 0], P[:, 1]
    x1, y1 = np.roll(x, -1), np.roll(y, -1)
    cr = x * y1 - x1 * y
    A = 0.5 * float(np.sum(cr))
    if abs(A) < 1e-300:
        return 0.0, P.mean(axis=0)
    return A, np.array([np.sum((x + x1) * cr), np.sum((y + y1) * cr)]) / (6.0 * A)


def _fill_strip(chain, level):
    """Area and centroid of the region between a polyline (x increasing) and the level above it."""
    x, z = chain[:, 0], chain[:, 1]
    if len(x) < 2:
        return 0.0, chain[0]
    if np.any(np.diff(x) < -1e-12):
        raise ValueError("A fill needs an extrados that advances along e1")
    xs, hs = [x[0]], [max(level - z[0], 0.0)]
    for k in range(len(x) - 1):
        h0, h1 = level - z[k], level - z[k + 1]
        if h0 * h1 < 0:
            r = h0 / (h0 - h1)
            xs.append(x[k] + r * (x[k + 1] - x[k]))
            hs.append(0.0)
        xs.append(x[k + 1])
        hs.append(max(h1, 0.0))
    xs, hs = np.array(xs), np.array(hs)
    dx = np.diff(xs)
    a, b = hs[:-1], hs[1:]
    A = float(np.sum(0.5 * (a + b) * dx))
    if A <= 1e-300:
        return 0.0, np.array([0.5 * (x[0] + x[-1]), level])
    Mx = float(np.sum(dx * (xs[:-1] * (2 * a + b) + xs[1:] * (a + 2 * b)) / 6.0))
    H2 = float(np.sum(dx * (a * a + a * b + b * b) / 3.0))
    return A, np.array([Mx / A, level - 0.5 * H2 / A])


@dataclass
class SliceLoads:
    """Loads of every slice: resultant (n, 2) and moment about the origin (n,) of each pattern."""
    ring: np.ndarray
    ring_moment: np.ndarray
    fill: np.ndarray
    fill_moment: np.ndarray
    inertia: np.ndarray
    inertia_moment: np.ndarray
    points: np.ndarray
    points_moment: np.ndarray
    ring_area: np.ndarray
    ring_centroid: np.ndarray
    fill_area: np.ndarray
    fill_centroid: np.ndarray
    point_list: list


def slice_loads(geo, unit_weight=20.0, depth=1.0, fill=False, fill_level=0.0, fill_weight=18.0,
                surcharge=0.0, fill_inertia=True, point_loads=()):
    """Loads of the slices. The inertia pattern is the weight turned along e1 (multiplier 1)."""
    n = geo.n
    ci, ce = _lengths(geo.intrados), _lengths(geo.extrados)
    ring_a = np.zeros(n)
    ring_c = np.zeros((n, 2))
    fill_a = np.zeros(n)
    fill_c = np.zeros((n, 2))
    sur = np.zeros(n)
    sur_x = np.zeros(n)
    top = []
    for k in range(n):
        low = _between(geo.intrados, ci, geo.ia[k], geo.ia[k + 1])
        up = _between(geo.extrados, ce, geo.ea[k], geo.ea[k + 1])
        A, g = _polygon(np.vstack([low, up[::-1]]))
        ring_a[k], ring_c[k] = A, g
        if A <= 0:
            raise ValueError("Slice %d of the arch has no positive area: check the geometry" % (k + 1))
        if fill:
            fill_a[k], fill_c[k] = _fill_strip(up, fill_level)
        if surcharge:
            x0, x1 = up[0, 0], up[-1, 0]
            sur[k] = surcharge * depth * max(x1 - x0, 0.0)
            sur_x[k] = 0.5 * (x0 + x1)
        top.append(up)
    W = unit_weight * depth * ring_a
    ring = np.column_stack((np.zeros(n), -W))
    ring_m = cross2(ring_c, ring)
    Wf = fill_weight * depth * fill_a
    fill_v = np.column_stack((np.zeros(n), -(Wf + sur)))
    sur_pts = np.column_stack((sur_x, np.full(n, fill_level if fill else 0.0)))
    fill_m = cross2(fill_c, np.column_stack((np.zeros(n), -Wf))) + cross2(sur_pts, np.column_stack((np.zeros(n), -sur)))
    inertia = np.column_stack((W, np.zeros(n)))
    inertia_m = cross2(ring_c, inertia)
    if fill_inertia and fill:
        fi = np.column_stack((Wf, np.zeros(n)))
        inertia = inertia + fi
        inertia_m = inertia_m + cross2(fill_c, fi)
    pts = np.zeros((n, 2))
    pts_m = np.zeros(n)
    plist = []
    x_lo = np.array([u[0, 0] for u in top])
    x_hi = np.array([u[-1, 0] for u in top])
    for x, G1, G3 in point_loads:
        G = np.array([G1, G3], dtype=float)
        if not np.any(G):
            continue
        k = np.where((x_lo - 1e-12 <= x) & (x <= x_hi + 1e-12))[0]
        if not len(k):
            raise ValueError("The point load at x = %g m is not above the extrados of the arch" % x)
        k = int(k[0])
        up = top[k]
        r = np.array([x, np.interp(x, up[:, 0], up[:, 1])])
        pts[k] += G
        pts_m[k] += cross2(r, G)
        plist.append((k, r, G))
    return SliceLoads(ring, ring_m, fill_v, fill_m, inertia, inertia_m, pts, pts_m, ring_a, ring_c,
                      fill_a, fill_c, plist)


def combine(loads, lam=0.0, points=1.0):
    """Resultant (n, 2) and moment (n,) of the slices for the dead loads, lam times the inertia and the points."""
    P = loads.ring + loads.fill + lam * loads.inertia + points * loads.points
    Q = loads.ring_moment + loads.fill_moment + lam * loads.inertia_moment + points * loads.points_moment
    return P, Q


def cumulative_loads(P, Q):
    """Resultant and moment of the loads on the left of every joint (n + 1 values)."""
    return (np.vstack([np.zeros((1, 2)), np.cumsum(P, axis=0)]), np.r_[0.0, np.cumsum(Q)])


# ---------------------------------------------------------------- forms of the conditions

def _forms(X, Pc, Qc, Pv=None, Qv=None):
    """g = M_j - X_j x F_j = A y + b with y = (C1, C3, M0[, mu])."""
    A = np.column_stack((X[:, 1], -X[:, 0], np.ones(len(X))))
    b = -Qc + X[:, 0] * Pc[:, 1] - X[:, 1] * Pc[:, 0]
    if Pv is not None:
        A = np.column_stack((A, -Qv + X[:, 0] * Pv[:, 1] - X[:, 1] * Pv[:, 0]))
    return A, b


def _force_forms(Pc, Pv=None):
    """F1 and F3 at every joint as forms in y."""
    n = len(Pc)
    A1 = np.column_stack((np.ones(n), np.zeros(n), np.zeros(n)))
    A3 = np.column_stack((np.zeros(n), np.ones(n), np.zeros(n)))
    if Pv is not None:
        A1 = np.column_stack((A1, -Pv[:, 0]))
        A3 = np.column_stack((A3, -Pv[:, 1]))
    return (A1, -Pc[:, 0]), (A3, -Pc[:, 1])


class ThrustProblem:
    """Linear conditions of a thrust line in the arch, for fixed loads and an optional variable pattern."""

    def __init__(self, geo, P, Q, Pv=None, Qv=None, friction=0.0, alpha=1.0):
        self.geo = geo
        self.Pc, self.Qc = cumulative_loads(P, Q)
        self.var = Pv is not None
        if self.var:
            self.Pvc, self.Qvc = cumulative_loads(Pv, Qv)
        else:
            self.Pvc = self.Qvc = None
        self.friction = float(friction)
        self.scale_F = max(float(np.sum(np.abs(P))), EPS)
        self.scale_L = max(float(np.ptp(geo.extrados, axis=0).max()), EPS)
        self.set_alpha(alpha)

    @property
    def nvar(self):
        return 4 if self.var else 3

    def set_alpha(self, alpha):
        """Shrink every joint about its centre by alpha (alpha = 1: the arch itself)."""
        self.alpha = float(alpha)
        I, E, M = self.geo.I, self.geo.E, self.geo.mid
        self.Ia = M + alpha * (I - M)
        self.Ea = M + alpha * (E - M)
        gI = _forms(self.Ia, self.Pc, self.Qc, self.Pvc, self.Qvc)
        gE = _forms(self.Ea, self.Pc, self.Qc, self.Pvc, self.Qvc)
        rows = [-gI[0], gE[0]]
        rhs = [gI[1], -gE[1]]
        if self.friction > 0:
            d = self.geo.direction
            (A1, b1), (A3, b3) = _force_forms(self.Pc, self.Pvc)
            T = (d[:, :1] * A1 + d[:, 1:] * A3, d[:, 0] * b1 + d[:, 1] * b3)
            N = (d[:, :1] * A3 - d[:, 1:] * A1, d[:, 0] * b3 - d[:, 1] * b1)
            mu = self.friction
            rows += [T[0] - mu * N[0], -T[0] - mu * N[0]]
            rhs += [-(T[1] - mu * N[1]), -(-T[1] - mu * N[1])]
        self.A_ub = np.vstack(rows)
        self.b_ub = np.concatenate(rhs)

    def _solve(self, c, mu=None, bounds_mu=(0.0, None)):
        A, b = self.A_ub, self.b_ub
        nv = self.nvar
        bounds = [(None, None)] * 3
        if self.var:
            bounds.append(bounds_mu if mu is None else (mu, mu))
        sF, sL = self.scale_F, self.scale_L
        # scale the unknowns: forces by sF, the moment by sF sL
        D = np.array([sF, sF, sF * sL] + ([1.0] if self.var else []))
        As = A * D[None, :]
        rs = np.maximum(np.max(np.abs(As), axis=1), EPS)
        res = linprog(np.asarray(c, dtype=float) * D, A_ub=As / rs[:, None], b_ub=b / rs,
                      bounds=[(None if lo is None else lo / D[k], None if hi is None else hi / D[k])
                              for k, (lo, hi) in enumerate(bounds)][:nv], method="highs")
        if res.status == 2:
            return None
        if res.status == 3:
            return "unbounded"
        if res.status != 0:
            raise ValueError("The linear programme failed: %s" % res.message)
        return res.x * D

    def feasible(self, mu=None):
        return self._solve(np.zeros(self.nvar), mu) is not None

    def thrust(self, which="min", mu=None):
        """The line of minimum or maximum thrust H_A = -C1 (horizontal reaction at the first springing)."""
        c = np.zeros(self.nvar)
        c[0] = -1.0 if which == "min" else 1.0
        y = self._solve(c, mu)
        if isinstance(y, str):
            raise ValueError("The %s thrust is unbounded" % ("minimum" if which == "min" else "maximum"))
        return y

    def collapse(self, cap=1e6):
        """Largest multiplier of the variable pattern."""
        if not self.var:
            raise ValueError("No variable load")
        c = np.zeros(4)
        c[3] = -1.0
        y = self._solve(c, None, (0.0, cap))
        if isinstance(y, str):
            return None
        return y

    def through(self, eps, joints):
        """The line through the points at the eccentricities eps (fractions of the joint, from its centre)."""
        X = np.array([self.geo.mid[j] + e * (self.geo.E[j] - self.geo.I[j]) for e, j in zip(eps, joints)])
        Pc, Qc = self.Pc[list(joints)], self.Qc[list(joints)]
        A, b = _forms(X, Pc, Qc)
        try:
            return np.linalg.solve(A, -b)
        except np.linalg.LinAlgError:
            raise ValueError("The three points do not fix a thrust line (they are aligned with the loads)")

    def state(self, y):
        """Forces, centres of pressure and eccentricities of the line y at every joint."""
        y = np.asarray(y, dtype=float)
        mu = y[3] if len(y) > 3 else 0.0
        Pc = self.Pc + (mu * self.Pvc if self.var else 0.0)
        Qc = self.Qc + (mu * self.Qvc if self.var else 0.0)
        F = y[None, :2] - Pc
        M = y[2] - Qc
        geo = self.geo
        I, E = geo.I, geo.E
        gI = M - cross2(I, F)
        gE = M - cross2(E, F)
        D = gI - gE
        tau = np.where(np.abs(D) > EPS * self.scale_F * self.scale_L, gI / np.where(D == 0, 1.0, D), np.nan)
        centre = I + tau[:, None] * (E - I)
        d = geo.direction
        N = -(d[:, 0] * F[:, 1] - d[:, 1] * F[:, 0])
        V = d[:, 0] * F[:, 0] + d[:, 1] * F[:, 1]
        ecc = tau - 0.5
        e = ecc * geo.length
        inside = bool(np.all(gI >= -1e-9 * self.scale_F * self.scale_L) and
                      np.all(gE <= 1e-9 * self.scale_F * self.scale_L))
        return dict(y=y, mu=mu, F=F, M=M, gI=gI, gE=gE, tau=tau, centre=centre, N=N, V=V, ecc=ecc, e=e,
                    moment=-N * e, H=-F[:, 0], inside=inside)

    def hinges(self, st, tol=1e-7):
        """Joints where the centre of pressure reaches a face: (joint, 'intrados' or 'extrados', point)."""
        scale = tol * self.scale_F * self.scale_L
        gI = st["M"] - cross2(self.Ia, st["F"])
        gE = st["M"] - cross2(self.Ea, st["F"])
        out = []
        for face, g, X in (("intrados", gI, self.Ia), ("extrados", -gE, self.Ea)):
            act = np.where(np.abs(g) <= scale)[0]
            groups = np.split(act, np.where(np.diff(act) > 1)[0] + 1) if len(act) else []
            for grp in groups:
                j = int(grp[np.argmin(np.abs(g[grp]))])
                out.append((j, face, X[j]))
        out.sort(key=lambda r: r[0])
        return out


# ---------------------------------------------------------------- derived quantities

def geometric_factor(problem, tol=1e-7):
    """Geometric safety factor: the actual thickness over the least thickness, about the joint centres,
    that still contains a thrust line for the same loads (bisection on the shrink factor alpha)."""
    lo, hi = 0.0, 1.0
    problem.set_alpha(1.0)
    if not problem.feasible():
        hi = 1.0
        for _ in range(60):
            hi *= 1.5
            problem.set_alpha(hi)
            if problem.feasible():
                break
        else:
            problem.set_alpha(1.0)
            return None, None
        lo = hi / 1.5
    while hi - lo > tol * hi:
        mid = 0.5 * (lo + hi)
        problem.set_alpha(mid)
        if problem.feasible():
            hi = mid
        else:
            lo = mid
    problem.set_alpha(hi)
    y = problem._solve(np.zeros(problem.nvar))
    st = problem.state(y)
    hinges = problem.hinges(st, tol=1e-6)
    problem.set_alpha(1.0)
    return 1.0 / hi, dict(alpha=hi, state=st, hinges=hinges)


def mechanism_multiplier(hinges, P, Q, Pv, Qv):
    """Multiplier of the variable loads for the mechanism with four hinges, by virtual work.

    Slices on the left of the first hinge and on the right of the last stay
    at rest; the three blocks between rotate about the first hinge, about the
    intersection of the lines through hinges 1-2 and 3-4, and about the last
    hinge. The power of a slice load rotating with omega about O is
    omega (Q_k - O x P_k).
    """
    (j1, H1), (j2, H2), (j3, H3), (j4, H4) = [(h[0], np.asarray(h[2], dtype=float)) for h in hinges]
    a, b = H2 - H1, H4 - H3
    den = cross2(a, b)
    if abs(den) < EPS * max(np.linalg.norm(a) * np.linalg.norm(b), EPS):
        return None
    t = cross2(H3 - H1, b) / den
    O = H1 + t * a
    w1 = 1.0
    w2 = w1 * float(np.dot(H2 - H1, H2 - O)) / max(float(np.dot(H2 - O, H2 - O)), EPS)
    w3 = w2 * float(np.dot(H3 - O, H3 - H4)) / max(float(np.dot(H3 - H4, H3 - H4)), EPS)
    k = np.arange(len(P))
    blocks = [((k >= j1) & (k < j2), w1, H1), ((k >= j2) & (k < j3), w2, O), ((k >= j3) & (k < j4), w3, H4)]
    pd = pv = 0.0
    for mask, w, c in blocks:
        pd += w * float(np.sum(Q[mask] - cross2(c, P[mask])))
        pv += w * float(np.sum(Qv[mask] - cross2(c, Pv[mask])))
    if abs(pv) < EPS:
        return None
    return -pd / pv


def minimum_thickness(make, tol=1e-5, floor=1e-4):
    """Least factor on the thickness for which a thrust line fits, the loads following the geometry.

    make(factor) returns the ThrustProblem of the arch with every thickness
    multiplied by factor. Returns the factor and the problem and line at it,
    or None when even a thickness ten times larger does not contain a line.
    """
    hi = 1.0
    while not make(hi).feasible():
        hi *= 1.5
        if hi > 10.0:
            return None
    lo = hi
    while True:
        lo *= 0.5
        if lo < floor:
            lo = 0.0
            break
        if not make(lo).feasible():
            break
    while hi - lo > tol * hi:
        mid = 0.5 * (lo + hi)
        if mid < floor:
            hi = floor if make(floor).feasible() else hi
            break
        if make(mid).feasible():
            hi = mid
        else:
            lo = mid
    problem = make(hi)
    y = problem._solve(np.zeros(problem.nvar))
    st = problem.state(y)
    return dict(factor=hi, problem=problem, state=st, hinges=problem.hinges(st, tol=1e-5))
