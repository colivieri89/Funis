"""Plane funiculars: the catenary, the parabola and their generalisations.

The line lies in the vertical plane of e1 and e3, with abscissa x along e1
(the projected length s of the article, for a straight plan) and height
z = f(x). Loads p = (p1, p3) act on the line, per metre of x or per metre of
actual length, together with point forces G_j at x_j. The internal force
F = (F1, F3) satisfies F' + p = 0 between the nodes and jumps by -G_j at a
node, and the line is tangent to it, f' = F3 / F1. In compression the thrust
S = F1 is negative and N = -|F|; the reactions are R_A = -F(0) at the first
support and R_B = F(L) at the second.

A load q per metre of actual length gives p = q J with
J = sqrt(1 + f'^2) = |F| / |F1|, so that the force depends on the unknown
line (the catenary, for q = (0, -w)): force and line are then integrated
together as one system of ordinary differential equations.

Plane vectors are pairs (component along e1, component along e3).
"""
import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import brentq

from .grid import after, cumulative, piecewise_grid, pieces

EPS = 1e-12


def cross2(a, b):
    """Component along e2 of a x b for plane vectors, a1 b3 - a3 b1 (moment about e2, sign of x1 x3)."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    return a[..., 0] * b[..., 1] - a[..., 1] * b[..., 0]


# ---------------------------------------------------------------- grid

def plane_grid(length, n, nodes=(), extra=()):
    """Abscissae from 0 to L with the point-force nodes repeated and the extra abscissae included once.

    Returns the grid and the index of every extra abscissa.
    """
    s = piecewise_grid(length, n, nodes)
    idx = []
    for v in extra:
        v = float(v)
        i = int(np.argmin(np.abs(s - v)))
        if abs(s[i] - v) <= 1e-12 * max(length, 1.0):
            idx.append(i)
            continue
        bounds = set()
        for i0, i1 in pieces(s):
            bounds.update((i0, i1 - 1))
        if i in bounds:
            i = i + 1 if v > s[i] else i - 1
        s[i] = v
        idx.append(i)
    return s, idx


# ---------------------------------------------------------------- the line for a given initial force

def primitive(s, p, actions=()):
    """P(x): integral of p from 0 to x plus the point forces already passed."""
    P = cumulative(p, s)
    for x_j, G in actions:
        P = P + after(s, x_j)[:, None] * np.asarray(G, dtype=float)[None, :]
    return P


def _check_compression(s, F):
    scale = max(float(np.max(np.abs(F))), EPS)
    bad = np.where(F[:, 0] >= -1e-9 * scale)[0]
    if len(bad):
        raise ValueError("The horizontal force F₁ is not negative at x = %.4g m: the line would turn "
                         "vertical or go into tension there, and the projected abscissa cannot describe "
                         "it. Change the thrust or the loads." % s[bad[0]])


def line_projected(s, C, p, actions=(), z0=0.0):
    """Line and force for loads p (n, 2) per metre of x: F = C - P, z = z0 + integral of F3/F1."""
    F = np.asarray(C, dtype=float)[None, :] - primitive(s, p, actions)
    _check_compression(s, F)
    z = z0 + cumulative(F[:, 1] / F[:, 0], s)
    return dict(s=s, z=z, F=F, p=np.asarray(p, dtype=float))


def line_actual(s, C, q, p=None, actions=(), z0=0.0, rtol=1e-11):
    """Line and force for loads q(x) per metre of actual length and p(x) per metre of x.

    q and p are functions of x returning a plane vector for a number x and an
    (n, 2) array for an array x. The system
    F1' = -(p1 + q1 J), F3' = -(p3 + q3 J), z' = F3 / F1 with J = |F| / |F1|
    is integrated piece by piece, the force jumping by -G at the nodes.
    """
    s = np.asarray(s, dtype=float)
    zero = np.zeros(2)
    pf = p if p is not None else (lambda x: zero if np.ndim(x) == 0 else np.zeros((len(x), 2)))
    scale = max(float(np.linalg.norm(C)), EPS)

    def rhs(x, y):
        F1, F3 = y[0], y[1]
        J = np.hypot(F1, F3) / max(abs(F1), 1e-300)
        qq = q(x)
        pp = pf(x)
        return [-(pp[0] + qq[0] * J), -(pp[1] + qq[1] * J), F3 / F1]

    def vertical(x, y):
        return y[0] + 1e-9 * scale
    vertical.terminal = True
    vertical.direction = 1

    y0 = np.array([C[0], C[1], z0], dtype=float)
    jumps = {}
    for x_j, G in actions:
        jumps[float(x_j)] = jumps.get(float(x_j), zero) + np.asarray(G, dtype=float)
    out = np.zeros((len(s), 3))
    for k, (i0, i1) in enumerate(pieces(s)):
        if k > 0:
            node = s[i0]
            G = sum((v for xj, v in jumps.items() if abs(xj - node) <= 1e-9 * max(s[-1], 1.0)), zero)
            y0 = y0.copy()
            y0[:2] -= G
        if y0[0] >= -1e-9 * scale:
            raise ValueError("The horizontal force F₁ is not negative at x = %.4g m." % s[i0])
        xs = s[i0:i1]
        if len(xs) == 1 or xs[-1] <= xs[0]:
            out[i0:i1] = y0
            continue
        sol = solve_ivp(rhs, (xs[0], xs[-1]), y0, t_eval=xs, method="DOP853", rtol=rtol,
                        atol=1e-12 * max(scale, abs(z0), 1.0), events=vertical)
        if sol.status != 0 or sol.y.shape[1] != len(xs):
            where = sol.t_events[0][0] if sol.t_events and len(sol.t_events[0]) else xs[-1]
            raise ValueError("The horizontal force F₁ vanishes near x = %.4g m: the line turns vertical "
                             "and the projected abscissa cannot describe it. Change the thrust or the "
                             "loads." % where)
        out[i0:i1] = sol.y.T
        y0 = sol.y[:, -1]
    F = out[:, :2]
    _check_compression(s, F)
    J = np.linalg.norm(F, axis=1) / np.abs(F[:, 0])
    qv = np.asarray(q(s), dtype=float)
    pv = np.asarray(pf(s), dtype=float)
    return dict(s=s, z=out[:, 2], F=F, p=pv + qv * J[:, None], J=J)


# ---------------------------------------------------------------- selection of the line

class LineProblem:
    """The plane funicular between A = (0, z0) and B = (L, zB) for the given loads.

    proj(x) and actual(x) return the loads per metre of x and per metre of
    actual length, a plane vector for a number x and (n, 2) for an array x;
    actual may be None. The line follows
    from its initial force C = F(0), or from the thrust H = -F1(0) with the
    second support, or from a point (x_c, z_c) with the second support.
    """

    def __init__(self, s, proj, actual=None, actions=(), z0=0.0, zB=0.0):
        self.s = np.asarray(s, dtype=float)
        self.proj = proj
        self.actual = actual
        self.actions = list(actions)
        self.z0 = float(z0)
        self.zB = float(zB)
        self.p_grid = np.asarray(proj(self.s), dtype=float)
        self.L = float(self.s[-1])
        total = float(np.sum(np.abs(self.p_grid))) * self.L / max(len(self.s), 1)
        total += sum(float(np.linalg.norm(G)) for _, G in self.actions)
        if actual is not None:
            q = np.asarray(actual(self.s), dtype=float)
            total += float(np.mean(np.linalg.norm(q, axis=1))) * self.L
        self.load_scale = max(total, EPS)

    def line(self, C):
        C = np.asarray(C, dtype=float)
        if self.actual is None:
            return line_projected(self.s, C, self.p_grid, self.actions, self.z0)
        return line_actual(self.s, C, self.actual, self.proj, self.actions, self.z0)

    # projected loads: z(L) is affine in C3 at a fixed C1
    def _c3_projected(self, C1, J=None):
        p = self.p_grid if J is None else self.p_grid + np.asarray(self.actual(self.s)) * J[:, None]
        P = primitive(self.s, p, self.actions)
        F1 = C1 - P[:, 0]
        _check_compression(self.s, np.column_stack((F1, np.zeros_like(F1))))
        a = cumulative(1.0 / F1, self.s)[-1]
        b = cumulative(P[:, 1] / F1, self.s)[-1]
        return (self.zB - self.z0 + b) / a, p

    def through_end(self, H, guess=None):
        """C3 that takes the line with thrust H = -F1(0) to the second support."""
        C1 = -float(H)
        if H <= 0:
            raise ValueError("The thrust H must be positive (compression)")
        if self.actual is None:
            return np.array([C1, self._c3_projected(C1)[0]])
        C3 = self._approximate(C1)[1] if guess is None else float(guess)

        def miss(c3):
            try:
                return self.line((C1, c3))["z"][-1] - self.zB
            except ValueError:
                return np.nan
        step = 0.05 * max(abs(C3), H, 1e-3 * self.load_scale)
        lo, hi = C3 - step, C3 + step
        flo, fhi = miss(lo), miss(hi)
        for _ in range(60):
            if np.isfinite(flo) and np.isfinite(fhi) and flo * fhi <= 0:
                break
            step *= 1.8
            lo, hi = C3 - step, C3 + step
            flo, fhi = miss(lo), miss(hi)
        else:
            raise ValueError("No line with the thrust H = %.4g kN reaches the second support" % H)
        return np.array([C1, brentq(miss, lo, hi, xtol=1e-13 * max(1.0, abs(C3)), rtol=1e-14,
                                    maxiter=200)])

    def _approximate(self, C1):
        """Initial force for a weight per actual length, from lines with a frozen J (a few passes)."""
        J = np.ones(len(self.s))
        C3 = 0.0
        for _ in range(6):
            C3, p = self._c3_projected(C1, J)
            F = np.column_stack((C1 - primitive(self.s, p, self.actions)[:, 0],
                                 C3 - primitive(self.s, p, self.actions)[:, 1]))
            J = np.linalg.norm(F, axis=1) / np.abs(F[:, 0])
        return np.array([C1, C3])

    def through_point(self, index, zc, tol=1e-12):
        """Initial force of the line through the sample `index` at height zc and the second support."""
        xc = float(self.s[index])
        if not (0.0 < xc < self.L):
            raise ValueError("The point must lie between the supports (0 < x_c < L)")

        def height(H):
            C = self.through_end(H)
            if self.actual is None:
                return line_projected(self.s, C, self.p_grid, self.actions, self.z0)["z"][index]
            return self.line(C)["z"][index]

        if self.actual is None:
            target = zc
            Hs = np.geomspace(1e-6, 1e6, 49) * self.load_scale
            vals = []
            for H in Hs:
                try:
                    vals.append(height(H) - target)
                except ValueError:
                    vals.append(np.nan)
            vals = np.array(vals)
            for k in range(len(Hs) - 1):
                a, b = vals[k], vals[k + 1]
                if np.isfinite(a) and np.isfinite(b) and a * b <= 0:
                    H = brentq(lambda h: height(h) - target, Hs[k], Hs[k + 1], xtol=1e-14 * Hs[k + 1],
                               rtol=1e-15, maxiter=300)
                    return self.through_end(H)
            raise ValueError("No compressive line through (%.4g m, %.4g m) reaches both supports" % (xc, zc))
        # weight per actual length: start from the line with a frozen J, then Newton on (C1, C3)
        J = np.ones(len(self.s))
        for _ in range(3):
            frozen = LineProblem(self.s, lambda x, J=J: self.proj(x) + np.asarray(self.actual(x)) * J[:, None],
                                 None, self.actions, self.z0, self.zB)
            C = frozen.through_point(index, zc)
            F = frozen.line(C)["F"]
            J = np.linalg.norm(F, axis=1) / np.abs(F[:, 0])

        def residual(c):
            ln = self.line(c)
            return np.array([ln["z"][index] - zc, ln["z"][-1] - self.zB])
        r = residual(C)
        size = max(abs(zc - self.z0), abs(self.zB - self.z0), self.L, 1e-9)
        for _ in range(40):
            if np.max(np.abs(r)) < tol * size:
                break
            J = np.zeros((2, 2))
            for k in range(2):
                h = 1e-7 * max(abs(C[k]), 1e-3 * self.load_scale)
                d = np.zeros(2)
                d[k] = h
                J[:, k] = (residual(C + d) - residual(C - d)) / (2 * h)
            step = np.linalg.solve(J, -r)
            t = 1.0
            while t > 1e-4:
                try:
                    rn = residual(C + t * step)
                    if np.max(np.abs(rn)) < np.max(np.abs(r)):
                        break
                except ValueError:
                    pass
                t *= 0.5
            C = C + t * step
            r = residual(C)
        if np.max(np.abs(r)) > 1e-8 * size:
            raise ValueError("The line through the point did not converge (mismatch %.3g m)" % np.max(np.abs(r)))
        return C


# ---------------------------------------------------------------- closed forms

def parabola(x, C, p3, z0=0.0):
    """Constant vertical density p3 per metre of x, no horizontal load: z = z0 + (C3 x - p3 x^2 / 2) / C1."""
    x = np.asarray(x, dtype=float)
    return z0 + (C[1] * x - 0.5 * p3 * x ** 2) / C[0]


def log_branch(x, C, h, p3, z0=0.0):
    """Constant densities h along e1 and p3 per metre of x (Appendix B, B = 0, sigma = -1).

    A = C1 - h x, z = z0 - (Cbar / h) log(A / C1) + (p3 / h) x with Cbar = C3 - p3 C1 / h.
    """
    x = np.asarray(x, dtype=float)
    A = C[0] - h * x
    Cbar = C[1] - p3 * C[0] / h
    return z0 - (Cbar / h) * np.log(A / C[0]) + (p3 / h) * x


def catenary(x, C, w, z0=0.0):
    """Weight w per metre of actual length, no horizontal load: z = z_c - a cosh((x - x_c) / a).

    a = H / w with H = -C1, x_c = a arsinh(C3 / C1) and z_c = z0 + a cosh(x_c / a).
    """
    x = np.asarray(x, dtype=float)
    H = -C[0]
    a = H / w
    xc = a * np.arcsinh(C[1] / C[0])
    zc = z0 + a * np.cosh(xc / a)
    return zc - a * np.cosh((x - xc) / a)


def inclined_catenary(x, C, w, gamma, z0=0.0):
    """Load (gamma w, -w) per metre of actual length, of fixed direction: a catenary with an inclined axis.

    With g = w (gamma, -1) the force along the arc length sigma is F = C - g sigma, and the line
    follows r' = -F / |F|. In the frame u = g / |g|, v normal to u, F = A u + b v with
    A = a - |g| sigma, so that
    r(sigma) = r0 + u (|F| - |C|) / |g| + v (b / |g|) (arsinh(A / |b|) - arsinh(a / |b|)).
    The heights at the abscissae x follow by solving x1(sigma) = x with Newton's method.
    """
    x = np.asarray(x, dtype=float)
    C = np.asarray(C, dtype=float)
    g = w * np.array([gamma, -1.0])
    gn = float(np.linalg.norm(g))
    u = g / gn
    v = np.array([-u[1], u[0]])
    a, b = float(C @ u), float(C @ v)
    c0 = float(np.hypot(a, b))

    def point(sig):
        A = a - gn * sig
        F = np.sqrt(A ** 2 + b ** 2)
        r = (np.array([0.0, z0])[None, :] + u[None, :] * ((F - c0) / gn)[:, None]
             + v[None, :] * ((b / gn) * (np.arcsinh(A / abs(b)) - np.arcsinh(a / abs(b))))[:, None])
        dr = -(A[:, None] * u[None, :] + b * v[None, :]) / F[:, None]
        return r, dr

    top = 2.0 * (float(np.max(x)) + 1.0)
    while True:
        sig = np.linspace(0.0, top, 4001)
        r, _ = point(sig)
        if r[-1, 0] >= np.max(x) or top > 1e8:
            break
        top *= 2.0
    s = np.interp(x, r[:, 0], sig)
    for _ in range(8):
        r, dr = point(s)
        s = s - (r[:, 0] - x) / dr[:, 0]
    return point(s)[0][:, 1]
