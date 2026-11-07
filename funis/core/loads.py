"""Load densities as functions of the projected length, in kN per projected metre."""
import numpy as np


def polynomial(coeffs):
    """a0 + a1 s + a2 s^2 + ..., with s in m."""
    c = [float(v) for v in coeffs] or [0.0]

    def fn(s):
        if np.ndim(s) == 0:
            v = 0.0
            for ck in reversed(c):
                v = v * float(s) + ck
            return v
        s = np.asarray(s, dtype=float)
        out = np.zeros_like(s)
        for k, ck in enumerate(c):
            out = out + ck * s ** k
        return out
    fn.coeffs = c
    return fn


def polynomial_derivative(coeffs):
    c = [float(v) for v in coeffs]
    return polynomial([k * ck for k, ck in enumerate(c)][1:] or [0.0])


def table(rows):
    """Piecewise linear interpolation of (s, value) rows, constant beyond the ends."""
    r = np.asarray(rows, dtype=float)
    if r.ndim != 2 or r.shape[1] < 2 or len(r) < 1:
        raise ValueError("A table of values needs rows (s, value)")
    order = np.argsort(r[:, 0])
    xs, ys = r[order, 0], r[order, 1]

    def fn(s):
        return np.interp(np.asarray(s, dtype=float), xs, ys)
    return fn


def direction(beta_deg):
    """Horizontal unit vector at the angle beta (degrees) from e1 toward e2."""
    b = np.radians(float(beta_deg))
    return np.array([np.cos(b), np.sin(b), 0.0])
