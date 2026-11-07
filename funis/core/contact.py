"""Effective wall contact and the admissible preloads and horizontal loads.

The horizontal reaction on the line, resolved on the projected frame, must
satisfy r_nu >= 0 and |r_t| <= eta r_nu with eta = min(mu, phi) and
phi = L_sw / (2 delta) (Section 6 of the article). The reactions are affine
in the preload T = -S(0) and in the multiplier lam of the horizontal loads,
r(T, lam) = r^v + T r^(1) + lam r^h, so every constraint sampled along the
path is a linear form a + b T + c lam >= 0. The admissible preloads at a
fixed multiplier, the admissible multipliers at a fixed preload and the
admissible pairs are therefore an interval, an interval and a convex polygon.
Compression of the line, -S >= 0, depends on T only. A point action adds the
cone of its point reaction, which depends on neither parameter.
"""
import numpy as np
from scipy.optimize import brentq

from .supported import preload_to_C3, supported

EPS = 1e-12


def friction_strip(mu, strip, delta):
    """eta = min(mu, phi), phi = L_sw / (2 delta); delta <= 0 means no strip limit."""
    phi = np.inf if delta <= 0 else float(strip) / (2.0 * float(delta))
    return float(min(float(mu), phi)), float(phi)


def cone_margin(rt, rnu, eta):
    """Nonnegative exactly inside the cone: min(r_nu, eta r_nu - |r_t|)."""
    return np.minimum(rnu, eta * rnu - np.abs(rt))


def cone_forms(rt, rnu, eta):
    """Linear forms (eta r_nu - r_t, eta r_nu + r_t), nonnegative inside the cone."""
    rt = np.asarray(rt, dtype=float)
    rnu = np.asarray(rnu, dtype=float)
    return np.column_stack((eta * rnu - rt, eta * rnu + rt))


def interval(base, slope, lower=-np.inf, upper=np.inf, tol=EPS):
    """Set of x with base + x * slope >= 0 for every form.

    Returns (lo, hi, index_lo, index_hi), the indices naming the forms that
    bound the interval (-1 for the given bounds), or None when it is empty.
    """
    a = np.ravel(np.asarray(base, dtype=float))
    b = np.ravel(np.asarray(slope, dtype=float))
    scale = max(float(np.max(np.abs(a))) if a.size else 0.0, 1.0)
    lo, hi, ilo, ihi = float(lower), float(upper), -1, -1
    pos = b > tol
    neg = b < -tol
    flat = ~(pos | neg)
    if np.any(a[flat] < -1e-9 * scale):
        return None
    if np.any(pos):
        v = -a[pos] / b[pos]
        k = int(np.argmax(v))
        if v[k] > lo:
            lo, ilo = float(v[k]), int(np.where(pos)[0][k])
    if np.any(neg):
        v = -a[neg] / b[neg]
        k = int(np.argmin(v))
        if v[k] < hi:
            hi, ihi = float(v[k]), int(np.where(neg)[0][k])
    return None if lo > hi + 1e-12 * max(abs(lo), abs(hi), 1.0) else (lo, hi, ilo, ihi)


class ContactProblem:
    """Linear forms of the contact constraints of a supported path.

    path: the geometry; p_fixed: the loads that are not scaled (vertical);
    p_h: the horizontal loads at multiplier 1; actions: point actions;
    eta: the cone coefficient; wall: side of the wall.
    """

    def __init__(self, path, p_fixed, p_h, actions, eta, wall="right", compression=True):
        self.path = path
        self.eta = float(eta)
        self.wall = wall
        zero = np.zeros((len(path.s), 3))
        base = supported(path, p_fixed, 0.0, actions, wall)
        unit_T = supported(path, zero, preload_to_C3(path, 1.0), (), wall)
        unit_lam = supported(path, np.asarray(p_h, dtype=float), 0.0, (), wall)
        self.base, self.unit_T, self.unit_lam = base, unit_T, unit_lam
        a = cone_forms(base["rt"], base["rnu"], eta)
        b = cone_forms(unit_T["rt"], unit_T["rnu"], eta)
        c = cone_forms(unit_lam["rt"], unit_lam["rnu"], eta)
        n = len(path.s)
        self.where = [("line", i, face) for i in range(n) for face in ("-", "+")]
        self.a, self.b, self.c = a.ravel(), b.ravel(), c.ravel()
        if compression:
            self.a = np.r_[self.a, -base["S"]]
            self.b = np.r_[self.b, -unit_T["S"]]
            self.c = np.r_[self.c, np.zeros(n)]
            self.where += [("compression", i, "") for i in range(n)]
        for k, act in enumerate(base["actions"]):
            f = cone_forms([act["Rt"]], [act["Rnu"]], eta).ravel()
            self.a = np.r_[self.a, f]
            self.b = np.r_[self.b, 0.0, 0.0]
            self.c = np.r_[self.c, 0.0, 0.0]
            self.where += [("point", k, "-"), ("point", k, "+")]
        # unit horizontal loads turned to any direction: c(beta) = cos(beta) cx + sin(beta) cy
        self._dir = None

    def describe(self, index):
        if index is None or index < 0:
            return "bound of the range"
        kind, i, face = self.where[index]
        path = self.path
        if kind == "point":
            return "point action %d" % (i + 1)
        at = "s = %.4g m" % path.s[i]
        if path.theta is not None:
            at += ", θ = %.4g rad" % path.theta[i]
        if kind == "compression":
            return "compression at %s" % at
        return "cone side %s at %s" % ("rₜ ≤ η r_ν" if face == "-" else "−rₜ ≤ η r_ν", at)

    def location(self, index):
        if index is None or index < 0:
            return None
        kind, i, _ = self.where[index]
        return None if kind == "point" else i

    def preload_interval(self, lam):
        """Admissible preloads T >= 0 at the multiplier lam."""
        r = interval(self.a + lam * self.c, self.b, lower=0.0)
        return None if r is None else dict(lo=r[0], hi=r[1], governing_lo=r[2], governing_hi=r[3])

    def multiplier_interval(self, T):
        """Admissible multipliers lam at the preload T."""
        r = interval(self.a + T * self.b, self.c)
        return None if r is None else dict(lo=r[0], hi=r[1], governing_lo=r[2], governing_hi=r[3])

    def region(self, T_range, lam_range, rows=241):
        """Boundary of the convex admissible region in the (T, lam) plane within a window.

        For each of `rows` multipliers the admissible preloads form an
        interval (one vectorised pass over all the forms). The left ends
        and the right ends, in order, outline the convex region.
        """
        T0, T1 = map(float, T_range)
        lams = np.linspace(float(lam_range[0]), float(lam_range[1]), int(rows))
        A = self.a[None, :] + lams[:, None] * self.c[None, :]
        b = self.b
        pos, neg = b > EPS, b < -EPS
        flat = ~(pos | neg)
        lo = np.full(len(lams), T0)
        hi = np.full(len(lams), T1)
        if np.any(pos):
            lo = np.maximum(lo, np.max(-A[:, pos] / b[pos], axis=1))
        if np.any(neg):
            hi = np.minimum(hi, np.min(-A[:, neg] / b[neg], axis=1))
        ok = lo <= hi
        if np.any(flat):
            tol = 1e-9 * max(float(np.max(np.abs(self.a))), 1.0)
            ok &= np.all(A[:, flat] >= -tol, axis=1)
        idx = np.where(ok)[0]
        if not len(idx):
            return np.zeros((0, 2))
        left = np.column_stack((lo[idx], lams[idx]))
        right = np.column_stack((hi[idx], lams[idx]))[::-1]
        return np.vstack([left, right])

    # ------------------------------------------------------------ loads turned to a direction
    def _directional(self, profile):
        """Forms of a unit horizontal load profile(s) along e1 and along e2."""
        if self._dir is None or self._dir[0] is not profile:
            path = self.path
            out = []
            for d in (np.array([1.0, 0.0, 0.0]), np.array([0.0, 1.0, 0.0])):
                p = profile[:, None] * d[None, :]
                st = supported(path, p, 0.0, (), self.wall)
                f = cone_forms(st["rt"], st["rnu"], self.eta).ravel()
                n_extra = len(self.a) - len(f)
                out.append(np.r_[f, np.zeros(n_extra)])
            self._dir = (profile, out[0], out[1])
        return self._dir[1], self._dir[2]

    def critical_load(self, T, profile, beta, lam_cap=np.inf):
        """Largest multiplier of profile(s) d(beta) admissible at the preload T (0 if none)."""
        cx, cy = self._directional(profile)
        c = np.cos(beta) * cx + np.sin(beta) * cy
        r = interval(self.a + T * self.b, c, lower=0.0, upper=lam_cap)
        return None if r is None else r[1]

    def minimum_preload(self, lam, profile=None, beta=None):
        """Least admissible preload at the multiplier lam (None if no preload is admissible)."""
        if profile is None:
            c = self.c
        else:
            cx, cy = self._directional(profile)
            c = np.cos(beta) * cx + np.sin(beta) * cy
        r = interval(self.a + lam * c, self.b, lower=0.0)
        return None if r is None else (r[0], r[2])


# ---------------------------------------------------------------- Appendix A: exact circle

def minimum_preload_circle(hx, hy, radius, grade, weight, eta, theta_end, details=False):
    """Exact finite-candidate reduction of the continuum contact test on a circle.

    Descending constant-grade circular helix (grade < 0) from theta = 0 to
    theta_end, p3 = -weight, constant horizontal density (hx, hy) in the
    coordinates of the start (x1 along the start radius), r3 = 0, wall on
    the right (outside). Returns T_min, or (T_min, theta, branch).
    """
    if radius <= 0 or grade >= 0 or weight <= 0 or eta <= 0 or theta_end <= 0:
        raise ValueError("The exact bound needs R, w, eta, theta_end > 0 and a descending grade")
    h, beta = np.hypot(hx, hy), np.arctan2(hy, hx)
    q0 = weight / abs(grade)
    candidates = [(0.0, 0.0, 0)]
    amplitude = np.hypot(1.0 / eta, 1.0)
    for sign in (-1, 1):
        angles = [0.0, theta_end]
        if h * amplitude >= q0 and h > 0:
            phase = np.arctan2(1.0, sign / eta)
            alpha = np.arccos(np.clip(q0 / (h * amplitude), -1, 1))
            for base in (beta + phase - alpha, beta + phase + alpha):
                first = int(np.ceil(-base / (2 * np.pi)))
                last = int(np.floor((theta_end - base) / (2 * np.pi)))
                angles += [base + 2 * np.pi * j for j in range(first, last + 1)]
        for theta in angles:
            value = radius * (sign * q0 / eta - q0 * theta
                              + h * (sign * np.sin(theta - beta) / eta - np.cos(theta - beta)))
            candidates.append((float(value), float(theta), sign))
    best = max(candidates, key=lambda row: row[0])
    return best if details else best[0]


def critical_horizontal_circle(beta, preload, **kwargs):
    """Load-ray threshold of the exact circle bound at the preload T."""
    zero = minimum_preload_circle(0.0, 0.0, **kwargs)
    if preload <= zero:
        return 0.0

    def difference(h):
        return minimum_preload_circle(h * np.cos(beta), h * np.sin(beta), **kwargs) - preload
    upper = 1.0
    for _ in range(60):
        if difference(upper) > 0:
            return brentq(difference, 0.0, upper, xtol=1e-12)
        upper *= 2
    return np.inf
