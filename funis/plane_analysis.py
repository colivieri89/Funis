"""The plane tasks: the plane funicular (catenary) and the thrust line assessment of arches."""
import numpy as np

from . import diagrams
from .analysis import InputError, Result, Table, _balance_table, _f, _g, _local, _spatial, global_balance
from .core import arch as A
from .core import loads as L
from .core.grid import cumulative, node_index
from .core.plane import (LineProblem, catenary, cross2, inclined_catenary, log_branch, parabola, plane_grid)

E2 = np.array([0.0, 1.0, 0.0])


def _poly(coeffs):
    return L.polynomial(coeffs)


def _constant(coeffs):
    return all(abs(float(v)) < 1e-15 for v in list(coeffs)[1:])


def plane_actions(rows, lo, hi, what="line"):
    """Point loads (x, G) with lo < x < hi; the others are reported and ignored."""
    acts, msgs = [], []
    for k, r in enumerate(rows):
        r = list(r) + [0.0] * 3
        x, G = float(r[0]), np.array([float(r[1]), float(r[2])])
        if not np.any(G):
            continue
        if not (lo + 1e-9 * (hi - lo) < x < hi - 1e-9 * (hi - lo)):
            msgs.append("Point load %d at x = %g m is not on the %s (%g < x < %g m) and is ignored."
                        % (k + 1, x, what, lo, hi))
            continue
        acts.append((x, G))
    acts.sort(key=lambda a: a[0])
    return acts, msgs


def _stations(n, count, keep=()):
    count = int(min(max(int(count), 2), n))
    idx = set(np.unique(np.round(np.linspace(0, n - 1, count)).astype(int)).tolist())
    idx.update(int(k) for k in keep if 0 <= k < n)
    return sorted(idx)


# ----------------------------------------------------------------- plane funicular

def _pair(f1, f3):
    """Plane load law from its two components: a vector for a number x, an (n, 2) array for an array."""
    def fn(x):
        if np.ndim(x) == 0:
            return np.array([f1(x), f3(x)], dtype=float)
        x = np.asarray(x, dtype=float)
        return np.column_stack((np.broadcast_to(f1(x), x.shape), np.broadcast_to(f3(x), x.shape)))
    return fn


def _vertical_law(fs):
    if fs.vertical_mode in ("density", "actual"):
        return _poly(fs.w)
    if fs.vertical_mode == "table":
        return L.table(fs.w_table)
    raise InputError("Unknown vertical load %s" % fs.vertical_mode)


def _describe_funicular_loads(fs):
    if fs.vertical_mode == "table":
        v = "w(x) from a table, per metre of x"
    else:
        poly = " + ".join("%g x^%d" % (c, k) if k else "%g" % c for k, c in enumerate(fs.w) if c) or "0"
        v = "w = %s kN/m per metre of %s" % (poly, "actual length (catenary)" if fs.vertical_mode == "actual" else "x")
    if fs.horizontal_mode == "none":
        h = "none"
    elif fs.horizontal_mode == "density":
        poly = " + ".join("%g x^%d" % (c, k) if k else "%g" % c for k, c in enumerate(fs.h) if c) or "0"
        h = "p₁ = %s kN/m per metre of x" % poly
    else:
        h = "pseudo-static, p₁ = %g w in the measure of w" % fs.gamma
    return v, h


def run_plane_funicular(project):
    res = Result(project)
    fs = project.funicular
    Lspan = float(fs.span)
    if Lspan <= 0:
        raise InputError("The span must be positive")
    acts, msgs = plane_actions(project.plane_points, 0.0, Lspan)
    res.messages += msgs
    n = int(min(max(int(fs.samples), 101), 20001))
    extra = [float(fs.through[0])] if fs.selection == "point" else []
    s, idx = plane_grid(Lspan, n, [a for a, _ in acts], extra)
    w = _vertical_law(fs)
    hmode = fs.horizontal_mode
    if hmode == "density":
        hx = _poly(fs.h)
    elif hmode == "proportional":
        hx = lambda x: float(fs.gamma) * w(x)
    elif hmode == "none":
        hx = lambda x: 0.0 if np.ndim(x) == 0 else np.zeros(len(x))
    else:
        raise InputError("Unknown horizontal load %s" % hmode)
    zero = lambda x: 0.0 if np.ndim(x) == 0 else np.zeros(len(x))
    neg_w = lambda x: -w(x)
    if fs.vertical_mode == "actual":
        proj = _pair(hx if hmode == "density" else zero, zero)
        actual = _pair(hx if hmode == "proportional" else zero, neg_w)
    else:
        proj = _pair(hx, neg_w)
        actual = None
    zB = float(fs.end_height)
    problem = LineProblem(s, proj, actual, acts, 0.0, zB)
    if fs.selection == "initial":
        C = np.asarray(fs.force, dtype=float)
        sel = "prescribed initial force F(0) = %s" % _g(C, "kN")
    elif fs.selection == "thrust":
        C = problem.through_end(float(fs.thrust))
        sel = "thrust H_A = %s and the second support" % _g(fs.thrust, "kN")
    elif fs.selection == "point":
        xc, zc = float(fs.through[0]), float(fs.through[1])
        if not (0 < xc < Lspan):
            raise InputError("The point of the line must lie between the supports (0 < x_c < %g m)" % Lspan)
        C = problem.through_point(idx[0], zc)
        sel = "through (%g, %g) m and the second support" % (xc, zc)
    else:
        raise InputError("Unknown selection %s" % fs.selection)
    ln = problem.line(C)
    z, F, p = ln["z"], ln["F"], ln["p"]
    slope = F[:, 1] / F[:, 0]
    J = np.sqrt(1.0 + slope ** 2)
    N = -np.linalg.norm(F, axis=1)
    length = float(cumulative(J, s)[-1])
    top = int(np.argmax(z))
    v, h = _describe_funicular_loads(fs)
    res.summary += [("Span L", _g(Lspan, "m")), ("Second support B", "(%s, %s) m" % (_g(Lspan), _g(zB))),
                    ("Vertical load", v), ("Horizontal load", h), ("Line", sel),
                    ("Initial force F(0)", _g(F[0], "kN")),
                    ("Thrust at A, H_A = −F₁(0)", _g(-F[0, 0], "kN")),
                    ("Thrust at B, H_B = −F₁(L)", _g(-F[-1, 0], "kN")),
                    ("Reaction at A, R_A = −F(0)", _g(-F[0], "kN")),
                    ("Reaction at B, R_B = F(L)", _g(F[-1], "kN")),
                    ("Highest point", "(%s, %s) m" % (_g(s[top]), _g(z[top]))),
                    ("Length of the line", _g(length, "m")),
                    ("Axial force N = −|F|", "%s to %s" % (_g(N.max(), "kN"), _g(N.min(), "kN")))]
    if fs.selection in ("point", "thrust"):
        res.summary.append(("Height reached at x = L", "%s (target %s)" % (_g(z[-1], "m"), _g(zB, "m"))))
    # closed forms
    closed, name = None, None
    if not acts and _constant(fs.w) and fs.vertical_mode != "table":
        w0 = float(fs.w[0])
        h_const = hmode == "none" or (hmode == "density" and _constant(fs.h)) or hmode == "proportional"
        if h_const and w0 != 0:
            h0 = 0.0 if hmode == "none" else (float(fs.h[0]) if hmode == "density" else float(fs.gamma) * w0)
            if fs.vertical_mode == "density":
                if abs(h0) < 1e-15:
                    closed, name = parabola(s, F[0], -w0), "parabola, constant load per metre of x"
                else:
                    closed, name = log_branch(s, F[0], h0, -w0), "Appendix B, constant h and p₃ per metre of x"
            elif hmode in ("none", "proportional"):
                if abs(h0) < 1e-15:
                    closed, name = catenary(s, F[0], w0), "catenary, Appendix B"
                else:
                    closed, name = inclined_catenary(s, F[0], w0, float(fs.gamma)), \
                        "catenary with an inclined axis, load of fixed direction per actual length"
    if closed is not None:
        err = float(np.max(np.abs(closed - z)))
        res.summary.append(("Closed form against the integration", "%.2e m (%s)" % (err, name)))
        res.data["closed_form_error"] = err
    xyz = np.column_stack((s, np.zeros_like(s), z))
    F3d = np.column_stack((F[:, 0], np.zeros_like(s), F[:, 1]))
    p3d = np.column_stack((p[:, 0], np.zeros_like(s), p[:, 1]))
    pts3 = [(np.array([a, 0.0, z[node_index(s, a)]]), np.array([G[0], 0.0, G[1]])) for a, G in acts]
    bal = global_balance(s, xyz, F3d, p3d, None, pts3)
    local = _local(s, F3d, p3d)
    res.summary.append(("Global balance (normalised)", "force %.1e, moment %.1e" % (
        bal["force_relative"], bal["moment_relative"])))
    res.tables["balance"] = _balance_table(bal, local)
    nodes = [node_index(s, a) for a, _ in acts]
    idx_rows = _stations(len(s), project.output.stations, nodes + [n + 1 for n in nodes] + [top])
    cols = ["x [m]", "z [m]", "f,x", "F₁ [kN]", "F₃ [kN]", "N [kN]", "p₁ [kN/m]", "p₃ [kN/m]"]
    if closed is not None:
        cols.append("closed form z [m]")
    rows = []
    for i in idx_rows:
        row = [_f(s[i]), _f(z[i], 6), _f(slope[i], 6), _f(F[i, 0]), _f(F[i, 1]), _f(N[i]), _f(p[i, 0]), _f(p[i, 1])]
        if closed is not None:
            row.append(_f(closed[i], 6))
        rows.append(row)
    res.tables["stations"] = Table("Stations", cols, rows,
                                   "Values at evenly spaced stations; at a point load the two rows give the "
                                   "values before and after the node. Compression: F₁ < 0, N < 0.")
    if acts:
        res.tables["points"] = Table("Point loads", ["j", "x [m]", "z [m]", "G₁ [kN]", "G₃ [kN]"],
                                     [[k + 1, _f(a), _f(z[node_index(s, a)]), _f(G[0]), _f(G[1])]
                                      for k, (a, G) in enumerate(acts)], "The force jumps by −G at each node.")
    # drawings
    span = max(float(np.ptp(s)), float(np.ptp(z)), 1e-9)
    arrow_at = diagrams.stations_for_arrows(s, 12, [a for a, _ in acts])
    maxd = max(float(np.max(np.abs(p))), 1e-9)
    ds = diagrams.density_scale(span, maxd, 0.12)
    maxf = max([np.linalg.norm(G) for _, G in acts] + [np.linalg.norm(F[0]), np.linalg.norm(F[-1]), 1e-9])
    fsc = diagrams.force_scale(span, maxf, 0.18)
    marks = [((float(fs.through[0]), float(fs.through[1])), "given point", "reaction")] if fs.selection == "point" else []
    res.drawings["funicular"] = diagrams.funicular_view(
        s, z, "Plane funicular", p=p, arrow_at=arrow_at, ds=ds,
        point_loads=[((a, z[node_index(s, a)]), G) for a, G in acts], fs=fsc,
        reactions=[((s[0], z[0]), -F[0], "R_A"), ((s[-1], z[-1]), F[-1], "R_B")], marks=marks)
    res.drawings["forces"] = diagrams.graph("Forces along the line", s, [(F[:, 0], "F₁", "ink", "solid"),
                                                                        (F[:, 1], "F₃", "horizontal", "dashed"),
                                                                        (N, "N", "vertical", "dotted")],
                                            "x [m]", "force [kN]", s=s)
    res.drawings["loads"] = diagrams.graph("Loads per metre of x", s, [(p[:, 1], "p₃", "vertical", "solid"),
                                                                      (p[:, 0], "p₁", "horizontal", "dashed")],
                                           "x [m]", "density [kN/m]", s=s)
    arrows = [(xyz[i], np.array([0.0, 0.0, p[i, 1] * ds]), "vertical") for i in arrow_at]
    res.spatial = _spatial(xyz, arrows, [(xyz[0], "ink", "A"), (xyz[-1], "ink", "B")],
                           "The line lies in the plane of e₁ and e₃. Densities drawn at 1 kN/m = %.3g m." % ds)
    res.data.update(s=s, z=z, F=F, N=N, C=F[0], p=p)
    res.tables["summary"] = Table("Summary", ["quantity", "value"], [list(r) for r in res.summary])
    return res


# ----------------------------------------------------------------- arches

def _arch_geometry(a, factor=1.0):
    return A.build(a.shape, a.span, a.rise, factor * a.thickness, factor * a.thickness_springing, a.count,
                   a.joints, a.points)


def _arch_loads(geo, a, acts):
    return A.slice_loads(geo, a.unit_weight, a.depth, a.fill, a.fill_level, a.fill_weight, a.surcharge,
                         a.fill_inertia, [(x, G[0], G[1]) for x, G in acts])


def _describe_arch(a, geo):
    names = {"circular": "Circular arch", "pointed": "Pointed (two-centred) arch", "elliptical": "Elliptical arch",
             "parabolic": "Parabolic arch", "catenary": "Catenary arch", "points": "Arch on a spline centre line"}
    text = names.get(a.shape, a.shape)
    if a.shape != "points":
        text += ", span %g m, rise %g m" % (a.span, a.rise)
        if geo.radius is not None:
            text += ", radius of the centre line %s" % _g(geo.radius, "m")
    if abs(a.thickness - a.thickness_springing) < 1e-15:
        text += ", thickness %g m" % a.thickness
    else:
        text += ", thickness %g m at the crown and %g m at the springings" % (a.thickness, a.thickness_springing)
    return text


def _fill_polygon(geo, level):
    E = geo.extrados
    z = np.minimum(E[:, 1], level)
    return np.vstack([np.column_stack((E[:, 0], z)), [[E[-1, 0], level], [E[0, 0], level]]])


def _where(geo, j, face=None):
    m = geo.I[j] if face == "intrados" else (geo.E[j] if face == "extrados" else geo.mid[j])
    text = "x = %.4g m" % m[0]
    if geo.joints == "normal" or j in (0, geo.n):
        ang = abs(float(geo.angle[j]))
        text += ", %.3g° from the vertical" % (ang if ang > 1e-6 else 0.0)
    return text


def _hinge_text(geo, hinges):
    return "; ".join("%s at %s" % (face, _where(geo, j, face)) for j, face, _ in hinges)


def run_arch(project):
    res = Result(project)
    a = project.arch
    if a.shape not in A.SHAPES:
        raise InputError("Unknown shape %s" % a.shape)
    geo = _arch_geometry(a)
    xs = np.r_[geo.intrados[:, 0], geo.extrados[:, 0]]
    acts, msgs = plane_actions(project.plane_points, float(geo.extrados[:, 0].min()),
                               float(geo.extrados[:, 0].max()), "extrados")
    res.messages += msgs
    ld = _arch_loads(geo, a, acts)
    sign = 1.0 if a.direction == "right" else -1.0
    lam = sign * float(a.lam)
    mu_f = float(a.friction)
    P, Q = A.combine(ld, lam=lam, points=1.0)
    prob = A.ThrustProblem(geo, P, Q, friction=mu_f)
    n = geo.n
    Wring = -float(np.sum(ld.ring[:, 1]))
    Wfill = -float(np.sum(ld.fill[:, 1]))
    res.summary += [("Arch", _describe_arch(a, geo)),
                    ("Joints", "%d %s, %d slices" % (n + 1, "joints normal to the centre line"
                                                     if geo.joints == "normal" else "joints: the springings and "
                                                     "vertical sections", n)),
                    ("Weight of the arch", "%s (γ = %g kN/m³, depth %g m)" % (_g(Wring, "kN"), a.unit_weight, a.depth))]
    if a.fill or a.surcharge:
        res.summary.append(("Fill and surcharge", "%s%s" % (
            _g(Wfill, "kN"), ", fill up to x₃ = %g m, γ = %g kN/m³" % (a.fill_level, a.fill_weight) if a.fill else "")))
    if acts:
        res.summary.append(("Point loads", ", ".join("G%d = (%g, %g) kN at x = %g m" % (k + 1, G[0], G[1], x)
                                                      for k, (x, G) in enumerate(acts))))
    res.summary.append(("Horizontal action", "λ = %g of the weights%s, along %s" % (
        abs(lam), " of the arch and of the fill" if a.fill and a.fill_inertia else "", "+e₁" if sign > 0 else "−e₁")
        if lam else "none"))
    if mu_f > 0:
        res.summary.append(("Sliding", "|V| ≤ %g |N| at every joint" % mu_f))
    else:
        res.summary.append(("Sliding", "excluded (Heyman: no sliding)"))

    feasible = prob.feasible()
    lines = {}
    if feasible:
        lines["min"] = prob.state(prob.thrust("min"))
        lines["max"] = prob.state(prob.thrust("max"))
        for key, label in (("min", "Minimum thrust"), ("max", "Maximum thrust")):
            st = lines[key]
            res.summary.append(("%s H_A" % label, "%s, H_B = %s; touches %s" % (
                _g(st["H"][0], "kN"), _g(st["H"][-1], "kN"), _hinge_text(geo, prob.hinges(st)) or "no face")))
        res.data["H_min"] = float(lines["min"]["H"][0])
        res.data["H_max"] = float(lines["max"]["H"][0])
    else:
        res.messages.append("No thrust line lies within the arch under these loads: by the safe theorem the "
                            "arch is not shown to be safe, and the geometric safety factor is below 1.")
        res.summary.append(("Thrust lines within the arch", "none"))
    if a.line == "points":
        eps = [float(v) for v in (list(a.eccentricities) + [0.0] * 3)[:3]]
        st = prob.state(prob.through(eps, [0, geo.crown, n]))
        lines["points"] = st
        out = np.where((st["gI"] < -1e-9 * prob.scale_F * prob.scale_L) |
                       (st["gE"] > 1e-9 * prob.scale_F * prob.scale_L))[0]
        res.data["three_points_inside"] = not len(out)
        res.summary.append(("Line through three points", "e/t = %g, %g, %g at the springing A, the crown and "
                            "the springing B: H_A = %s, largest |e/t| = %.4g" % (
                                eps[0], eps[1], eps[2], _g(st["H"][0], "kN"), np.nanmax(np.abs(st["ecc"])))))
        if len(out):
            res.messages.append("The line through the three points lies outside the arch at %d joints, from %s "
                                "to %s." % (len(out), _where(geo, out[0]), _where(geo, out[-1])))
    gsf, info = A.geometric_factor(prob)
    if gsf is not None:
        res.summary.append(("Geometric safety factor", "%.5g: the joints shrunk about their centres to %.4g of "
                            "their length still contain a line, with %s" % (
                                gsf, info["alpha"], _hinge_text(geo, info["hinges"]) or "no hinge")))
        res.data["gsf"] = gsf
    # collapse
    collapse = None
    if a.variable == "horizontal":
        Pd, Qd = A.combine(ld, lam=0.0, points=1.0)
        Pv, Qv = sign * ld.inertia, sign * ld.inertia_moment
        what = "λ of the horizontal action along %s" % ("+e₁" if sign > 0 else "−e₁")
    elif a.variable == "points":
        Pd, Qd = A.combine(ld, lam=lam, points=0.0)
        Pv, Qv = ld.points, ld.points_moment
        what = "multiplier of the point loads"
        if not acts:
            res.messages.append("The collapse multiplier of the point loads needs at least one point load.")
            Pv = None
    else:
        Pv = None
    if Pv is not None:
        pc = A.ThrustProblem(geo, Pd, Qd, Pv, Qv, friction=mu_f)
        y = pc.collapse(cap=1e4)
        if y is None:
            res.summary.append(("Collapse multiplier", "no collapse for %s up to 10⁴" % what))
        elif not pc.feasible(0.0):
            res.summary.append(("Collapse multiplier", "none: the arch holds no line even without the variable loads"))
        else:
            st = pc.state(y)
            hinges = pc.hinges(st)
            collapse = dict(mu=float(y[3]), state=st, hinges=hinges, problem=pc)
            res.summary.append(("Collapse multiplier", "%.6g, %s; hinges: %s" % (y[3], what, _hinge_text(geo, hinges))))
            res.data["collapse"] = float(y[3])
            if len(hinges) == 4 and mu_f == 0:
                kin = A.mechanism_multiplier(hinges, Pd, Qd, Pv, Qv)
                if kin is not None:
                    res.summary.append(("Mechanism through the four hinges", "multiplier %.6g by virtual work "
                                        "(difference %.1e)" % (kin, abs(kin - y[3]))))
                    res.data["kinematic"] = kin
            # domain of the admissible thrusts
            mus = np.linspace(0.0, y[3], 31)
            Hmin, Hmax = [], []
            for m in mus:
                try:
                    Hmin.append(-pc.thrust("min", m)[0])
                    Hmax.append(-pc.thrust("max", m)[0])
                except (ValueError, TypeError):
                    Hmin.append(np.nan)
                    Hmax.append(np.nan)
            collapse["domain"] = (mus, np.array(Hmin), np.array(Hmax))
    # minimum thickness with the loads following the geometry
    thin_arch = None
    if a.minimum_thickness:
        def make(factor):
            g = _arch_geometry(a, factor)
            l = _arch_loads(g, a, acts)
            PP, QQ = A.combine(l, lam=lam, points=1.0)
            return A.ThrustProblem(g, PP, QQ, friction=mu_f)
        thin_arch = A.minimum_thickness(make)
        if thin_arch is None:
            res.summary.append(("Minimum thickness", "above ten times the given thickness"))
        else:
            fct = thin_arch["factor"]
            g2 = thin_arch["problem"].geo
            text = "%.5g of the given thickness (t = %s at the crown)" % (fct, _g(fct * a.thickness, "m"))
            if geo.radius is not None and a.shape == "circular":
                text += ", t / R = %.5g" % (fct * a.thickness / geo.radius)
            res.summary.append(("Minimum thickness, loads recomputed", text + "; hinges: " +
                                _hinge_text(g2, thin_arch["hinges"])))
            res.data["minimum_thickness"] = fct
            res.data["minimum_thickness_hinges"] = [(j, face, float(g2.angle[j])) for j, face, _ in thin_arch["hinges"]]
    # selected line
    key = a.line if a.line in lines else ("min" if "min" in lines else None)
    sel = lines.get(key) if key else (info["state"] if info else None)
    sel_name = {"min": "line of minimum thrust", "max": "line of maximum thrust",
                "points": "line through three points"}.get(key, "line of the geometric safety factor")
    if sel is not None:
        V = np.abs(sel["V"])
        Nn = np.abs(sel["N"])
        ratio = float(np.max(V / np.maximum(Nn, 1e-300)))
        res.summary.append(("Friction needed by the %s" % sel_name, "|V| / |N| up to %.4g" % ratio))
        res.data["friction_needed"] = ratio
        # balance of the selected line
        cA, cB = sel["centre"][0], sel["centre"][-1]
        RA, RB = -sel["F"][0], sel["F"][-1]
        force = RA + RB + np.sum(P, axis=0)
        moment = cross2(cA, RA) + cross2(cB, RB) + float(np.sum(Q))
        scale = float(np.sum(np.abs(P))) + np.linalg.norm(RA) + np.linalg.norm(RB)
        extent = max(float(np.max(np.abs(xs))), float(np.max(np.abs(geo.extrados[:, 1]))), 1e-9)
        c = sel["centre"]
        Fk = sel["F"]
        loc = (-cross2(c[:-1], Fk[:-1]) + cross2(c[1:], Fk[1:]) + Q)
        bal = dict(force=np.array([force[0], 0.0, force[1]]), moment=np.array([0.0, -moment, 0.0]),
                   force_relative=float(np.linalg.norm(force) / max(scale, 1e-12)),
                   moment_relative=float(abs(moment) / max(scale * extent, 1e-12)))
        res.tables["balance"] = _balance_table(bal, float(np.max(np.abs(loc))) / max(scale * extent / n, 1e-12))
        res.tables["balance"].note = ("Checks of the %s: balance of the reactions at the centres of pressure of "
                                      "the springings and of all loads (kN and kN m), and the moment balance of "
                                      "every slice under the forces at its two centres of pressure (last row)."
                                      % sel_name)
        res.summary.append(("Global balance (normalised)", "force %.1e, moment %.1e" % (
            bal["force_relative"], bal["moment_relative"])))
        # tables
        hinge_joints = [j for j, _, _ in (collapse["hinges"] if collapse else [])]
        idx = _stations(n + 1, project.output.stations, [0, geo.crown, n] + hinge_joints)
        rows = []
        for j in idx:
            rows.append([j, _f(geo.mid[j, 0]), _f(geo.mid[j, 1]), _f(geo.angle[j], 3), _f(geo.length[j]),
                         _f(sel["H"][j]), _f(sel["F"][j, 1]), _f(sel["N"][j]), _f(sel["V"][j]),
                         _f(sel["ecc"][j], 5), _f(sel["moment"][j]), _f(sel["centre"][j, 0]), _f(sel["centre"][j, 1])])
        res.tables["joints"] = Table("Joints", ["joint", "x [m]", "z [m]", "angle [°]", "length [m]", "H [kN]",
                                                "F₃ [kN]", "N [kN]", "V [kN]", "e / t", "M [kN m]",
                                                "x of the centre of pressure [m]", "z [m]"], rows,
                                     "The %s at the joints: x and z of the joint centre, angle of the joint from "
                                     "the vertical, H = −F₁ and F₃ of the force on the part on the left, normal "
                                     "force N (compression negative) and shear V along the joint, eccentricity "
                                     "e of the centre of pressure from the joint centre toward the extrados, and "
                                     "M = |N| e about the joint centre." % sel_name)
    ecc_rows = []
    cols = ["joint", "x [m]"]
    series = []
    pos = geo.position
    ecc_lines = [(k, lab, role, style) for k, lab, role, style in (
        ("min", "minimum thrust", "vertical", "solid"), ("max", "maximum thrust", "horizontal", "dashed"),
        ("points", "three points", "ink", "solid")) if k in lines]
    for k, lab, role, style in ecc_lines:
        cols.append("e/t, %s" % lab)
        series.append((lines[k]["ecc"], lab, role, style))
    if collapse:
        cols.append("e/t at collapse")
        series.append((collapse["state"]["ecc"], "collapse", "reaction", "dotted"))
    if not feasible and info:
        cols.append("e/t, least-thickness line")
        series.append((info["state"]["ecc"], "least thickness", "reaction", "solid"))
    for j in _stations(n + 1, project.output.stations, [0, geo.crown, n]):
        row = [j, _f(geo.mid[j, 0])]
        for y, *_ in series:
            row.append(_f(y[j], 5))
        ecc_rows.append(row)
    res.tables["eccentricities"] = Table("Eccentricities", cols, ecc_rows,
                                         "e / t of the centre of pressure from the joint centre, positive toward "
                                         "the extrados: the line lies in the arch where |e / t| ≤ 1/2.")
    hrows = []
    if collapse:
        for j, face, X in collapse["hinges"]:
            hrows.append(["collapse", j, face, _f(X[0]), _f(X[1]), _f(geo.angle[j], 3)])
    if info:
        for j, face, X in info["hinges"]:
            hrows.append(["geometric safety factor", j, face, _f(X[0]), _f(X[1]), _f(geo.angle[j], 3)])
    if thin_arch:
        g2 = thin_arch["problem"].geo
        for j, face, X in thin_arch["hinges"]:
            hrows.append(["minimum thickness", j, face, _f(X[0]), _f(X[1]), _f(g2.angle[j], 3)])
    if hrows:
        res.tables["hinges"] = Table("Hinges", ["state", "joint", "face", "x [m]", "z [m]", "angle [°]"], hrows,
                                     "Joints where the centre of pressure reaches the intrados or the extrados "
                                     "(of the shrunk joints, for the geometric safety factor).")
    if collapse and "domain" in collapse:
        mus, Hmin, Hmax = collapse["domain"]
        res.tables["domain"] = Table("Admissible thrusts", ["multiplier", "H_min [kN]", "H_max [kN]"],
                                     [[_f(m, 6), _f(h0), _f(h1)] for m, h0, h1 in zip(mus, Hmin, Hmax)],
                                     "Range of the thrust H_A of the lines in the arch at each multiplier of the "
                                     "variable loads; it closes at the collapse multiplier.")
    res.tables["loads"] = Table("Loads", ["load", "total [kN]"], [
        ["weight of the arch", _f(Wring)], ["fill and surcharge", _f(Wfill)],
        ["point loads, vertical", _f(-sum(G[1] for _, G in acts))],
        ["point loads, horizontal", _f(sum(G[0] for _, G in acts))],
        ["horizontal action at λ", _f(lam * float(np.sum(ld.inertia[:, 0])))]],
        "Vertical loads downward positive in this table.")

    # drawings
    fillp = _fill_polygon(geo, a.fill_level) if a.fill else None
    span = max(float(np.ptp(geo.extrados[:, 0])), float(np.ptp(geo.extrados[:, 1])), 1e-9)
    view_lines = [(lines[k]["centre"], lab, role, style) for k, lab, role, style in ecc_lines]
    if view_lines:
        res.drawings["arch_lines"] = diagrams.arch_view(geo, "Thrust lines in the arch", view_lines, fillp)
    if sel is not None:
        maxf = max([np.linalg.norm(G) for _, G in acts] + [np.linalg.norm(sel["F"][0]), np.linalg.norm(sel["F"][-1])])
        fsc = diagrams.force_scale(span, maxf, 0.16)
        res.drawings["arch_loads"] = diagrams.arch_view(
            geo, "Loads and reactions, %s" % sel_name, [(sel["centre"], "", "ink", "solid")], fillp,
            point_loads=[(r, G) for _, r, G in ld.point_list], fs=fsc,
            reactions=[(sel["centre"][0], -sel["F"][0], "R_A"), (sel["centre"][-1], sel["F"][-1], "R_B")])
    if collapse:
        hz = [(X, "h" + diagrams.sub(k + 1)) for k, (_, _, X) in enumerate(collapse["hinges"])]
        res.drawings["arch_collapse"] = diagrams.arch_view(
            geo, "Collapse, multiplier %.4g" % collapse["mu"], [(collapse["state"]["centre"], "", "reaction", "solid")],
            fillp, hinges=hz)
    if info:
        prob.set_alpha(info["alpha"])
        Ia, Ea = prob.Ia.copy(), prob.Ea.copy()
        prob.set_alpha(1.0)
        res.drawings["arch_gsf"] = diagrams.arch_view(
            geo, "Geometric safety factor %.4g" % gsf, [(info["state"]["centre"], "", "ink", "solid")], fillp,
            hinges=[(X, "") for _, _, X in info["hinges"]], reduced=(Ia, Ea))
        res.drawings["arch_gsf"].notes.append("Dashed: the joints shrunk about their centres by %.4g." % info["alpha"])
    if thin_arch:
        g2 = thin_arch["problem"].geo
        res.drawings["arch_thickness"] = diagrams.arch_view(
            g2, "Arch of minimum thickness, %.4g t" % thin_arch["factor"],
            [(thin_arch["state"]["centre"], "", "ink", "solid")], _fill_polygon(g2, a.fill_level) if a.fill else None,
            hinges=[(X, "") for _, _, X in thin_arch["hinges"]])
    if series:
        res.drawings["eccentricity"] = diagrams.eccentricity_graph(pos, series)
    force_series = [(lines[k]["N"], "N, " + lab, role, style) for k, lab, role, style in ecc_lines]
    if force_series:
        res.drawings["arch_forces"] = diagrams.graph("Normal force at the joints", pos, force_series,
                                                     "position along the arch [m]", "N [kN]")
    if collapse and "domain" in collapse:
        mus, Hmin, Hmax = collapse["domain"]
        cur = None
        m0 = abs(lam) if a.variable == "horizontal" else 1.0
        if key in lines and m0 <= mus[-1] * (1 + 1e-9):
            cur = (m0, lines[key]["H"][0])
        res.drawings["thrust_domain"] = diagrams.thrust_domain(
            mus, Hmin, Hmax, cur, xlabel="multiplier of the %s" % ("horizontal action" if a.variable == "horizontal"
                                                                  else "point loads"))
    res.data.update(geometry=geo, lines=lines, collapse_state=collapse, gsf_info=info, thin=thin_arch,
                    group_titles={"contact": "Admissible thrusts"})
    res.tables["summary"] = Table("Summary", ["quantity", "value"], [list(r) for r in res.summary])
    return res
