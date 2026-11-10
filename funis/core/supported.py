"""Supported path: prescribed geometry, horizontal distributed reactions, r3 = 0.

Vertical balance integrates to V = C3 - P3(s), the grade gives S = V / f_s and
N = S J, and the two horizontal balances give the reactions the lateral
support must supply, r_t = -S_s - p_h . t and r_n = -rho S - p_h . n. Adding a
horizontal load leaves S unchanged and shifts the reaction by -p_h. A
concentrated force G at s_j with a horizontal point reaction and no vertical
point reaction gives the jump [S] = -G3 / f_s and R_h = (G3 / f_s) t - G_h.
"""
import numpy as np

from .grid import after, cumulative, integral, node_index

EPS = 1e-12


def preload_to_C3(path, preload):
    """C3 = V(0) for the compressive end thrust T = -S(0) at the initial end."""
    return -float(preload) * float(path.fs[0])


def wall_sign(wall):
    return -1.0 if wall == "left" else 1.0


def supported(path, p, C3, actions=(), wall="right"):
    """Forces and reactions of the supported path.

    p: densities (n, 3) on the grid of the path. C3: vertical component of
    the initial force. actions: list of (s_j, G) concentrated forces, the
    grid of the path repeating their abscissae. Reactions are forces on the
    line, per projected metre; r_nu = sign r_n with the wall on the right
    (sign +1) or on the left (sign -1) of the direction of travel.
    """
    s = path.s
    p = np.asarray(p, dtype=float)
    if p.shape != (len(s), 3):
        raise ValueError("The densities need one row per abscissa of the path")
    fs = path.fs
    if np.any(np.abs(fs) < 1e-9):
        raise ValueError("The path has a stationary elevation: vertical balance does not fix the "
                         "thrust there (f_s = 0)")
    P3 = cumulative(p[:, 2], s)
    V = float(C3) - P3
    acts = []
    for s_j, G in actions:
        G = np.asarray(G, dtype=float)
        V = V - G[2] * after(s, s_j)
        acts.append((float(s_j), G))
    S = V / fs
    J = path.J
    N = S * J
    Ss = (-p[:, 2] - S * path.fss) / fs
    pt = p[:, 0] * path.t[:, 0] + p[:, 1] * path.t[:, 1]
    pn = p[:, 0] * path.n[:, 0] + p[:, 1] * path.n[:, 1]
    rt = -Ss - pt
    rn = -path.rho * S - pn
    r = rt[:, None] * path.t + rn[:, None] * path.n
    F = S[:, None] * path.u
    sign = wall_sign(wall)
    rows = []
    sum_force = np.zeros(3)
    sum_moment = np.zeros(3)
    for s_j, G in acts:
        i = node_index(s, s_j)
        fsj = float(fs[i])
        jump = -G[2] / fsj
        R = (G[2] / fsj) * path.t[i] - np.array([G[0], G[1], 0.0])
        Rt, Rn = float(np.sum(R * path.t[i])), float(np.sum(R * path.n[i]))
        rows.append(dict(s=s_j, index=i, G=G, R=R, jump=jump, Rt=Rt, Rn=Rn, Rnu=sign * Rn,
                         theta=None if path.theta is None else float(path.theta[i])))
        sum_force += G + R
        sum_moment += np.cross(path.xyz[i], G + R)
    R0, RL = -F[0], F[-1]
    total = p + r
    force = R0 + RL + integral(total, s) + sum_force
    moment = (np.cross(path.xyz[0], R0) + np.cross(path.xyz[-1], RL)
              + integral(np.cross(path.xyz, total), s) + sum_moment)
    scale = (np.linalg.norm(R0) + np.linalg.norm(RL) + integral(np.linalg.norm(total, axis=1), s)
             + sum(np.linalg.norm(G) + np.linalg.norm(a["R"]) for a, (_, G) in zip(rows, acts)))
    extent = max(path.L, float(np.max(np.linalg.norm(path.xyz, axis=1))), 1e-9)
    return dict(S=S, V=V, N=N, Ss=Ss, F=F, p=p, r=r, rt=rt, rn=rn, rnu=sign * rn, R0=R0, RL=RL,
                C3=float(C3), T=float(-S[0]), actions=rows, sign=sign,
                compression=bool(np.all(S <= 1e-9 * max(np.max(np.abs(S)), EPS))),
                balance=dict(force=force, moment=moment,
                             force_relative=float(np.linalg.norm(force) / max(scale, EPS)),
                             moment_relative=float(np.linalg.norm(moment) / max(scale * extent, EPS))))
