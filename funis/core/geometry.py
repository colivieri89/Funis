"""Spatial paths described by the projected arc length s.

x*(s) = x(s) + f(s) e3 with |x_{,s}| = 1. The projected unit tangent is
t = x_{,s}, the left normal n = e3 x t, the signed projected curvature rho
(t_{,s} = rho n), the grade f_{,s} and its derivative f_{,ss}. The tangent per
unit projected length is u = t + f_{,s} e3, of length J = sqrt(1 + f_{,s}^2),
and T = u/J is the spatial unit tangent.
"""
from dataclasses import dataclass
from typing import Optional

import numpy as np
from scipy.integrate import cumulative_simpson
from scipy.interpolate import CubicSpline

from .grid import piecewise_grid

E1, E2, E3 = np.eye(3)
EPS = 1e-12


@dataclass
class Path:
    s: np.ndarray
    xyz: np.ndarray
    t: np.ndarray
    n: np.ndarray
    rho: np.ndarray
    fs: np.ndarray
    fss: np.ndarray
    theta: Optional[np.ndarray] = None
    kind: str = "path"

    @property
    def L(self):
        return float(self.s[-1])

    @property
    def J(self):
        return np.sqrt(1.0 + self.fs * self.fs)

    @property
    def u(self):
        v = self.t.copy()
        v[:, 2] = self.fs
        return v

    @property
    def T(self):
        return self.u / self.J[:, None]

    @property
    def plan(self):
        return self.xyz[:, :2]

    @property
    def developed(self):
        """Developed elevation: abscissa s and height x3."""
        return np.column_stack((self.s, self.xyz[:, 2]))


def helix(radius, pitch, theta_start, theta_end, n=1001, nodes=()):
    """Circular helix (R cos th, R sin th, c (th - th0)), th in radians, s = R (th - th0)."""
    R, c = float(radius), float(pitch)
    th0, th1 = float(theta_start), float(theta_end)
    if R <= 0 or th1 <= th0:
        raise ValueError("The helix needs R > 0 and an end angle beyond the start angle")
    s = piecewise_grid(R * (th1 - th0), n, nodes)
    th = th0 + s / R
    sn, cs = np.sin(th), np.cos(th)
    xyz = np.column_stack((R * cs, R * sn, c * (th - th0)))
    t = np.column_stack((-sn, cs, np.zeros_like(th)))
    nn = np.column_stack((-cs, -sn, np.zeros_like(th)))
    return Path(s, xyz, t, nn, np.full_like(s, 1.0 / R), np.full_like(s, c / R),
                np.zeros_like(s), th, "helix")


def ellipse(a, b, pitch, theta_start, theta_end, n=1001, mode="angle", nodes=()):
    """Elliptical helix (a cos th, b sin th, f) with f = c (th - th0) or f = k_s s.

    In angle mode pitch is c (m/rad), in arc mode it is the constant grade k_s.
    """
    a, b, c = float(a), float(b), float(pitch)
    th0, th1 = float(theta_start), float(theta_end)
    if a <= 0 or b <= 0 or th1 <= th0:
        raise ValueError("The ellipse needs a, b > 0 and an end angle beyond the start angle")
    fine = np.linspace(th0, th1, max(20 * int(n), 4001))
    g_fine = np.sqrt(a * a * np.sin(fine) ** 2 + b * b * np.cos(fine) ** 2)
    s_fine = cumulative_simpson(g_fine, x=fine, initial=0)
    s = piecewise_grid(float(s_fine[-1]), n, nodes)
    th = np.interp(s, s_fine, fine)
    sn, cs = np.sin(th), np.cos(th)
    g = np.sqrt(a * a * sn * sn + b * b * cs * cs)
    gt = (a * a - b * b) * sn * cs / g
    t = np.column_stack((-a * sn / g, b * cs / g, np.zeros_like(th)))
    nn = np.column_stack((-b * cs / g, -a * sn / g, np.zeros_like(th)))
    rho = a * b / g ** 3
    if mode == "angle":
        z, fs, fss = c * (th - th0), c / g, -c * gt / g ** 3
    elif mode == "arc":
        z, fs, fss = c * s, np.full_like(s, c), np.zeros_like(s)
    else:
        raise ValueError("mode must be angle or arc")
    return Path(s, np.column_stack((a * cs, b * sn, z)), t, nn, rho, fs, fss, th, "ellipse")


def spline_path(points, n=1001, nodes=()):
    """Smooth path through given points, parametrized by the projected length.

    A cubic spline in the chord-length parameter of the plan passes through
    the points (two points give a straight segment). The plan must not stop
    or reverse, so that the projected length is a regular parameter.
    """
    P = np.asarray(points, dtype=float)
    if P.ndim != 2 or P.shape[1] != 3 or len(P) < 2:
        raise ValueError("The table of points needs at least two rows with x1, x2, x3")
    chord = np.linalg.norm(np.diff(P[:, :2], axis=0), axis=1)
    if np.any(chord < EPS):
        raise ValueError("Two consecutive points have the same plan position")
    w = np.r_[0.0, np.cumsum(chord)]
    spline = CubicSpline(w, P, axis=0)
    fine = np.linspace(0.0, w[-1], max(20 * int(n), 4001))
    d1 = spline(fine, 1)
    speed = np.linalg.norm(d1[:, :2], axis=1)
    if np.min(speed) < 1e-6 * max(np.max(speed), EPS):
        raise ValueError("The plan of the path stops or reverses: the projected length is not regular")
    s_fine = cumulative_simpson(speed, x=fine, initial=0)
    s = piecewise_grid(float(s_fine[-1]), n, nodes)
    ww = np.interp(s, s_fine, fine)
    x = spline(ww)
    x1 = spline(ww, 1)
    x2 = spline(ww, 2)
    sp = np.linalg.norm(x1[:, :2], axis=1)
    spp = np.sum(x1[:, :2] * x2[:, :2], axis=1) / sp
    xs = x1 / sp[:, None]
    xss = (x2 * sp[:, None] - x1 * spp[:, None]) / (sp ** 3)[:, None]
    t = xs.copy()
    t[:, 2] = 0.0
    nn = np.cross(E3, t)
    rho = np.sum(xss[:, :2] * nn[:, :2], axis=1)
    return Path(s, x, t, nn, rho, xs[:, 2], xss[:, 2], None, "spline")
