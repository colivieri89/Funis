"""Views and graphs of every task as Drawing objects.

Plans and developed elevations are drawn to scale (lengths in m), with the
horizontal densities as arrows at a density scale (m per kN/m): loads start
from the line and reactions end on it, since they act on the line. Graphs of
forces, reactions and margins along the path are labelled directly at their
curves, so that no legend covers them.
"""
import numpy as np

from .core.grid import pieces
from .drawing import Drawing

SUB = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")
MAX_POINTS = 700

GROUPS = {
    "views": ("plan", "elevation", "node_plan", "node_elevation", "polygon", "iterates", "funicular",
              "arch_lines", "arch_loads", "arch_collapse", "arch_gsf", "arch_thickness"),
    "graphs": ("forces", "reactions", "loads", "residual", "curvature", "plane", "newton", "eccentricity",
               "arch_forces"),
    "contact": ("margin", "cone", "domain", "preload", "region", "thrust_domain"),
}
"""Drawings shown together in the tabs of the window, in this order."""


def sub(i):
    return str(i).translate(SUB)


def _unit(v):
    v = np.asarray(v, dtype=float)
    s = np.linalg.norm(v)
    return v / s if s > 1e-12 else v


def _left(v):
    v = _unit(v)
    return np.array([-v[1], v[0]])


def thin(n, s=None, limit=MAX_POINTS):
    """Indices of at most `limit` samples, keeping the ends of every smooth piece."""
    if n <= limit:
        return np.arange(n)
    if s is None:
        idx = np.unique(np.round(np.linspace(0, n - 1, limit)).astype(int))
        return idx
    out = []
    for i0, i1 in pieces(s):
        m = max(2, int(round(limit * (i1 - i0) / n)))
        out.append(np.unique(np.round(np.linspace(i0, i1 - 1, m)).astype(int)))
    return np.concatenate(out)


def density_scale(span, max_density, fraction=0.2):
    """Metres per kN/m that make the largest density arrow a fraction of the span."""
    return fraction * max(span, 1e-9) / max(max_density, 1e-9)


def force_scale(span, max_force, fraction=0.12):
    """Metres per kN that make the largest point force a fraction of the span."""
    return fraction * max(span, 1e-9) / max(max_force, 1e-9)


def stations_for_arrows(s, count=10, nodes=()):
    """Indices of evenly spaced interior samples for the density arrows."""
    L = s[-1]
    targets = np.linspace(0.0, L, count + 2)[1:-1]
    idx = sorted({int(np.argmin(np.abs(s - v))) for v in targets})
    return [i for i in idx if all(abs(s[i] - a) > 0.02 * L for a in nodes)]


# ---------------------------------------------------------------- plan and elevation

def plan(xyz, title="Plan", s=None, loads=None, reactions=None, reactions_vertical=None,
         point_loads=(), point_reactions=(), ds=1.0, fs=1.0, wall=None, normals=None,
         marks=(), arrow_at=None):
    """Horizontal projection with horizontal loads and reactions at the density scale ds."""
    d = Drawing(title, unit="m", xlabel="x₁ [m]", ylabel="x₂ [m]")
    X = np.asarray(xyz, dtype=float)[:, :2]
    k = thin(len(X), s)
    span = max(np.ptp(X, axis=0).max(), 1e-9)
    if wall is not None and normals is not None:
        side = -1.0 if wall == "right" else 1.0
        off = 0.045 * span
        W = X[k] + side * off * np.asarray(normals)[k, :2]
        d.polyline(W, role="light", width=3.0, layer="wall")
    d.polyline(X[k], role="ink", width=1.7, layer="path")
    d.marker(X[0], role="ink", size=5.0)
    d.marker(X[-1], role="ink", size=5.0, filled=False)
    gap = 0.04 * span
    t0 = X[min(1, len(X) - 1)] - X[0]
    t1 = X[-1] - X[max(len(X) - 2, 0)]
    d.text(X[0], "start", offset=tuple(-gap * _unit(t0)), size=8.5)
    d.text(X[-1], "end", offset=tuple(gap * _unit(t1)), size=8.5)
    idx = arrow_at if arrow_at is not None else []
    drew_h = drew_r = drew_r0 = False
    if reactions_vertical is not None:
        for i in idx:
            r = np.asarray(reactions_vertical[i, :2]) * ds
            if np.linalg.norm(r) > 1e-9 * span:
                d.arrow(X[i] - r, X[i], role="reaction", width=1.0, style="dashed",
                        layer="reactions of the vertical loads")
                drew_r0 = True
    if reactions is not None:
        for i in idx:
            r = np.asarray(reactions[i, :2]) * ds
            if np.linalg.norm(r) > 1e-9 * span:
                d.arrow(X[i] - r, X[i], role="reaction", width=1.3, layer="reactions")
                if not drew_r:
                    d.text(X[i] - r, "rₕ", role="reaction", offset=tuple(-gap * _unit(r)), size=9)
                drew_r = True
    if loads is not None:
        for i in idx:
            ph = np.asarray(loads[i, :2]) * ds
            if np.linalg.norm(ph) > 1e-9 * span:
                d.arrow(X[i], X[i] + ph, role="horizontal", width=1.3, layer="horizontal loads")
                if not drew_h:
                    d.text(X[i] + ph, "pₕ", role="horizontal", offset=tuple(gap * _unit(ph)), size=9)
                drew_h = True
    for j, (x, G) in enumerate(point_loads):
        g = np.asarray(G[:2]) * fs
        x = np.asarray(x)[:2]
        if np.linalg.norm(g) > 1e-9 * span:
            d.arrow(x, x + g, role="horizontal", width=1.6, layer="point loads")
        d.marker(x, role="horizontal", size=4.5)
        d.text(x, "G" + sub(j + 1), role="horizontal", offset=(0.0, gap), size=9)
    for j, (x, R) in enumerate(point_reactions):
        r = np.asarray(R[:2]) * fs
        x = np.asarray(x)[:2]
        if np.linalg.norm(r) > 1e-9 * span:
            d.arrow(x - r, x, role="reaction", width=1.6, layer="point reactions")
            d.text(x - r, "R" + sub(j + 1), role="reaction", offset=tuple(-gap * _unit(r)), size=9)
    for x, text, role in marks:
        d.marker(np.asarray(x)[:2], role=role, size=4.5)
        d.text(np.asarray(x)[:2], text, role=role, offset=(0.0, gap), size=8.5)
    notes = []
    if drew_h or drew_r:
        notes.append("Densities drawn at 1 kN/m = %.3g m." % ds)
    if drew_r0:
        notes.append("Dashed: reactions of the vertical loads alone.")
    if point_loads or point_reactions:
        notes.append("Point forces drawn at 1 kN = %.3g m." % fs)
    d.notes.extend(notes)
    return d


def elevation(s, xyz, title="Developed elevation", nodes=(), extra=()):
    """Height x3 against the projected length s, to scale (the plan unrolled)."""
    d = Drawing(title, unit="m", xlabel="s [m]", ylabel="x₃ [m]")
    s = np.asarray(s, dtype=float)
    z = np.asarray(xyz, dtype=float)[:, 2]
    k = thin(len(s), s)
    d.polyline(np.column_stack((s[k], z[k])), role="ink", width=1.7, layer="path")
    d.polyline([[s[0], min(z.min(), 0.0)], [s[-1], min(z.min(), 0.0)]], role="light", width=0.8,
               layer="datum")
    d.marker((s[0], z[0]), role="ink", size=5.0)
    d.marker((s[-1], z[-1]), role="ink", size=5.0, filled=False)
    for j, sj in enumerate(nodes):
        i = int(np.argmin(np.abs(s - sj)))
        d.marker((s[i], z[i]), role="horizontal", size=4.5)
        span = max(np.ptp(s), np.ptp(z), 1e-9)
        d.text((s[i], z[i]), "G" + sub(j + 1), role="horizontal", offset=(0.0, 0.05 * span), size=9)
    for ss, zz, role, style in extra:
        kk = thin(len(ss))
        d.polyline(np.column_stack((np.asarray(ss)[kk], np.asarray(zz)[kk])), role=role, width=1.0,
                   style=style)
    return d


# ---------------------------------------------------------------- graphs along the path

def graph(title, x, series, xlabel, ylabel, s=None, zero=True, shade_below=False, xticks=None,
          markers=(), ylim=None):
    """Curves y(x) labelled directly: series = [(y, label, role, style)].

    Every smooth piece of s is a separate line, so that the jumps at the point
    actions are not bridged. shade_below shades the band below zero (a
    violated condition). markers: [(x, y, text, role)].
    """
    d = Drawing(title, unit="", xlabel=xlabel, ylabel=ylabel, aspect="auto", xticks=xticks)
    x = np.asarray(x, dtype=float)
    ys = [np.asarray(y, dtype=float) for y, *_ in series]
    finite = np.concatenate([y[np.isfinite(y)] for y in ys] + [np.zeros(0)])
    if not finite.size:
        finite = np.zeros(1)
    lo, hi = float(np.min(finite)), float(np.max(finite))
    if zero:
        lo, hi = min(lo, 0.0), max(hi, 0.0)
    if ylim is not None:
        lo, hi = ylim
    if hi - lo <= 1e-9 * max(1.0, abs(hi), abs(lo)):
        lo, hi = lo - 1.0, hi + 1.0
    pad = 0.1 * (hi - lo)
    d.ylim = (lo - pad, hi + pad)
    d.xlim = (float(np.min(x)), float(np.max(x)))
    if shade_below and lo < 0:
        d.fill([[d.xlim[0], lo - pad], [d.xlim[1], lo - pad], [d.xlim[1], 0.0], [d.xlim[0], 0.0]],
               role="violation", layer="violation")
    if zero and lo < 0 < hi:
        d.polyline([[d.xlim[0], 0.0], [d.xlim[1], 0.0]], role="gray", width=0.6, layer="zero")
    parts = pieces(s) if s is not None else [(0, len(x))]
    n = len(series)
    rise = 0.06 * (hi - lo + 2 * pad)
    for j, (y, label, role, style) in enumerate(series):
        y = np.asarray(y, dtype=float)
        for i0, i1 in parts:
            k = i0 + thin(i1 - i0, None, max(24, int(MAX_POINTS * (i1 - i0) / len(x))))
            good = k[np.isfinite(y[k])]
            if len(good) > 1:
                d.polyline(np.column_stack((x[good], y[good])), role=role, width=1.5, style=style,
                           layer=label or "curve")
        if label:
            frac = (0.15 + 0.7 * j / max(n - 1, 1)) if n > 1 else 0.5
            ok = np.where(np.isfinite(y))[0]
            if len(ok):
                i = ok[min(int(round(frac * (len(ok) - 1))), len(ok) - 1)]
                d.text((x[i], y[i]), label, role=role, offset=(0.0, rise), size=9)
    for xm, ym, text, role in markers:
        d.marker((xm, ym), role=role, size=4.5)
        if text:
            d.text((xm, ym), text, role=role, offset=(0.0, rise), size=8.5)
    return d


def cone(rt, rnu, eta, title="Contact cone", s=None, nu="rₙ"):
    """Path of the reaction (r_t, r_nu) along the line, with the cone |r_t| <= eta r_nu."""
    d = Drawing(title, unit="kN/m", xlabel="rₜ [kN/m]", ylabel="%s [kN/m]" % nu)
    rt = np.asarray(rt, dtype=float)
    rnu = np.asarray(rnu, dtype=float)
    top = max(float(np.max(rnu)), float(np.max(np.abs(rt))) / max(eta, 1e-9), 1e-6) * 1.08
    w = eta * top
    d.fill([[0.0, 0.0], [w, top], [-w, top]], role="cone", layer="cone")
    d.polyline([[-w, top], [0.0, 0.0], [w, top]], role="gray", width=0.9, layer="cone")
    d.text((w, top), "|rₜ| = η %s" % nu, role="gray", offset=(0.06 * top, 0.0), size=8.5)
    k = thin(len(rt), s)
    for i0, i1 in (pieces(s) if s is not None else [(0, len(rt))]):
        kk = k[(k >= i0) & (k < i1)]
        if len(kk) > 1:
            d.polyline(np.column_stack((rt[kk], rnu[kk])), role="reaction", width=1.5, layer="reaction")
    d.marker((rt[0], rnu[0]), role="reaction", size=5.0)
    d.marker((rt[-1], rnu[-1]), role="reaction", size=5.0, filled=False)
    gap = 0.06 * top
    d.text((rt[0], rnu[0]), "start", role="reaction", offset=(0.0, -gap), size=8.5)
    d.text((rt[-1], rnu[-1]), "end", role="reaction", offset=(0.0, gap), size=8.5)
    d.notes.append("Inside the shaded cone the reaction satisfies %s ≥ 0 and |rₜ| ≤ η %s, η = %.4g." % (nu, nu, eta))
    return d


def region(vertices, T, lam, T_range, lam_range, title="Admissible preload and load multiplier"):
    d = Drawing(title, unit="", xlabel="preload T [kN]", ylabel="multiplier λ", aspect="auto")
    d.xlim = tuple(T_range)
    d.ylim = tuple(lam_range)
    if len(vertices):
        d.fill(vertices, role="cone", layer="admissible")
        d.polyline(vertices, role="ink", width=1.3, closed=True, layer="admissible")
        c = np.mean(vertices, axis=0)
        d.text(c, "admissible", role="ink", size=9)
    d.marker((T, lam), role="reaction", size=5.5)
    d.text((T, lam), "model", role="reaction", offset=(0.0, 0.07 * (lam_range[1] - lam_range[0])), size=8.5)
    return d


def load_domain(points, current, unit_label, title="Admissible horizontal loads"):
    """Polygon of the admissible horizontal loads turned around at the fixed preload."""
    d = Drawing(title, unit="", xlabel="%s along e₁" % unit_label, ylabel="%s along e₂" % unit_label)
    P = np.asarray(points, dtype=float)
    d.fill(P, role="cone", layer="admissible")
    d.polyline(P, role="ink", width=1.4, closed=True, layer="boundary")
    span = max(np.ptp(P, axis=0).max(), 1e-9)
    d.polyline([[-0.06 * span, 0.0], [0.06 * span, 0.0]], role="gray", width=0.7)
    d.polyline([[0.0, -0.06 * span], [0.0, 0.06 * span]], role="gray", width=0.7)
    d.marker((0.0, 0.0), role="ink", size=4.5)
    if current is not None:
        d.marker(current, role="reaction", size=5.5)
        d.text(current, "model", role="reaction", offset=(0.05 * span, 0.05 * span), size=8.5)
    return d


# ---------------------------------------------------------------- form-finding

def newton(history, title="Endpoint correction"):
    it = np.array([h["iteration"] for h in history], dtype=float)
    e = np.log10(np.maximum([h["error"] for h in history], 1e-16))
    d = Drawing(title, unit="", xlabel="force update", ylabel="log₁₀ (endpoint mismatch / 1 m)",
                aspect="auto")
    d.polyline(np.column_stack((it, e)), role="ink", width=1.3, markers=True)
    d.xlim = (-0.3, max(it[-1], 1.0) + 0.3)
    d.ylim = (min(e.min(), -1.0) - 0.8, max(e.max(), 0.0) + 0.8)
    d.xticks = [(float(v), "%d" % v) for v in it]
    return d


def iterates_elevation(curves, s, title="Elevations of the successive estimates"):
    d = Drawing(title, unit="m", xlabel="s [m]", ylabel="x₃ [m]")
    k = thin(len(s), s)
    for j, xyz in enumerate(curves):
        last = j == len(curves) - 1
        d.polyline(np.column_stack((s[k], xyz[k, 2])), role="ink" if last else "gray",
                   width=1.7 if last else 0.9, style="solid" if last else "dashed")
    return d


# ---------------------------------------------------------------- node

def node_projection(res, axes=(0, 1), title="Node, plan", segment=2.0, fs=1.0):
    a, b = axes
    names = "x₁ x₂ x₃".split()
    d = Drawing(title, unit="m", xlabel=names[a] + " [m]", ylabel=names[b] + " [m]")
    O = np.zeros(2)
    Pm = -segment * res["Tm"][[a, b]]
    Pp = segment * res["Tp"][[a, b]]
    d.polyline([Pm, O, Pp], role="ink", width=1.8, layer="members")
    d.marker(O, role="ink", size=5.0)
    gap = 0.06 * segment
    d.text(Pm, "member −", offset=tuple(-gap * _unit(Pm)) if np.linalg.norm(Pm) > 1e-9 else (0, gap), size=8.5)
    d.text(Pp, "member +", offset=tuple(gap * _unit(Pp)) if np.linalg.norm(Pp) > 1e-9 else (0, gap), size=8.5)
    G = res["G"][[a, b]] * fs
    if np.linalg.norm(G) > 1e-9:
        d.arrow(O, G, role="horizontal", width=1.5, layer="point force")
        d.text(G, "G", role="horizontal", offset=tuple(gap * _unit(G)), size=9)
    R = res["R"][[a, b]] * fs
    if np.linalg.norm(R) > 1e-9:
        d.arrow(-R, O, role="reaction", width=1.5, layer="point reaction")
        d.text(-R, "R", role="reaction", offset=tuple(-gap * _unit(R)), size=9)
    d.notes.append("Forces drawn at 1 kN = %.3g m." % fs)
    return d


def node_polygon(res, title="Force polygon"):
    """Closed polygon -F⁻ + G + R + F⁺ = 0 in the plane of the forces (kN, to one scale)."""
    Fm, G, R = res["Fm"], res["G"], res["R"]
    e1 = _unit(-Fm)
    gn = (G + R) - np.sum((G + R) * e1) * e1
    if np.linalg.norm(gn) < 1e-9 * max(np.linalg.norm(G + R), 1.0):
        trial = np.array([0.0, 0.0, 1.0]) if abs(e1[2]) < 0.9 else np.array([1.0, 0.0, 0.0])
        gn = trial - np.sum(trial * e1) * e1
    e2 = _unit(gn)

    def P(v):
        return np.array([np.sum(v * e1), np.sum(v * e2)])
    d = Drawing(title, unit="kN", xlabel="along −F⁻ [kN]", ylabel="normal component of G [kN]")
    A = np.zeros(2)
    B = P(-Fm)
    C = B + P(G)
    D = C + P(R)
    d.arrow(A, B, role="ink", width=1.5)
    d.arrow(B, C, role="horizontal", width=1.5)
    if np.linalg.norm(P(R)) > 1e-9:
        d.arrow(C, D, role="reaction", width=1.5)
        d.text(0.5 * (C + D), "R", role="reaction", offset=tuple(0.08 * _left(D - C)), size=9)
    d.arrow(D, A, role="ink", width=1.5)
    span = max(np.linalg.norm(B), np.linalg.norm(C), 1e-9)
    gap = 0.07 * span
    d.text(0.5 * (A + B), "−F⁻", offset=tuple(-gap * _left(B - A)), size=9)
    d.text(0.5 * (B + C), "G", role="horizontal", offset=tuple(-gap * _left(C - B)), size=9)
    d.text(0.5 * (D + A), "F⁺", offset=tuple(-gap * _left(A - D)), size=9)
    return d


# ---------------------------------------------------------------- plane funicular

def funicular_view(x, z, title="Plane funicular", p=None, arrow_at=(), ds=1.0, point_loads=(), fs=1.0,
                   reactions=(), marks=()):
    """Elevation of a plane line to scale, with the load densities, the point loads and the reactions.

    Vertical densities end on the line (they act on it from above), horizontal
    densities start from it, reactions end at the supports.
    """
    d = Drawing(title, unit="m", xlabel="x₁ [m]", ylabel="x₃ [m]")
    x = np.asarray(x, dtype=float)
    z = np.asarray(z, dtype=float)
    k = thin(len(x), x)
    for i0, i1 in pieces(x):
        kk = k[(k >= i0) & (k < i1)]
        d.polyline(np.column_stack((x[kk], z[kk])), role="ink", width=1.8, layer="line")
    span = max(np.ptp(x), np.ptp(z), 1e-9)
    gap = 0.04 * span
    for X, name in (((x[0], z[0]), "A"), ((x[-1], z[-1]), "B")):
        d.marker(X, role="ink", size=5.0)
        d.text(X, name, offset=(0.0, -gap), size=9)
    drew_v = drew_h = False
    if p is not None:
        for i in arrow_at:
            pv = p[i, 1] * ds
            if abs(pv) > 1e-9 * span:
                d.arrow((x[i], z[i] - pv), (x[i], z[i]), role="vertical", width=1.1, layer="vertical loads")
                if not drew_v:
                    d.text((x[i], z[i] - pv), "p₃", role="vertical", offset=(0.0, gap), size=9)
                drew_v = True
            ph = p[i, 0] * ds
            if abs(ph) > 1e-9 * span:
                d.arrow((x[i], z[i]), (x[i] + ph, z[i]), role="horizontal", width=1.1, layer="horizontal loads")
                if not drew_h:
                    d.text((x[i] + ph, z[i]), "p₁", role="horizontal", offset=(gap * np.sign(ph), 0.0), size=9)
                drew_h = True
    for j, (X, G) in enumerate(point_loads):
        g = np.asarray(G, dtype=float) * fs
        d.arrow(np.asarray(X) - g, X, role="horizontal" if abs(G[0]) > 1e-12 else "vertical", width=1.6,
                layer="point loads")
        d.text(np.asarray(X) - g, "G" + sub(j + 1), role="horizontal" if abs(G[0]) > 1e-12 else "vertical",
               offset=tuple(-gap * _unit(g)), size=9)
    for X, R, name in reactions:
        r = np.asarray(R, dtype=float) * fs
        if np.linalg.norm(r) > 1e-9 * span:
            d.arrow(np.asarray(X) - r, X, role="reaction", width=1.5, layer="reactions")
            d.text(np.asarray(X) - r, name, role="reaction", offset=tuple(-gap * _unit(r)), size=9)
    for X, text, role in marks:
        d.marker(X, role=role, size=4.5, filled=False)
        d.text(X, text, role=role, offset=(0.0, gap), size=8.5)
    if drew_v or drew_h:
        d.notes.append("Densities drawn at 1 kN/m = %.3g m." % ds)
    if point_loads or reactions:
        d.notes.append("Point forces and reactions drawn at 1 kN = %.3g m." % fs)
    return d


# ---------------------------------------------------------------- arches

def _ring(d, geo, fill_polygon=None, voussoirs=True, faces_role="gray"):
    ring = np.vstack([geo.intrados, geo.extrados[::-1]])
    d.fill(ring, role="fill", layer="arch")
    if fill_polygon is not None and len(fill_polygon) > 2:
        # the polygon runs along the extrados and closes along the fill level (its last two points)
        d.fill(fill_polygon, role="soil", layer="fill")
        d.polyline(fill_polygon[-2:], role="light", width=0.9, layer="fill level")
    ki = thin(len(geo.intrados), None, 900)
    ke = thin(len(geo.extrados), None, 900)
    d.polyline(geo.intrados[ki], role=faces_role, width=1.0, layer="intrados")
    d.polyline(geo.extrados[ke], role=faces_role, width=1.0, layer="extrados")
    I, E = geo.I, geo.E
    if voussoirs and geo.n <= 48:
        for a, b in zip(I[1:-1], E[1:-1]):
            d.polyline([a, b], role="light", width=0.7, layer="joints")
    for j in (0, len(I) - 1):
        d.polyline([I[j], E[j]], role=faces_role, width=1.0, layer="springings")


def arch_view(geo, title, lines=(), fill_polygon=None, hinges=(), point_loads=(), reactions=(), fs=1.0,
              reduced=None, label_lines=True):
    """Arch to scale with thrust lines: lines = [(points, label, role, style)], hinges = [(point, label)]."""
    d = Drawing(title, unit="m", xlabel="x₁ [m]", ylabel="x₃ [m]")
    _ring(d, geo, fill_polygon)
    x0, x1, y0, y1 = d.extent()
    span = max(x1 - x0, y1 - y0, 1e-9)
    gap = 0.035 * span
    if reduced is not None:
        Ia, Ea = reduced
        d.polyline(Ia, role="vertical", width=1.0, style="dashed", layer="reduced intrados")
        d.polyline(Ea, role="vertical", width=1.0, style="dashed", layer="reduced extrados")
    n_lines = len(lines)
    for k, (pts, label, role, style) in enumerate(lines):
        pts = np.asarray(pts, dtype=float)
        good = np.all(np.isfinite(pts), axis=1)
        pts = pts[good]
        if len(pts) < 2:
            continue
        kk = thin(len(pts), None, 700)
        d.polyline(pts[kk], role=role, width=1.6, style=style, layer=label or "thrust line")
        if label and label_lines:
            frac = 0.2 + 0.6 * k / max(n_lines - 1, 1) if n_lines > 1 else 0.3
            i = int(round(frac * (len(pts) - 1)))
            d.text(pts[i], label, role=role, offset=(0.0, -gap), size=8.5)
    for X, label in hinges:
        d.marker(X, role="reaction", size=5.5)
        if label:
            d.text(X, label, role="reaction", offset=(0.0, gap), size=8.5)
    for j, (X, G) in enumerate(point_loads):
        g = np.asarray(G, dtype=float) * fs
        role = "horizontal" if abs(G[0]) > 1e-12 * max(abs(G[1]), 1.0) else "vertical"
        d.arrow(np.asarray(X) - g, X, role=role, width=1.6, layer="point loads")
        d.text(np.asarray(X) - g, "G" + sub(j + 1), role=role, offset=tuple(-gap * _unit(g)), size=9)
    for X, R, name in reactions:
        r = np.asarray(R, dtype=float) * fs
        if np.linalg.norm(r) > 1e-9 * span:
            d.arrow(np.asarray(X) - r, X, role="reaction", width=1.5, layer="reactions")
            d.text(np.asarray(X) - r, name, role="reaction", offset=tuple(-gap * _unit(r)), size=9)
    if point_loads or reactions:
        d.notes.append("Point forces and reactions drawn at 1 kN = %.3g m." % fs)
    return d


def eccentricity_graph(position, series, xlabel="position along the arch [m]", title="Eccentricity of the centre of pressure"):
    """e/t along the arch for several lines, with the faces at ±1/2 and the region outside shaded."""
    d = Drawing(title, unit="", xlabel=xlabel, ylabel="e / t", aspect="auto")
    x = np.asarray(position, dtype=float)
    vals = np.concatenate([np.asarray(y, float)[np.isfinite(y)] for y, *_ in series] + [np.zeros(1)])
    hi = max(0.62, float(np.max(np.abs(vals))) * 1.08)
    d.xlim = (float(x.min()), float(x.max()))
    d.ylim = (-hi, hi)
    d.fill([[d.xlim[0], 0.5], [d.xlim[1], 0.5], [d.xlim[1], hi], [d.xlim[0], hi]], role="violation", layer="outside")
    d.fill([[d.xlim[0], -hi], [d.xlim[1], -hi], [d.xlim[1], -0.5], [d.xlim[0], -0.5]], role="violation",
           layer="outside")
    for v in (0.5, -0.5):
        d.polyline([[d.xlim[0], v], [d.xlim[1], v]], role="gray", width=0.8, layer="faces")
    d.polyline([[d.xlim[0], 0.0], [d.xlim[1], 0.0]], role="light", width=0.6, layer="centre")
    n = len(series)
    for j, (y, label, role, style) in enumerate(series):
        y = np.asarray(y, dtype=float)
        good = np.isfinite(y)
        if good.sum() < 2:
            continue
        k = thin(len(x), None, 700)
        k = k[good[k]]
        d.polyline(np.column_stack((x[k], y[k])), role=role, width=1.5, style=style, layer=label)
        frac = 0.15 + 0.7 * j / max(n - 1, 1) if n > 1 else 0.5
        ok = np.where(good)[0]
        i = ok[min(int(round(frac * (len(ok) - 1))), len(ok) - 1)]
        d.text((x[i], y[i]), label, role=role, offset=(0.0, 0.08 * hi), size=9)
    d.text((d.xlim[0] + 0.5 * (d.xlim[1] - d.xlim[0]), 0.5), "extrados", role="gray", offset=(0.0, 0.05 * hi), size=8.5)
    d.text((d.xlim[0] + 0.5 * (d.xlim[1] - d.xlim[0]), -0.5), "intrados", role="gray", offset=(0.0, -0.05 * hi), size=8.5)
    return d


def thrust_domain(mu, H_min, H_max, current=None, xlabel="multiplier", title="Admissible thrusts"):
    """Thrusts H_A of the lines that fit in the arch, against the multiplier of the variable loads."""
    d = Drawing(title, unit="", xlabel=xlabel, ylabel="thrust H_A [kN]", aspect="auto")
    mu = np.asarray(mu, dtype=float)
    lo = np.asarray(H_min, dtype=float)
    hi = np.asarray(H_max, dtype=float)
    good = np.isfinite(lo) & np.isfinite(hi)
    mu, lo, hi = mu[good], lo[good], hi[good]
    if len(mu) >= 2:
        poly = np.vstack([np.column_stack((mu, lo)), np.column_stack((mu[::-1], hi[::-1]))])
        d.fill(poly, role="cone", layer="admissible")
        d.polyline(np.column_stack((mu, lo)), role="vertical", width=1.5, layer="minimum thrust")
        d.polyline(np.column_stack((mu, hi)), role="horizontal", width=1.5, style="dashed", layer="maximum thrust")
        j = len(mu) // 4
        d.text((mu[j], lo[j]), "H_min", role="vertical", offset=(0.0, -0.06 * (hi.max() - lo.min() + 1e-9)), size=9)
        d.text((mu[j], hi[j]), "H_max", role="horizontal", offset=(0.0, 0.06 * (hi.max() - lo.min() + 1e-9)), size=9)
        top = max(float(hi.max()), 1e-9)
        bottom = min(float(lo.min()), 0.0)
        pad = 0.12 * (top - bottom)
        d.xlim = (float(mu.min()), float(mu.max()) + 0.04 * max(float(np.ptp(mu)), 1e-9))
        d.ylim = (bottom, top + pad)
    if current is not None:
        d.marker(current, role="reaction", size=5.5)
        d.text(current, "model", role="reaction", offset=(0.0, 0.07 * (d.ylim[1] - d.ylim[0]) if d.ylim else 1.0), size=8.5)
    return d
