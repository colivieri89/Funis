"""Abscissae of the projected length with the smooth pieces of a path.

A concentrated force makes the internal force jump. The grid repeats the
abscissa of such a node, so that every array holds the value before the node
(first copy) and after it (second copy), and integrals and derivatives are
taken piece by piece.
"""
import numpy as np
from scipy.integrate import cumulative_simpson

EPS = 1e-12


def piecewise_grid(length, n, nodes=()):
    """n abscissae from 0 to length, the interior nodes repeated once.

    Every piece has at least five points. A node at an end or outside the
    interval is ignored.
    """
    L = float(length)
    if L <= 0:
        raise ValueError("The projected length must be positive")
    cuts = sorted({float(v) for v in nodes if 1e-9 * L < float(v) < L * (1.0 - 1e-9)})
    edges = [0.0] + cuts + [L]
    out = []
    for a, b in zip(edges[:-1], edges[1:]):
        m = max(5, int(round(int(n) * (b - a) / L)) + 1)
        out.append(np.linspace(a, b, m))
    return np.concatenate(out)


def pieces(s):
    """Index ranges (i0, i1) of the smooth pieces: a repeated abscissa starts a piece."""
    s = np.asarray(s, dtype=float)
    cut = np.where(np.diff(s) <= 0)[0] + 1
    starts = np.r_[0, cut]
    ends = np.r_[cut, len(s)]
    return list(zip(starts.tolist(), ends.tolist()))


def after(s, node):
    """True on the pieces that follow the node (the second copy of its abscissa)."""
    s = np.asarray(s, dtype=float)
    mask = np.zeros(len(s), dtype=bool)
    for i0, i1 in pieces(s):
        if i0 > 0 and s[i0] >= float(node) - 1e-9 * max(s[-1], 1.0):
            mask[i0:i1] = True
    return mask


def node_index(s, node):
    """Index of the first copy of the abscissa of a node (the value before it)."""
    s = np.asarray(s, dtype=float)
    return int(np.argmin(np.abs(s - float(node))))


def cumulative(y, s):
    """Running integral of y over s from 0, continuous across the pieces."""
    y = np.asarray(y, dtype=float)
    s = np.asarray(s, dtype=float)
    out = np.zeros(y.shape, dtype=float)
    offset = np.zeros(y.shape[1:], dtype=float)
    for i0, i1 in pieces(s):
        seg = cumulative_simpson(y[i0:i1], x=s[i0:i1], axis=0, initial=0)
        out[i0:i1] = seg + offset
        offset = out[i1 - 1]
    return out


def integral(y, s):
    return cumulative(y, s)[-1]


def derivative(y, s):
    """Second-order derivative along s, piece by piece."""
    y = np.asarray(y, dtype=float)
    s = np.asarray(s, dtype=float)
    out = np.empty(y.shape, dtype=float)
    for i0, i1 in pieces(s):
        out[i0:i1] = np.gradient(y[i0:i1], s[i0:i1], axis=0, edge_order=2)
    return out
