"""From a project to its results: geometry, loads, solver, tables and drawings."""
from dataclasses import dataclass, field
from typing import Dict, List

import numpy as np

from . import diagrams
from .core import geometry, loads as L
from .core.contact import (ContactProblem, cone_margin, critical_horizontal_circle,
                           friction_strip, minimum_preload_circle)
from .core.funicular import (compatibility, constant_load_curve, curvature_torsion, endpoint_jacobian,
                             fixed_plane, free_curve, loads_for_thrust, local_residual, node,
                             plane_distance, self_weight_curve, solve_endpoint)
from .core.grid import derivative, integral, node_index, piecewise_grid
from .core.supported import preload_to_C3, supported
from .model import Project

E3 = np.array([0.0, 0.0, 1.0])


@dataclass
class Table:
    name: str
    columns: List[str]
    rows: List[List[object]]
    note: str = ""


@dataclass
class Result:
    project: Project
    summary: List[tuple] = field(default_factory=list)
    tables: Dict[str, Table] = field(default_factory=dict)
    drawings: Dict[str, object] = field(default_factory=dict)
    messages: List[str] = field(default_factory=list)
    spatial: Dict[str, object] = None
    data: Dict[str, object] = field(default_factory=dict)

    @property
    def title(self):
        return "%s: %s" % (self.project.name, self.project.task_label)

    @property
    def curve3d(self):
        return None if self.spatial is None else self.spatial.get("xyz")


class InputError(ValueError):
    pass


# ----------------------------------------------------------------- formatting

def _f(x, nd=4):
    return float(np.round(float(x), nd))


def _g(x, unit="", digits=6):
    if x is None:
        return "–"
    if isinstance(x, (list, tuple, np.ndarray)):
        return "(" + ", ".join("%.*g" % (digits, v) for v in np.ravel(x)) + ")" + (" " + unit if unit else "")
    if not np.isfinite(x):
        return "unbounded"
    return "%.*g%s" % (digits, x, " " + unit if unit else "")


def _at(path_or_s, i, theta=None):
    s = path_or_s.s if hasattr(path_or_s, "s") else path_or_s
    th = theta if theta is not None else getattr(path_or_s, "theta", None)
    text = "s = %.4g m" % s[i]
    if th is not None:
        text += " (θ = %.4g rad)" % th[i]
    return text


# ----------------------------------------------------------------- builders

def _samples(n):
    return int(min(max(int(n), 101), 20001))


def build_path(spec, nodes=()):
    n = _samples(spec.samples)
    if spec.kind == "helix":
        h = spec.helix
        return geometry.helix(h.radius, h.pitch, np.radians(h.theta_start), np.radians(h.theta_end), n, nodes)
    if spec.kind == "ellipse":
        e = spec.ellipse
        return geometry.ellipse(e.a, e.b, e.pitch, np.radians(e.theta_start), np.radians(e.theta_end), n,
                                e.mode, nodes)
    if spec.kind == "points":
        return geometry.spline_path(spec.points, n, nodes)
    raise InputError("Unknown geometry %s" % spec.kind)


def describe_geometry(spec):
    if spec.kind == "helix":
        h = spec.helix
        return "Circular helix R = %g m, c = %g m/rad, θ from %g° to %g°" % (
            h.radius, h.pitch, h.theta_start, h.theta_end)
    if spec.kind == "ellipse":
        e = spec.ellipse
        rise = "f = c θ, c = %g m/rad" % e.pitch if e.mode == "angle" else "f = k_s s, k_s = %g" % e.pitch
        return "Elliptical helix a = %g m, b = %g m, %s, θ from %g° to %g°" % (
            e.a, e.b, rise, e.theta_start, e.theta_end)
    return "Smooth path through %d points" % len(spec.points)


def point_actions(project, length):
    acts, msgs = [], []
    for k, a in enumerate(project.point_actions):
        G = np.array([a.G1, a.G2, a.G3], dtype=float)
        if not (1e-9 * length < a.s < length * (1 - 1e-9)):
            msgs.append("Point action %d at s = %g m is not inside the path (0 < s < %.4g m) and is ignored."
                        % (k + 1, a.s, length))
        elif np.linalg.norm(G) > 0:
            acts.append((float(a.s), G))
    acts.sort(key=lambda r: r[0])
    return acts, msgs


def _poly(coeffs):
    return L.polynomial(coeffs)


def _constant(coeffs):
    return all(abs(float(v)) < 1e-15 for v in list(coeffs)[1:])


def build_loads(spec, s, J=None, vertical=True):
    """Vertical loads, horizontal loads at multiplier 1 and the profile of a directional load."""
    s = np.asarray(s, dtype=float)
    n = len(s)
    if not vertical:
        w = np.zeros(n)
    elif spec.vertical_mode == "density":
        w = _poly(spec.w)(s)
    elif spec.vertical_mode == "table":
        w = L.table(spec.w_table)(s)
    elif spec.vertical_mode == "actual":
        if J is None:
            raise InputError("A weight per actual length needs the path")
        w = _poly(spec.w)(s) * J
    else:
        raise InputError("Unknown vertical load %s" % spec.vertical_mode)
    pv = np.zeros((n, 3))
    pv[:, 2] = -w
    ph = np.zeros((n, 3))
    profile, beta, unit = None, None, ""
    mode = spec.horizontal_mode
    if mode in ("fixed", "fixed_table", "pseudo"):
        beta = np.radians(spec.beta)
        d = L.direction(spec.beta)
        if mode == "fixed":
            profile = _poly(spec.h)(s)
            const = _constant(spec.h)
            unit = ("h [kN/m]", float(spec.h[0])) if const and abs(spec.h[0]) > 0 else ("λ", 1.0)
        elif mode == "fixed_table":
            profile = L.table(spec.h_table)(s)
            unit = ("λ", 1.0)
        else:
            profile = float(spec.gamma) * np.abs(pv[:, 2])
            unit = ("γ", float(spec.gamma)) if abs(spec.gamma) > 0 else ("λ", 1.0)
        ph = profile[:, None] * d[None, :]
    elif mode == "components":
        ph[:, 0] = _poly(spec.p1)(s)
        ph[:, 1] = _poly(spec.p2)(s)
    elif mode != "none":
        raise InputError("Unknown horizontal load %s" % mode)
    return dict(pv=pv, ph=ph, lam=float(spec.multiplier), profile=profile, beta=beta, unit=unit,
                horizontal=bool(np.any(np.abs(ph) > 0)))


def abscissa(project, s, theta=None):
    """Abscissa of the graphs: theta in rad when asked and available, otherwise s."""
    if project.output.abscissa == "theta" and theta is not None:
        lo, hi = float(np.min(theta)), float(np.max(theta))
        ks = np.arange(np.ceil(lo / (np.pi / 2) - 1e-9), np.floor(hi / (np.pi / 2) + 1e-9) + 1)
        ticks = None
        if 3 <= len(ks) <= 13:
            ticks = [(k * np.pi / 2, _pi_label(int(k))) for k in ks]
        return np.asarray(theta), "θ [rad]", ticks
    return np.asarray(s), "s [m]", None


def _pi_label(k):
    if k == 0:
        return "0"
    if k % 2 == 0:
        m = k // 2
        return "π" if m == 1 else ("−π" if m == -1 else "%dπ" % m)
    return ("π/2" if k == 1 else "−π/2" if k == -1 else "%dπ/2" % k)


def station_indices(s, count, nodes=()):
    s = np.asarray(s, dtype=float)
    count = int(min(max(int(count), 2), len(s)))
    idx = {int(np.argmin(np.abs(s - v))) for v in np.linspace(0.0, s[-1], count)}
    for a in nodes:
        i = node_index(s, a)
        idx.add(i)
        if i + 1 < len(s):
            idx.add(i + 1)
    return sorted(idx)


def global_balance(s, xyz, F, p, r=None, points=()):
    """Resultant force and moment of all actions on the line, and their normalised values."""
    total = np.asarray(p, dtype=float) + (0.0 if r is None else np.asarray(r, dtype=float))
    R0, RL = -F[0], F[-1]
    force = R0 + RL + integral(total, s)
    moment = np.cross(xyz[0], R0) + np.cross(xyz[-1], RL) + integral(np.cross(xyz, total), s)
    scale = np.linalg.norm(R0) + np.linalg.norm(RL) + integral(np.linalg.norm(total, axis=1), s)
    for x, P in points:
        force = force + P
        moment = moment + np.cross(x, P)
        scale += np.linalg.norm(P)
    extent = max(float(np.max(np.linalg.norm(xyz, axis=1))), float(s[-1]), 1e-9)
    return dict(force=force, moment=moment,
                force_relative=float(np.linalg.norm(force) / max(scale, 1e-12)),
                moment_relative=float(np.linalg.norm(moment) / max(scale * extent, 1e-12)))


def _local(s, F, p, r=None):
    res = local_residual(s, F, p, r)
    total = np.asarray(p) + (0.0 if r is None else np.asarray(r))
    scale = max(float(np.max(np.linalg.norm(total, axis=1))), float(np.max(np.linalg.norm(F, axis=1))) / max(s[-1], 1e-9), 1e-12)
    return float(np.max(np.linalg.norm(res, axis=1)) / scale)


def _balance_table(bal, local):
    rows = [["resultant force", _f(bal["force"][0], 10), _f(bal["force"][1], 10), _f(bal["force"][2], 10),
             "%.2e" % bal["force_relative"]],
            ["resultant moment", _f(bal["moment"][0], 10), _f(bal["moment"][1], 10), _f(bal["moment"][2], 10),
             "%.2e" % bal["moment_relative"]]]
    if local is not None:
        rows.append(["local balance F,s + p + r", "", "", "", "%.2e" % local])
    return Table("Balance", ["check", "x₁", "x₂", "x₃", "normalised"], rows,
                 "Independent checks of the computed state: global balance of every action on the line "
                 "(kN and kN m), and a finite-difference test of the local equations. Values are "
                 "normalised by the sum of the magnitudes of the actions.")


def _spatial(xyz, arrows=(), markers=(), note=""):
    k = diagrams.thin(len(xyz), None, 900)
    return dict(xyz=np.asarray(xyz)[k], arrows=list(arrows), markers=list(markers), note=note)


def _span(xyz):
    return max(float(np.ptp(np.asarray(xyz)[:, :2], axis=0).max()), float(np.ptp(np.asarray(xyz)[:, 2])), 1e-9)


# ----------------------------------------------------------------- supported path

def _path_with_actions(project):
    path0 = build_path(project.geometry)
    acts, msgs = point_actions(project, path0.L)
    path = build_path(project.geometry, [a for a, _ in acts]) if acts else path0
    return path, acts, msgs


def _exact_circle(project, ld, eta, lam):
    """Arguments of the exact bound of Appendix A, when the model is the benchmark type."""
    g, lo, sp = project.geometry, project.loads, project.support
    if g.kind != "helix" or g.helix.pitch >= 0 or project.point_actions or sp.wall != "right":
        return None
    if lo.vertical_mode != "density" or not _constant(lo.w) or lo.w[0] <= 0:
        return None
    if lo.horizontal_mode == "none":
        h, beta = 0.0, 0.0
    elif lo.horizontal_mode == "fixed" and _constant(lo.h):
        h, beta = lam * float(lo.h[0]), np.radians(lo.beta)
    elif lo.horizontal_mode == "pseudo":
        h, beta = lam * float(lo.gamma) * float(lo.w[0]), np.radians(lo.beta)
    else:
        return None
    th0 = np.radians(g.helix.theta_start)
    b = beta - th0
    return dict(hx=h * np.cos(b), hy=h * np.sin(b), radius=g.helix.radius,
                grade=g.helix.pitch / g.helix.radius, weight=float(lo.w[0]), eta=eta,
                theta_end=np.radians(g.helix.theta_end - g.helix.theta_start), beta=b, h=h)


def run_supported(project):
    res = Result(project)
    path, acts, msgs = _path_with_actions(project)
    res.messages += msgs
    nodes = [a for a, _ in acts]
    ld = build_loads(project.loads, path.s, path.J)
    lam = ld["lam"]
    p = ld["pv"] + lam * ld["ph"]
    T = float(project.support.preload)
    wall = project.support.wall
    st = supported(path, p, preload_to_C3(path, T), acts, wall)
    x, xlabel, ticks = abscissa(project, path.s, path.theta)
    S, N = st["S"], st["N"]
    true_length = integral(path.J, path.s)
    res.summary += [("Geometry", describe_geometry(project.geometry)),
                    ("Projected length L", _g(path.L, "m")),
                    ("Length of the spatial path", _g(true_length, "m")),
                    ("Drop x₃(0) − x₃(L)", _g(path.xyz[0, 2] - path.xyz[-1, 2], "m")),
                    ("Preload T = −S(0)", _g(T, "kN")),
                    ("Thrust S", "%s to %s" % (_g(S.max(), "kN"), _g(S.min(), "kN"))),
                    ("Axial force N = S J", "%s to %s" % (_g(N.max(), "kN"), _g(N.min(), "kN"))),
                    ("Force at the start F(0)", _g(st["F"][0], "kN")),
                    ("Force at the end F(L)", _g(st["F"][-1], "kN"))]
    if not st["compression"]:
        i = int(np.argmax(S))
        res.messages.append("The line is not in compression: S reaches %.4g kN at %s. Raise the preload "
                            "or check the loads." % (S[i], _at(path, i)))
        res.summary.append(("Compression", "lost (S > 0 at %s)" % _at(path, i)))
    else:
        res.summary.append(("Compression", "S ≤ 0 along the whole line"))
    rt, rn, rnu = st["rt"], st["rn"], st["rnu"]
    res.summary += [("Tangential reaction rₜ", "%s to %s" % (_g(rt.min(), "kN/m"), _g(rt.max(), "kN/m"))),
                    ("Normal reaction rₙ", "%s to %s" % (_g(rn.min(), "kN/m"), _g(rn.max(), "kN/m"))),
                    ("Wall", "on the %s of the direction of travel (r_ν = %srₙ)" % (
                        wall, "" if wall == "right" else "−"))]
    bal = global_balance(path.s, path.xyz, st["F"], p, st["r"],
                         [(path.xyz[a["index"]], a["G"] + a["R"]) for a in st["actions"]])
    local = _local(path.s, st["F"], p, st["r"])
    res.summary.append(("Global balance (normalised)", "force %.1e, moment %.1e" % (
        bal["force_relative"], bal["moment_relative"])))

    # contact
    c = project.contact
    margin = None
    if c.enabled:
        eta, phi = friction_strip(c.mu, c.strip, c.delta)
        if eta <= 0:
            raise InputError("The contact cone needs μ > 0 and a positive strip width")
        margin = cone_margin(rt, rnu, eta)
        problem = ContactProblem(path, ld["pv"], ld["ph"], acts, eta, wall)
        res.summary.append(("Contact cone", "η = min(μ, φ) = %.4g with μ = %g, φ = %s" % (
            eta, c.mu, "∞ (no strip limit)" if not np.isfinite(phi) else "%.4g" % phi)))
        i = int(np.argmin(margin))
        ok = margin[i] >= -1e-9 * max(np.max(np.abs(rnu)), 1.0)
        point_ok = all(min(a["Rnu"], eta * a["Rnu"] - abs(a["Rt"])) >= -1e-9 for a in st["actions"])
        res.summary.append(("Contact margin", "min %s at %s: %s" % (
            _g(margin[i], "kN/m"), _at(path, i), "satisfied" if ok else "violated")))
        if not ok:
            res.messages.append("The required reaction leaves the contact cone at %s (margin %.4g kN/m): "
                                "the assumed wall cannot supply it, although the line may remain in "
                                "compression." % (_at(path, i), margin[i]))
        if acts and not point_ok:
            res.messages.append("A point reaction leaves the contact cone (see the table of point actions).")
        Tint = problem.preload_interval(lam)
        if Tint is None:
            res.summary.append(("Admissible preloads at λ = %g" % lam, "none"))
            res.messages.append("No preload satisfies the contact cone at the multiplier λ = %g." % lam)
        else:
            res.summary.append(("Admissible preloads at λ = %g" % lam, "%s ≤ T ≤ %s, governed by %s" % (
                _g(Tint["lo"], "kN"), _g(Tint["hi"], "kN"), problem.describe(Tint["governing_lo"]))))
        if ld["horizontal"]:
            Lint = problem.multiplier_interval(T)
            res.summary.append(("Admissible multipliers at T = %g kN" % T, "none" if Lint is None else
                                "%s ≤ λ ≤ %s, governed by %s" % (_g(Lint["lo"]), _g(Lint["hi"]),
                                                                  problem.describe(Lint["governing_hi"]))))
        ex = _exact_circle(project, ld, eta, lam)
        if ex is not None:
            Tex, th_ex, _ = minimum_preload_circle(ex["hx"], ex["hy"], ex["radius"], ex["grade"], ex["weight"],
                                                    ex["eta"], ex["theta_end"], details=True)
            res.summary.append(("Exact minimum preload (Appendix A)", "%s, active at θ − θ₀ = %.5g rad" % (
                _g(Tex, "kN"), th_ex)))
            res.data["T_min_exact"] = Tex
        if Tint is not None:
            res.data["T_min"] = Tint["lo"]
        res.data["eta"] = eta
        _contact_drawings(res, project, path, problem, ld, x, xlabel, ticks, margin, rt, rnu, eta, T, lam, ex)

    # tables
    idx = station_indices(path.s, project.output.stations, nodes)
    cols = ["s [m]"] + (["θ [rad]"] if path.theta is not None else []) + [
        "x₁ [m]", "x₂ [m]", "x₃ [m]", "f,s", "S [kN]", "N [kN]", "V [kN]", "rₜ [kN/m]", "rₙ [kN/m]",
        "p₁ [kN/m]", "p₂ [kN/m]", "p₃ [kN/m]"] + (["margin [kN/m]"] if margin is not None else [])
    rows = []
    for i in idx:
        row = [_f(path.s[i])] + ([_f(path.theta[i])] if path.theta is not None else [])
        row += [_f(v) for v in path.xyz[i]] + [_f(path.fs[i]), _f(S[i]), _f(N[i]), _f(st["V"][i]),
                                               _f(rt[i]), _f(rn[i])] + [_f(v) for v in p[i]]
        if margin is not None:
            row.append(_f(margin[i]))
        rows.append(row)
    res.tables["stations"] = Table("Stations", cols, rows,
                                   "Values at evenly spaced stations; at a point action the two rows give "
                                   "the values before and after the node.")
    if st["actions"]:
        eta = res.data.get("eta")
        prow = []
        for k, a in enumerate(st["actions"]):
            row = [k + 1, _f(a["s"])] + [_f(v) for v in a["G"]] + [_f(a["jump"])] + [_f(v) for v in a["R"][:2]] + [
                _f(a["Rt"]), _f(a["Rnu"])]
            row.append(_f(min(a["Rnu"], eta * a["Rnu"] - abs(a["Rt"]))) if eta is not None else "")
            prow.append(row)
        res.tables["points"] = Table("Point actions", ["j", "s [m]", "G₁ [kN]", "G₂ [kN]", "G₃ [kN]", "[S] [kN]",
                                                       "R₁ [kN]", "R₂ [kN]", "R_t [kN]", "R_ν [kN]",
                                                       "cone margin [kN]"], prow,
                                     "Jump [S] = −G₃ / f,s and horizontal point reaction "
                                     "R_h = (G₃ / f,s) t − G_h, with no vertical support impulse.")
    res.tables["balance"] = _balance_table(bal, local)

    # drawings
    span = _span(path.xyz)
    arrow_at = diagrams.stations_for_arrows(path.s, 10, nodes)
    rh = st["r"]
    maxd = max(float(np.max(np.linalg.norm(rh[:, :2], axis=1))),
               float(np.max(np.linalg.norm(lam * ld["ph"][:, :2], axis=1))), 1e-9)
    ds = diagrams.density_scale(span, maxd)
    maxf = max([np.linalg.norm(a["G"]) for a in st["actions"]] + [np.linalg.norm(a["R"]) for a in st["actions"]] + [1e-9])
    fs = diagrams.force_scale(span, maxf)
    r_v = supported(path, ld["pv"], preload_to_C3(path, T), acts, wall)["r"] if ld["horizontal"] and lam != 0 else None
    res.drawings["plan"] = diagrams.plan(
        path.xyz, "Plan with loads and reactions", path.s, loads=lam * ld["ph"] if ld["horizontal"] else None,
        reactions=rh, reactions_vertical=r_v, ds=ds, fs=fs, wall=wall, normals=path.n, arrow_at=arrow_at,
        point_loads=[(path.xyz[a["index"]], a["G"]) for a in st["actions"]],
        point_reactions=[(path.xyz[a["index"]], a["R"]) for a in st["actions"]])
    res.drawings["elevation"] = diagrams.elevation(path.s, path.xyz, nodes=nodes)
    res.drawings["forces"] = diagrams.graph("Thrust and axial force", x, [(S, "S", "ink", "solid"),
                                                                          (N, "N", "vertical", "dashed")],
                                            xlabel, "force [kN]", s=path.s, xticks=ticks)
    res.drawings["reactions"] = diagrams.graph("Required reactions", x, [(rt, "rₜ", "reaction", "solid"),
                                                                         (rn, "rₙ", "ink", "dashed")],
                                               xlabel, "density [kN/m]", s=path.s, xticks=ticks)
    res.data.update(S=S, N=N, rt=rt, rn=rn, rnu=rnu, margin=margin, path=path, state=st)
    arrows = []
    for i in arrow_at:
        arrows.append((path.xyz[i], rh[i] * ds, "reaction"))
        if ld["horizontal"]:
            arrows.append((path.xyz[i], lam * ld["ph"][i] * ds, "horizontal"))
        arrows.append((path.xyz[i], p[i] * np.array([0, 0, 1.0]) * ds, "vertical"))
    for a in st["actions"]:
        arrows.append((path.xyz[a["index"]], a["G"] * fs, "horizontal"))
        arrows.append((path.xyz[a["index"]], a["R"] * fs, "reaction"))
    res.spatial = _spatial(path.xyz, arrows, [(path.xyz[0], "ink", "start"), (path.xyz[-1], "ink", "end")],
                           "Densities drawn at 1 kN/m = %.3g m. Reactions end on the line, loads start "
                           "from it (vertical loads end on it)." % ds)
    res.tables["summary"] = Table("Summary", ["quantity", "value"], [list(r) for r in res.summary])
    return res


def _contact_drawings(res, project, path, problem, ld, x, xlabel, ticks, margin, rt, rnu, eta, T, lam, ex):
    c = project.contact
    i = int(np.argmin(margin))
    nu = "rₙ" if project.support.wall == "right" else "−rₙ"
    res.drawings["margin"] = diagrams.graph(
        "Contact margin, η = %.3g" % eta, x, [(margin, "min(%s, η %s − |rₜ|)" % (nu, nu), "ink", "solid")], xlabel,
        "margin [kN/m]", s=path.s, shade_below=True, xticks=ticks,
        markers=[(x[i], margin[i], "least", "reaction")])
    res.drawings["cone"] = diagrams.cone(rt, rnu, eta, s=path.s, nu=nu)
    T0 = problem.minimum_preload(0.0)
    T0 = T0[0] if T0 is not None else None
    if not ld["horizontal"]:
        return
    Lint = problem.multiplier_interval(T)
    finite = [abs(v) for v in ((Lint["lo"], Lint["hi"]) if Lint else ()) if np.isfinite(v)]
    lam_hi = c.lam_max if c.lam_max > 0 else 1.5 * max([abs(lam), 1.0] + finite)
    T_hi = c.T_max if c.T_max > 0 else 2.0 * max(T, T0 or 0.0, 1.0)
    vertices = problem.region((0.0, T_hi), (-lam_hi, lam_hi))
    res.drawings["region"] = diagrams.region(vertices, T, lam, (0.0, T_hi), (-lam_hi, lam_hi))
    if not vertices.size:
        res.messages.append("No pair of preload and load multiplier in the window satisfies the contact cone.")
    if ld["profile"] is None:
        return
    unit, scale = ld["unit"]
    profile = ld["profile"] / scale
    betas = np.linspace(-np.pi, np.pi, 241)
    crit = []
    for b in betas:
        v = problem.critical_load(T, profile, b, lam_cap=4.0 * lam_hi * abs(scale))
        crit.append(np.nan if v is None else v)
    crit = np.array(crit)
    beta = ld["beta"]
    if np.all(np.isnan(crit)):
        res.messages.append("At T = %g kN no horizontal load is admissible: the vertical loads alone already "
                            "leave the contact cone (T_min = %s)." % (T, _g(T0, "kN")))
    else:
        crit = np.nan_to_num(crit, nan=0.0)
        pts = crit[:, None] * np.column_stack((np.cos(betas), np.sin(betas)))
        cur = lam * scale * np.array([np.cos(beta), np.sin(beta)])
        label = unit.split(" [")[0] if unit else "λ"
        d = diagrams.load_domain(pts, cur, unit if unit else "λ",
                                 title="Admissible horizontal loads at T = %g kN" % T)
        d.notes.append("The horizontal load of the model turned to every direction β and scaled; "
                       "the boundary is the largest admissible %s along each direction." % label)
        if ex is not None:
            hc = critical_horizontal_circle(0.0 - np.radians(project.geometry.helix.theta_start) + beta, T,
                                            radius=ex["radius"], grade=ex["grade"], weight=ex["weight"],
                                            eta=ex["eta"], theta_end=ex["theta_end"])
            res.data["critical_exact"] = hc
        res.drawings["domain"] = d
        k0 = int(np.argmin(np.abs(betas - np.arctan2(np.sin(beta), np.cos(beta)))))
        res.data["critical"] = float(crit[k0])
    # minimum preload along three directions
    grid = np.linspace(0.0, lam_hi * abs(scale), 121)
    series = []
    styles = ["solid", "dashed", "dotted"]
    roles = ["ink", "vertical", "reaction"]
    for j, db in enumerate((0.0, 90.0, 180.0)):
        b = beta + np.radians(db)
        vals = []
        for g in grid:
            m = problem.minimum_preload(g, profile, b)
            vals.append(np.nan if m is None else m[0])
        series.append((np.array(vals), "β = %.4g°" % np.degrees(np.arctan2(np.sin(b), np.cos(b))), roles[j],
                       styles[j]))
    d = diagrams.graph("Minimum preload along the load ray", grid, series,
                       (unit if unit else "λ"), "minimum preload [kN]", zero=True,
                       markers=[(lam * scale, T, "model", "reaction")])
    d.polyline([[grid[0], T], [grid[-1], T]], role="gray", width=0.7, style="dashed", layer="preload")
    res.drawings["preload"] = d


# ----------------------------------------------------------------- path without reactions

def run_reaction_free(project):
    res = Result(project)
    rf = project.reaction_free
    if rf.mode == "check":
        path, acts, msgs = _path_with_actions(project)
        res.messages += msgs
    else:
        path, acts = build_path(project.geometry), []
    nodes = [a for a, _ in acts]
    x, xlabel, ticks = abscissa(project, path.s, path.theta)
    res.summary += [("Geometry", describe_geometry(project.geometry)),
                    ("Projected length L", _g(path.L, "m"))]
    if rf.mode == "check":
        ld = build_loads(project.loads, path.s, path.J)
        p = ld["pv"] + ld["lam"] * ld["ph"]
        comp = compatibility(path, p, acts)
        F, S = comp["F"], comp["S"]
        ok = comp["relative_error"] < 1e-6
        i = int(np.argmax(comp["error_norm"]))
        res.summary += [("Best initial force C", _g(comp["C"], "kN")),
                        ("Largest transverse force |F − S u|", "%s at %s" % (_g(comp["maximum_error"], "kN"),
                                                                           _at(path, i))),
                        ("Relative to the force", "%.2e" % comp["relative_error"]),
                        ("Verdict", "the path is an axial equilibrium of these loads" if ok else
                         "no initial force makes the path an axial equilibrium of these loads")]
        if not ok:
            res.messages.append("The assigned path is not compatible with these loads without reactions: "
                                "the force F = C − P has a transverse part of up to %.4g kN for every C. "
                                "A lateral support (supported path) or a different geometry is needed."
                                % comp["maximum_error"])
        res.drawings["residual"] = diagrams.graph(
            "Transverse force of the best fit", x, [(comp["error_norm"], "|F − S u|", "reaction", "solid")],
            xlabel, "force [kN]", s=path.s, xticks=ticks)
        bal_points = [(path.xyz[node_index(path.s, a)], G) for a, G in acts]
        p_show = p
    elif rf.mode == "fixed_plane":
        out = fixed_plane(path, rf.B, rf.beta)
        F, S, p_show = out["F"], out["S"], out["p"]
        p = p_show
        res.summary += [("Conserved component F · m", _g(rf.B, "kN")),
                        ("Load plane", "spanned by e₃ and d = (cos β, sin β, 0), β = %g°" % rf.beta),
                        ("Horizontal density h = p · d", "%s to %s" % (_g(out["h"].min(), "kN/m"),
                                                                       _g(out["h"].max(), "kN/m"))),
                        ("Vertical density p₃", "%s to %s" % (_g(p[:, 2].min(), "kN/m"), _g(p[:, 2].max(), "kN/m")))]
        res.drawings["loads"] = diagrams.graph(
            "Compatible loads", x, [(out["h"], "h", "horizontal", "solid"), (p[:, 2], "p₃", "vertical", "dashed")],
            xlabel, "density [kN/m]", s=path.s, xticks=ticks)
        bal_points = []
    elif rf.mode == "thrust":
        Sfun = _poly(rf.thrust)
        Sd = L.polynomial_derivative(rf.thrust)
        out = loads_for_thrust(path, Sfun(path.s), Sd(path.s))
        F, S, p_show = out["F"], out["S"], out["p"]
        p = p_show
        res.summary.append(("Prescribed thrust S(s)", " + ".join("%g s^%d" % (c, k) if k else "%g" % c
                                                                for k, c in enumerate(rf.thrust) if c or k == 0)
                            + " kN"))
        res.drawings["loads"] = diagrams.graph(
            "Required loads", x, [(p[:, 0], "p₁", "horizontal", "solid"), (p[:, 1], "p₂", "reaction", "dashed"),
                                  (p[:, 2], "p₃", "vertical", "dotted")],
            xlabel, "density [kN/m]", s=path.s, xticks=ticks)
        bal_points = []
    else:
        raise InputError("Unknown mode %s" % rf.mode)
    N = S * path.J
    comp_ok = bool(np.all(S <= 1e-9 * max(np.max(np.abs(S)), 1e-12)))
    res.summary += [("Thrust S", "%s to %s" % (_g(S.max(), "kN"), _g(S.min(), "kN"))),
                    ("Axial force N", "%s to %s" % (_g(N.max(), "kN"), _g(N.min(), "kN"))),
                    ("Compression", "S ≤ 0 along the whole path" if comp_ok else "lost: S > 0 on part of the path")]
    if not comp_ok:
        i = int(np.argmax(S))
        res.messages.append("The force is a tension on part of the path (S = %.4g kN at %s): this branch is "
                            "not a compression path. Reverse the sign of the conserved component or shorten "
                            "the path." % (S[i], _at(path, i)))
    bal = global_balance(path.s, path.xyz, F, p, None, bal_points)
    local = _local(path.s, F, p) if rf.mode != "check" or not acts else None
    res.summary.append(("Global balance (normalised)", "force %.1e, moment %.1e" % (
        bal["force_relative"], bal["moment_relative"])))
    res.tables["balance"] = _balance_table(bal, local)
    if rf.mode == "check" and not ok:
        res.tables["balance"].note += (" Here the force F = C − P balances the loads, but it is not "
                                       "tangent to the path, so its moment does not balance: the "
                                       "moment residual measures the incompatibility.")
    idx = station_indices(path.s, project.output.stations, nodes)
    cols = ["s [m]"] + (["θ [rad]"] if path.theta is not None else []) + [
        "x₁ [m]", "x₂ [m]", "x₃ [m]", "S [kN]", "N [kN]", "F₁ [kN]", "F₂ [kN]", "F₃ [kN]",
        "p₁ [kN/m]", "p₂ [kN/m]", "p₃ [kN/m]"]
    rows = []
    for i in idx:
        row = [_f(path.s[i])] + ([_f(path.theta[i])] if path.theta is not None else [])
        row += [_f(v) for v in path.xyz[i]] + [_f(S[i]), _f(N[i])] + [_f(v) for v in F[i]] + [_f(v) for v in p_show[i]]
        rows.append(row)
    res.tables["stations"] = Table("Stations", cols, rows)
    span = _span(path.xyz)
    arrow_at = diagrams.stations_for_arrows(path.s, 10, nodes)
    ph = p_show.copy()
    ph[:, 2] = 0.0
    maxd = max(float(np.max(np.linalg.norm(ph, axis=1))), 1e-9)
    ds = diagrams.density_scale(span, maxd)
    res.drawings["plan"] = diagrams.plan(path.xyz, "Plan with the horizontal loads", path.s,
                                         loads=ph if maxd > 1e-9 else None, ds=ds, arrow_at=arrow_at,
                                         point_loads=[(path.xyz[node_index(path.s, a)], G) for a, G in acts],
                                         fs=diagrams.force_scale(span, max([np.linalg.norm(G) for _, G in acts] + [1e-9])))
    res.drawings["elevation"] = diagrams.elevation(path.s, path.xyz, nodes=nodes)
    res.drawings["forces"] = diagrams.graph("Thrust and axial force", x, [(S, "S", "ink", "solid"),
                                                                          (N, "N", "vertical", "dashed")],
                                            xlabel, "force [kN]", s=path.s, xticks=ticks)
    if "loads" not in res.drawings:
        res.drawings["loads"] = diagrams.graph(
            "Loads", x, [(p_show[:, 0], "p₁", "horizontal", "solid"), (p_show[:, 1], "p₂", "reaction", "dashed"),
                         (p_show[:, 2], "p₃", "vertical", "dotted")], xlabel, "density [kN/m]", s=path.s,
            xticks=ticks)
    arrows = []
    for i in arrow_at:
        arrows.append((path.xyz[i], ph[i] * ds, "horizontal"))
        arrows.append((path.xyz[i], np.array([0, 0, p_show[i, 2]]) * ds, "vertical"))
    res.spatial = _spatial(path.xyz, arrows, [(path.xyz[0], "ink", "start"), (path.xyz[-1], "ink", "end")],
                           "Densities drawn at 1 kN/m = %.3g m. No reaction acts on the line." % ds)
    res.data.update(S=S, N=N, F=F, p=p_show, path=path)
    res.tables["summary"] = Table("Summary", ["quantity", "value"], [list(r) for r in res.summary])
    return res


# ----------------------------------------------------------------- form-finding

def _form_problem(project):
    fm = project.form
    length = float(fm.length)
    if length <= 0:
        raise InputError("The projected length must be positive")
    acts, msgs = point_actions(project, length)
    s = piecewise_grid(length, _samples(fm.samples), [a for a, _ in acts])
    lo = project.loads
    x0 = np.asarray(fm.start, dtype=float)
    lam = float(lo.multiplier)
    if lo.vertical_mode == "actual":
        wfun = _poly(lo.w)
        unit = np.array([0.0, 0.0, -1.0])
        extra = np.zeros((len(s), 3))
        if lo.horizontal_mode == "pseudo":
            d = L.direction(lo.beta)
            unit = unit + lam * float(lo.gamma) * d
        else:
            extra = lam * build_loads(lo, s, vertical=False)["ph"]

        def solve(C):
            return self_weight_curve(s, C, wfun, extra, x0, acts, unit)
        constant = None
    else:
        ld = build_loads(lo, s)
        p = ld["pv"] + lam * ld["ph"]

        def solve(C):
            return free_curve(s, C, p, x0, acts)
        constant = p[0] if (not acts and np.allclose(p, p[0][None, :], atol=1e-14, rtol=0)) else None
    return s, acts, msgs, x0, solve, constant


def run_form_finding(project):
    res = Result(project)
    fm = project.form
    s, acts, msgs, x0, solve, constant = _form_problem(project)
    res.messages += msgs
    nodes = [a for a, _ in acts]
    history = None
    if fm.mode == "endpoint":
        target = np.asarray(fm.target, dtype=float)
        if project.loads.vertical_mode == "actual":
            def end(C):
                try:
                    return solve(C)["xyz"][-1] - x0
                except ValueError:
                    return None

            def jac(C):
                J = np.zeros((3, 3))
                for k in range(3):
                    h = 1e-6 * max(1.0, abs(C[k]))
                    e = np.zeros(3)
                    e[k] = h
                    a, b = end(C + e), end(C - e)
                    if a is None or b is None:
                        raise ValueError("The curve is not regular near the current estimate")
                    J[:, k] = (a - b) / (2 * h)
                return J
            C, history, converged = solve_endpoint(s, None, x0, target, fm.guess, acts, end=end, jac=jac,
                                                   tol=1e-10)
        else:
            p = solve(np.asarray(fm.guess, float))["p"]
            C, history, converged = solve_endpoint(s, p, x0, target, fm.guess, acts)
        if not converged:
            res.messages.append("The endpoint correction stopped before reaching the target "
                                "(mismatch %.3g m)." % history[-1]["error"])
    elif fm.mode == "initial":
        C = np.asarray(fm.force, dtype=float)
    else:
        raise InputError("Unknown mode %s" % fm.mode)
    cur = solve(C)
    xyz, F, S, N, p = cur["xyz"], cur["F"], cur["S"], cur["N"], cur["p"]
    p_s = derivative(p, s)
    kappa, tau = curvature_torsion(F, p, p_s)
    res.summary += [("Projected length L", _g(s[-1], "m")),
                    ("Start x*(0)", _g(x0, "m")),
                    ("Initial force C = F(0)", _g(C, "kN")),
                    ("End x*(L)", _g(xyz[-1], "m")),
                    ("Force at the end F(L)", _g(F[-1], "kN")),
                    ("Length of the curve", _g(integral(np.linalg.norm(F, axis=1) / cur["Q"], s), "m")),
                    ("Thrust S = −Q", "%s to %s" % (_g(S.max(), "kN"), _g(S.min(), "kN"))),
                    ("Axial force N = −|F|", "%s to %s" % (_g(N.max(), "kN"), _g(N.min(), "kN"))),
                    ("Least horizontal force Q", _g(cur["Q"].min(), "kN"))]
    if history is not None:
        res.summary += [("Target x*(L)", _g(fm.target, "m")),
                        ("Force updates", "%d, final mismatch %.2e m" % (len(history) - 1, history[-1]["error"]))]
        if project.loads.vertical_mode != "actual":
            p_now = solve(C)["p"]
            J = endpoint_jacobian(s, C, p_now, acts)
            K = -J[:2, :2]
            ev = np.sort(np.linalg.eigvals(0.5 * (K + K.T)).real)
            res.summary.append(("Eigenvalues of K", "%s and %s m/kN" % (_g(ev[0]), _g(ev[1]))))
            res.data["K_eigenvalues"] = ev
    d0 = p[0]
    dist, nrm = plane_distance(xyz, x0, C, d0)
    planar = False
    if dist is not None:
        dmax = float(np.max(np.abs(dist)))
        planar = dmax < 1e-9 * max(_span(xyz), 1.0)
        res.summary.append(("Distance from the plane of C and p(0)",
                            "zero: the curve is plane" if planar else "up to %s" % _g(dmax, "m")))
        res.data["plane_distance"] = dist
    if constant is not None:
        closed = constant_load_curve(s, C, constant, x0)
        if closed is not None:
            err = float(np.max(np.linalg.norm(closed - xyz, axis=1)))
            res.summary.append(("Closed form (Appendix B) against quadrature", "%.2e m" % err))
            res.data["closed_form_error"] = err
    bal = global_balance(s, xyz, F, p, None, [(xyz[node_index(s, a)], G) for a, G in acts])
    local = _local(s, F, p)
    res.summary.append(("Global balance (normalised)", "force %.1e, moment %.1e" % (
        bal["force_relative"], bal["moment_relative"])))
    res.tables["balance"] = _balance_table(bal, local)
    idx = station_indices(s, project.output.stations, nodes)
    rows = []
    for i in idx:
        rows.append([_f(s[i])] + [_f(v) for v in xyz[i]] + [_f(v) for v in F[i]] + [_f(S[i]), _f(N[i])] +
                    [_f(kappa[i], 6), "" if not np.isfinite(tau[i]) else _f(tau[i], 6)] + [_f(v) for v in p[i]])
    res.tables["stations"] = Table("Stations", ["s [m]", "x₁ [m]", "x₂ [m]", "x₃ [m]", "F₁ [kN]", "F₂ [kN]",
                                                "F₃ [kN]", "S [kN]", "N [kN]", "κ [1/m]", "τ [1/m]",
                                                "p₁ [kN/m]", "p₂ [kN/m]", "p₃ [kN/m]"], rows)
    if history is not None:
        res.tables["newton"] = Table("Endpoint correction", ["update", "C₁ [kN]", "C₂ [kN]", "C₃ [kN]",
                                                             "x₁(L) [m]", "x₂(L) [m]", "x₃(L) [m]", "mismatch [m]"],
                                     [[h["iteration"]] + [_f(v, 8) for v in h["C"]] + [_f(v, 8) for v in h["endpoint"]]
                                      + ["%.3e" % h["error"]] for h in history],
                                     "Damped Newton correction with the exact endpoint Jacobian (finite "
                                     "differences for a weight per actual length).")
    span = _span(xyz)
    arrow_at = diagrams.stations_for_arrows(s, 10, nodes)
    ph = p.copy()
    ph[:, 2] = 0.0
    maxd = max(float(np.max(np.linalg.norm(ph, axis=1))), 1e-9)
    ds = diagrams.density_scale(span, maxd)
    fs = diagrams.force_scale(span, max([np.linalg.norm(G) for _, G in acts] + [1e-9]))
    res.drawings["plan"] = diagrams.plan(xyz, "Plan of the curve", s, loads=ph if maxd > 1e-9 else None, ds=ds,
                                         arrow_at=arrow_at, fs=fs,
                                         point_loads=[(xyz[node_index(s, a)], G) for a, G in acts],
                                         marks=[(fm.target, "target", "reaction")] if history is not None else ())
    res.drawings["elevation"] = diagrams.elevation(s, xyz, nodes=nodes)
    res.drawings["forces"] = diagrams.graph("Thrust and axial force", s, [(S, "S", "ink", "solid"),
                                                                          (N, "N", "vertical", "dashed")],
                                            "s [m]", "force [kN]", s=s)
    res.drawings["curvature"] = diagrams.graph("Curvature and torsion", s, [(kappa, "κ", "ink", "solid"),
                                                                            (tau, "τ", "reaction", "dashed")],
                                               "s [m]", "[1/m]", s=s)
    if dist is not None and not planar:
        res.drawings["plane"] = diagrams.graph("Distance from the plane of C and p(0)", s,
                                               [(dist, "distance", "ink", "solid")], "s [m]", "[m]", s=s)
    if history is not None:
        res.drawings["newton"] = diagrams.newton(history)
        curves = []
        for h in history:
            try:
                curves.append(solve(h["C"])["xyz"])
            except ValueError:
                pass
        res.drawings["iterates"] = diagrams.iterates_elevation(curves, s)
    arrows = []
    for i in arrow_at:
        if maxd > 1e-9:
            arrows.append((xyz[i], ph[i] * ds, "horizontal"))
        arrows.append((xyz[i], np.array([0, 0, p[i, 2]]) * ds, "vertical"))
    for a, G in acts:
        arrows.append((xyz[node_index(s, a)], G * fs, "horizontal"))
    markers = [(xyz[0], "ink", "start"), (xyz[-1], "ink", "end")]
    if history is not None:
        markers.append((np.asarray(fm.target, float), "reaction", "target"))
    res.spatial = _spatial(xyz, arrows, markers, "Densities drawn at 1 kN/m = %.3g m." % ds)
    res.data.update(s=s, xyz=xyz, F=F, S=S, N=N, kappa=kappa, tau=tau, C=C, history=history, p=p)
    res.tables["summary"] = Table("Summary", ["quantity", "value"], [list(r) for r in res.summary])
    return res


# ----------------------------------------------------------------- node

def run_node(project):
    res = Result(project)
    nd = project.node
    out = node(nd.force_before, nd.load, nd.reaction)
    seg = float(nd.segment) if nd.segment > 0 else 2.0
    res.summary += [("Force before the node F⁻", _g(out["Fm"], "kN")),
                    ("Point force G", _g(out["G"], "kN")),
                    ("Point reaction R", _g(out["R"], "kN")),
                    ("Force after the node F⁺ = F⁻ − G − R", _g(out["Fp"], "kN")),
                    ("Axial forces N⁻, N⁺", "%s, %s" % (_g(out["Nm"], "kN"), _g(out["Np"], "kN"))),
                    ("Tangent before T⁻", _g(out["Tm"])), ("Tangent after T⁺", _g(out["Tp"])),
                    ("Change of tangent", _g(out["angle"], "°")),
                    ("Closure of the force polygon", "%.1e kN" % out["residual"])]
    if min(out["Qm"], out["Qp"]) < 1e-9:
        res.messages.append("A member is vertical: its horizontal force vanishes and the projected length "
                            "cannot describe it.")
    rows = []
    for name, v in (("F⁻", out["Fm"]), ("G", out["G"]), ("R", out["R"]), ("F⁺", out["Fp"]),
                    ("T⁻", out["Tm"]), ("T⁺", out["Tp"])):
        rows.append([name] + [_f(c, 6) for c in v] + [_f(np.linalg.norm(v), 6)])
    res.tables["vectors"] = Table("Vectors", ["vector", "x₁", "x₂", "x₃", "magnitude"], rows,
                                  "Forces in kN, tangents dimensionless. Compression: T = −F / |F|.")
    fs = 0.5 * seg / max(np.linalg.norm(out["G"]), np.linalg.norm(out["R"]), 1e-9)
    res.drawings["node_plan"] = diagrams.node_projection(out, (0, 1), "Node, plan", seg, fs)
    res.drawings["node_elevation"] = diagrams.node_projection(out, (0, 2), "Node, elevation on x₁ x₃", seg, fs)
    res.drawings["polygon"] = diagrams.node_polygon(out)
    pts = np.array([-seg * out["Tm"], np.zeros(3), seg * out["Tp"]])
    arrows = [(np.zeros(3), out["G"] * fs, "horizontal")]
    if np.linalg.norm(out["R"]) > 0:
        arrows.append((np.zeros(3), out["R"] * fs, "reaction"))
    res.spatial = dict(xyz=pts, arrows=arrows, markers=[(np.zeros(3), "ink", "node")],
                       note="Point forces drawn at 1 kN = %.3g m." % fs)
    res.data.update(node=out)
    res.tables["summary"] = Table("Summary", ["quantity", "value"], [list(r) for r in res.summary])
    return res


RUNNERS = {"supported": run_supported, "reaction_free": run_reaction_free,
           "form_finding": run_form_finding, "node": run_node}

# The plane tasks use the helpers above, so they are imported after them.
from .plane_analysis import run_arch, run_plane_funicular  # noqa: E402

RUNNERS.update(plane_funicular=run_plane_funicular, arch=run_arch)


def run(project):
    """Results of the task of the project, or InputError when the data are inconsistent."""
    if project.task not in RUNNERS:
        raise InputError("Unknown task %s" % project.task)
    try:
        with np.errstate(all="ignore"):
            return RUNNERS[project.task](project)
    except InputError:
        raise
    except (ValueError, np.linalg.LinAlgError, ZeroDivisionError) as exc:
        raise InputError(str(exc))
