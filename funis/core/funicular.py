"""Paths without reactions, form-finding of free curves and node equilibrium.

Without reactions, F_{,s} + p = 0 gives F = C - P(s) with P the primitive of
the loads (and the jumps of the point actions), and an assigned path is in
axial equilibrium only if (C - P) x u = 0 everywhere (Section 3). For a
free curve the force fixes the tangent, x*_{,s} = -F / Q with Q = |F_h|, so
the curve follows from the initial force by quadrature, S = -Q and
N = -|F| (Section 4). The endpoint map E(C) and its Jacobian select the
initial force that reaches a prescribed support (damped Newton correction).
"""
import numpy as np
from scipy.integrate import solve_ivp

from .geometry import E3
from .grid import after, cumulative, derivative, integral, pieces

EPS = 1e-12


# ---------------------------------------------------------------- assigned path, no reactions

def primitive(s, p, actions=()):
    """P(s) = integral of p from 0 to s plus the point forces already passed."""
    P = cumulative(p, s)
    for s_j, G in actions:
        P = P + after(s, s_j)[:, None] * np.asarray(G, dtype=float)[None, :]
    return P


def compatibility(path, p, actions=()):
    """Least-squares initial force C of F = C - P parallel to u, and its residual.

    A residual that is not small disproves axial equilibrium of the assigned
    path for these loads (whatever C), within the sampling.
    """
    P = primitive(path.s, p, actions)
    u = path.u
    uu = np.sum(u * u, axis=1)
    proj = np.eye(3)[None, :, :] - np.einsum("ni,nj->nij", u, u) / uu[:, None, None]
    C = np.linalg.lstsq(proj.reshape(-1, 3), np.einsum("nij,nj->ni", proj, P).ravel(), rcond=None)[0]
    F = C[None, :] - P
    S = np.sum(F * u, axis=1) / uu
    error = F - S[:, None] * u
    e = np.linalg.norm(error, axis=1)
    scale = max(float(np.max(np.linalg.norm(F, axis=1))), float(np.max(np.linalg.norm(P, axis=1))), EPS)
    return dict(C=C, F=F, S=S, N=S * path.J, P=P, error=error, error_norm=e,
                maximum_error=float(np.max(e)), relative_error=float(np.max(e) / scale))


def loads_for_thrust(path, S, S_s):
    """Loads that keep F = S u in equilibrium without reactions: p = -(S u)_{,s}."""
    u = path.u
    us = path.rho[:, None] * path.n
    us[:, 2] = path.fss
    p = -(S_s[:, None] * u + S[:, None] * us)
    return dict(S=S, N=S * path.J, F=S[:, None] * u, p=p)


def fixed_plane(path, B, beta_deg):
    """Thrust and loads of the reaction-free family with loads in a fixed vertical plane.

    The loads lie in the plane spanned by e3 and d = (cos beta, sin beta, 0),
    so the component of F along m = e3 x d is conserved, F . m = B, which
    gives S = B / (t . m). Valid where t . m does not vanish (Section 3).
    """
    b = np.radians(float(beta_deg))
    d = np.array([np.cos(b), np.sin(b), 0.0])
    m = np.cross(E3, d)
    tm = np.sum(path.t * m, axis=1)
    nm = np.sum(path.n * m, axis=1)
    if np.min(np.abs(tm)) < 1e-6:
        raise ValueError("The path turns parallel to the load plane (t . m = 0): the conserved "
                         "component cannot be carried there. Shorten the path.")
    S = float(B) / tm
    S_s = -float(B) * path.rho * nm / tm ** 2
    out = loads_for_thrust(path, S, S_s)
    out.update(direction=d, normal=m, h=np.sum(out["p"] * d, axis=1),
               transverse=np.sum(out["p"] * m, axis=1))
    return out


# ---------------------------------------------------------------- free curves

def force_field(s, C, p, actions=()):
    return np.asarray(C, dtype=float)[None, :] - primitive(s, p, actions)


def curve_from_force(s, F, x0):
    """x* = x0 - integral of F / Q, piece by piece across the point actions."""
    Q = np.linalg.norm(F[:, :2], axis=1)
    if np.min(Q) < 1e-9 * max(float(np.max(np.linalg.norm(F, axis=1))), 1.0):
        i = int(np.argmin(Q))
        raise ValueError("The horizontal force vanishes at s = %.4g m: the projected length "
                         "is no longer a regular parameter" % s[i])
    return np.asarray(x0, dtype=float)[None, :] + cumulative(-F / Q[:, None], s), Q


def free_curve(s, C, p, x0, actions=()):
    F = force_field(s, C, p, actions)
    xyz, Q = curve_from_force(s, F, x0)
    return dict(s=s, xyz=xyz, F=F, S=-Q, N=-np.linalg.norm(F, axis=1), p=p, Q=Q)


def endpoint(s, C, p, actions=()):
    F = force_field(s, C, p, actions)
    Q = np.linalg.norm(F[:, :2], axis=1)
    if np.min(Q) < 1e-9:
        return None
    return integral(-F / Q[:, None], s)


def endpoint_jacobian(s, C, p, actions=()):
    """dE/dC = integral of (-I / Q + F (F_h, 0)^T / Q^3), m/kN."""
    F = force_field(s, C, p, actions)
    Q = np.linalg.norm(F[:, :2], axis=1)
    J = -np.eye(3)[None, :, :] / Q[:, None, None]
    J[:, :, :2] += np.einsum("ni,nj->nij", F, F[:, :2]) / Q[:, None, None] ** 3
    return integral(J.reshape(len(s), 9), s).reshape(3, 3)


def solve_endpoint(s, p, x0, target, guess, actions=(), tol=1e-11, iterations=40, jac=None,
                   end=None):
    """Damped Newton correction of the initial force to reach the target support.

    A step is halved until the endpoint mismatch decreases and the horizontal
    force stays away from zero, so that every iterate is a regular curve.
    Returns the force, the history and the converged flag.
    """
    end = end or (lambda C: endpoint(s, C, p, actions))
    jac = jac or (lambda C: endpoint_jacobian(s, C, p, actions))
    goal = np.asarray(target, dtype=float) - np.asarray(x0, dtype=float)
    C = np.asarray(guess, dtype=float).copy()
    E = end(C)
    if E is None:
        raise ValueError("The initial estimate of the force gives a vanishing horizontal force")
    history = []
    for k in range(iterations):
        error = float(np.linalg.norm(E - goal))
        history.append(dict(iteration=k, C=C.copy(), endpoint=E + x0, error=error))
        if error < tol * max(1.0, float(np.linalg.norm(goal))):
            return C, history, True
        Jk = jac(C)
        try:
            delta = np.linalg.solve(Jk, goal - E)
        except np.linalg.LinAlgError:
            raise ValueError("The endpoint Jacobian is singular: the target cannot be reached by "
                             "correcting the force from this estimate")
        step = 1.0
        while step > 2 ** -30:
            trial = C + step * delta
            Et = end(trial)
            if Et is not None and np.linalg.norm(Et - goal) < error:
                break
            step *= 0.5
        else:
            raise ValueError("No correction of the initial force reduces the endpoint mismatch: "
                             "the target may be unreachable with a regular compressive curve")
        C, E = trial, Et
    return C, history, False


def self_weight_curve(s, C, w, p_extra, x0, actions=(), unit=(0.0, 0.0, -1.0)):
    """Free curve under a weight w per metre of actual length plus other loads.

    The density per projected metre is w |F| / Q times unit (downward, plus a
    proportional horizontal part for a pseudo-static action), which depends
    on the force, so position and force are integrated together (DOP853),
    piece by piece across the point actions.
    """
    unit = np.asarray(unit, dtype=float)
    s = np.asarray(s, dtype=float)
    acts = sorted(((float(a), np.asarray(G, dtype=float)) for a, G in actions), key=lambda r: r[0])
    xyz = np.zeros((len(s), 3))
    F = np.zeros((len(s), 3))
    state = np.r_[np.asarray(x0, dtype=float), np.asarray(C, dtype=float)]
    k = 0
    for i0, i1 in pieces(s):
        seg = s[i0:i1]
        if i0 > 0:
            while k < len(acts) and acts[k][0] <= seg[0] + 1e-12 * max(s[-1], 1.0):
                state = state.copy()
                state[3:] -= acts[k][1]
                k += 1
        wf = w(seg)
        pe = p_extra[i0:i1]

        def rhs(v, y, seg=seg, wf=wf, pe=pe):
            Fv = y[3:]
            Q = np.hypot(Fv[0], Fv[1])
            if Q < 1e-10:
                raise ValueError("The horizontal force vanishes: the projected length is no "
                                 "longer a regular parameter")
            wv = np.interp(v, seg, wf)
            pv = np.array([np.interp(v, seg, pe[:, j]) for j in range(3)])
            pv = pv + wv * np.linalg.norm(Fv) / Q * unit
            return np.r_[-Fv / Q, -pv]
        if seg[-1] > seg[0]:
            sol = solve_ivp(rhs, (seg[0], seg[-1]), state, t_eval=seg, method="DOP853",
                            rtol=1e-11, atol=1e-12)
            if not sol.success:
                raise ValueError(sol.message)
            Y = sol.y.T
        else:
            Y = np.tile(state, (len(seg), 1))
        xyz[i0:i1], F[i0:i1] = Y[:, :3], Y[:, 3:]
        state = Y[-1]
    Q = np.linalg.norm(F[:, :2], axis=1)
    p = p_extra + (w(s) * np.linalg.norm(F, axis=1) / Q)[:, None] * unit[None, :]
    return dict(s=s, xyz=xyz, F=F, S=-Q, N=-np.linalg.norm(F, axis=1), p=p, Q=Q)


def curvature_torsion(F, p, p_s):
    """Curvature and signed torsion of a free curve from force and load (Section 4).

    kappa = Q |F x p| / |F|^3 and tau = -Q F . (p x p_s) / |F x p|^2, the
    torsion being undefined where kappa = 0 (returned as NaN).
    """
    F, p, p_s = (np.asarray(v, dtype=float) for v in (F, p, p_s))
    Q = np.linalg.norm(F[:, :2], axis=1)
    cross = np.cross(F, p)
    c2 = np.sum(cross * cross, axis=1)
    kappa = Q * np.sqrt(c2) / np.linalg.norm(F, axis=1) ** 3
    triple = np.sum(F * np.cross(p, p_s), axis=1)
    scale = max(float(np.max(c2)), EPS)
    with np.errstate(divide="ignore", invalid="ignore"):
        tau = np.where(c2 > 1e-14 * scale, -Q * triple / c2, np.nan)
    return kappa, tau


def plane_distance(xyz, x0, C, d):
    """Signed distance of the curve from the plane through x0 spanned by C and d."""
    nrm = np.cross(np.asarray(C, dtype=float), np.asarray(d, dtype=float))
    size = np.linalg.norm(nrm)
    if size < EPS:
        return None, None
    nrm = nrm / size
    return np.sum((np.asarray(xyz) - np.asarray(x0)[None, :]) * nrm, axis=1), nrm


def constant_load_curve(s, C, p, x0):
    """Closed forms of Appendix B for constant densities p = (h, 0, p3) after a rotation.

    The horizontal load is turned onto e1, the solution evaluated and turned
    back. Used as an independent check of the quadrature.
    """
    p = np.asarray(p, dtype=float)
    C = np.asarray(C, dtype=float)
    hh = float(np.hypot(p[0], p[1]))
    if hh > EPS:
        c, sn = p[0] / hh, p[1] / hh
    else:
        c, sn = 1.0, 0.0
    R = np.array([[c, sn, 0.0], [-sn, c, 0.0], [0.0, 0.0, 1.0]])
    A0, B, C0 = np.sum(R * C[None, :], axis=1)
    h, p3 = hh, float(p[2])
    A = A0 - h * s
    Q, Q0 = np.hypot(A, B), np.hypot(A0, B)
    if Q0 < EPS or np.min(Q) < EPS or (abs(B) < EPS and np.any(A * A0 <= 0)):
        return None
    if abs(h) < EPS:
        xyz = np.column_stack((-A0 * s / Q0, -B * s / Q0, (-C0 * s + p3 * s * s / 2) / Q0))
    elif abs(B) < EPS:
        sig, D = np.sign(A0), C0 - p3 * A0 / h
        xyz = np.column_stack((-sig * s, np.zeros_like(s),
                               sig * D / h * np.log(np.abs(A / A0)) - sig * p3 * s / h))
    else:
        I = (np.arcsinh(A0 / abs(B)) - np.arcsinh(A / abs(B))) / h
        D = C0 - p3 * A0 / h
        xyz = np.column_stack(((Q - Q0) / h, -B * I, -D * I + p3 * (Q - Q0) / h ** 2))
    return np.einsum("ni,ij->nj", xyz, R) + np.asarray(x0, dtype=float)[None, :]


# ---------------------------------------------------------------- node

def node(F_before, G, R=None):
    """Force after a node and the tangents of the two members (Section 5).

    [F] = F+ - F- = -G - R, T = -F / |F| in compression.
    """
    Fm = np.asarray(F_before, dtype=float)
    G = np.asarray(G, dtype=float)
    R = np.zeros(3) if R is None else np.asarray(R, dtype=float)
    Fp = Fm - G - R
    if np.linalg.norm(Fm) < EPS or np.linalg.norm(Fp) < EPS:
        raise ValueError("A member with zero force has no determined direction")
    Tm, Tp = -Fm / np.linalg.norm(Fm), -Fp / np.linalg.norm(Fp)
    angle = float(np.degrees(np.arccos(np.clip(np.sum(Tm * Tp), -1.0, 1.0))))
    return dict(Fm=Fm, Fp=Fp, G=G, R=R, Tm=Tm, Tp=Tp, angle=angle,
                Nm=-float(np.linalg.norm(Fm)), Np=-float(np.linalg.norm(Fp)),
                Qm=float(np.linalg.norm(Fm[:2])), Qp=float(np.linalg.norm(Fp[:2])),
                residual=float(np.linalg.norm(Fp - Fm + G + R)))


def local_residual(s, F, p, r=None):
    """Independent finite-difference balance F_{,s} + p + r, piece by piece."""
    total = np.asarray(p, dtype=float) + (0.0 if r is None else np.asarray(r, dtype=float))
    return derivative(F, s) + total
