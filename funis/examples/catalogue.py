"""Worked examples: the cases of the article, three reference cases and the plane cases.

The article is C. Olivieri, "Equilibrium and form-finding of spatial
compression paths under multidirectional loading through Linear Arch Static
Analysis". Figure and section numbers refer to it. The catenary, the
parabolic arch and the point force on case C are reference cases of the
application, not cases of the article, and so are the plane cases: the plane
funiculars, checked against their closed forms, and the arches, among them
the semicircular arch of least thickness under its own weight, whose
classical value t/R = 0.1075 with hinges near 54.5 degrees from the crown
the thrust line analysis reproduces.
"""
from collections import OrderedDict

import numpy as np

from ..core.funicular import constant_load_curve
from ..core.geometry import ellipse
from ..model import (ArchSpec, ContactSpec, EllipseSpec, FormSpec, FunicularSpec, GeometrySpec, HelixSpec,
                     LoadSpec, NodeSpec, OutputSpec, PointAction, Project, ReactionFreeSpec, SupportSpec)

F0 = [-3.0, -4.0, -2.0]


def _benchmark(name, theta_end=360.0, h=2.0, notes=""):
    p = Project(name=name, task="supported")
    p.geometry = GeometrySpec(kind="helix", helix=HelixSpec(2.0, -1.0, 0.0, theta_end))
    p.loads = LoadSpec(vertical_mode="density", w=[1.0, 0, 0, 0],
                       horizontal_mode="fixed" if h else "none", h=[h, 0, 0, 0], beta=0.0)
    p.support = SupportSpec(preload=8.0, wall="right")
    p.contact = ContactSpec(enabled=True, mu=0.6, strip=0.8, delta=0.5)
    p.notes = notes
    return p


def supported_fig2():
    return _benchmark(
        "Fig. 2: reaction shift on the supported circular path", np.degrees(2.7), 2.0,
        "Circular helix R = 2 m, c = −1 m/rad, 0 ≤ θ ≤ 2.7 rad, p₃ = −1 kN/m, S₀ = −8 kN and "
        "h = 2 kN/m along e₁. The horizontal load leaves the thrust unchanged and shifts the "
        "required reaction by −h e₁ (dashed: the reaction of the vertical load alone).")


def supported_benchmark():
    return _benchmark(
        "Figs. 12 and 13: supported circular benchmark, h = 2 kN/m", 360.0, 2.0,
        "Complete turn of the benchmark, S = −8 − 4θ, r_t = 2 + h sin θ, r_n = 4 + 2θ + h cos θ. "
        "Contact with μ = 0.6 and a centred strip L_sw = 0.8 m at δ = 0.5 m, so φ = 0.8 and "
        "η = 0.6. The Contact tab shows the admissible loads at T = 8 kN (Fig. 13a) and the "
        "minimum preload along three directions (Fig. 13b).")


def supported_h4():
    p = _benchmark(
        "Fig. 12: contact violated at h/w = 4", 360.0, 4.0,
        "The benchmark with h = 4 kN/m: the line stays in compression, while the required reaction "
        "leaves the contact cone near the start, so the contact margin is negative there.")
    return p


def supported_pseudo():
    p = _benchmark(
        "Section 5.3: pseudo-static action γ = 0.5", 360.0, 0.0,
        "Horizontal action proportional to the vertical load, h = γ w along e₁ with γ = 0.5. "
        "The axial force is unaffected and the minimum preload is 5.67 kN, against 6.67 kN "
        "without horizontal action.")
    p.loads.horizontal_mode = "pseudo"
    p.loads.gamma = 0.5
    return p


def supported_point():
    p = _benchmark(
        "Section 5.4: point force on the complete supported helix", 360.0, 1.0,
        "Point force G = (2, 0, −1) kN at θ = 5.7 rad (s = 11.4 m) with h = 1 kN/m. The thrust "
        "jumps by −G₃ / f,s = −2 kN and the horizontal point reaction R_h = (G₃ / f,s) t − G_h "
        "≈ (−0.90, 1.67, 0) kN satisfies the point contact cone with η = 0.6.")
    p.point_actions = [PointAction(s=11.4, G1=2.0, G2=0.0, G3=-1.0)]
    return p


def supported_ellipse(mode):
    if mode == "angle":
        name = "Fig. 10: elliptical path with f = cθ"
        pitch = -1.0
        text = "f = cθ with c = −1 m/rad"
    else:
        name = "Fig. 10: elliptical path with f = k_s s"
        L = ellipse(3.0, 2.0, -1.0, 0.0, 2 * np.pi, 2001).L
        pitch = float(-2 * np.pi / L)
        text = "f = k_s s with k_s = −2π / L = %.6f, for the same total drop of 2π m" % pitch
    p = Project(name=name, task="supported")
    p.geometry = GeometrySpec(kind="ellipse", ellipse=EllipseSpec(3.0, 2.0, pitch, mode, 0.0, 360.0))
    p.loads = LoadSpec(vertical_mode="density", w=[1.0, 0, 0, 0], horizontal_mode="fixed",
                       h=[1.0, 0, 0, 0], beta=0.0)
    p.support = SupportSpec(preload=8.0)
    p.contact = ContactSpec(enabled=False, mu=0.6)
    p.notes = ("Ellipse with semi-axes a = 3 m and b = 2 m, %s, p₃ = −1 kN/m, h = 1 kN/m along e₁ "
               "and S₀ = −8 kN. Both elevations share the projected curvature ab/g³ but not the "
               "grade, the axial force or the tangential reaction." % text)
    return p


def reaction_free_arc():
    p = Project(name="Fig. 9: exceptional reaction-free circular helical arc", task="reaction_free")
    a0, a1 = np.degrees(np.pi + 0.15), np.degrees(np.pi + 1.2)
    p.geometry = GeometrySpec(kind="helix", helix=HelixSpec(2.0, -1.0, a0, a1))
    p.reaction_free = ReactionFreeSpec(mode="fixed_plane", B=3.0, beta=0.0)
    p.notes = ("R = 2 m, c = −1 m/rad, B = 3 kN, π + 0.15 ≤ θ ≤ π + 1.2 rad. Loads in the plane of "
               "e₁ and e₃ conserve F₂ = B, so S = B / t₂ = B sec θ (compression for B > 0 inside "
               "π/2 < θ < 3π/2), with h = B a / (b g cos²θ) and p₃ = −B c sin θ / (b g cos²θ).")
    return p


def reaction_free_three():
    p = Project(name="Fig. 4: three-component loading on the complete helix", task="reaction_free")
    p.geometry = GeometrySpec(kind="helix", helix=HelixSpec(2.0, -1.0, 0.0, 360.0))
    p.reaction_free = ReactionFreeSpec(mode="thrust", thrust=[-8.0, -2.0, 0.0, 0.0])
    p.notes = ("The thrust S = −8 − 4θ = −8 − 2s kN of the benchmark carried without reactions: the "
               "loads p = −(S u),s have three components, p₁ = −2 sin θ + (−4 − 2θ) cos θ, "
               "p₂ = 2 cos θ + (−4 − 2θ) sin θ and p₃ = −1 kN/m, and vary in direction.")
    return p


def _fig3_points(bump):
    s = np.linspace(0.0, 5.0, 61)
    xyz = constant_load_curve(s, np.array(F0), np.array([0.7, 0.0, -1.0]), np.zeros(3))
    xyz[:, 2] += bump * np.sin(np.pi * s / 5.0)
    return [[float(v) for v in row] for row in xyz]


def reaction_free_check(bump):
    if bump:
        name = "Fig. 3: prescribed path that is not an axial equilibrium"
        text = ("The funicular of p = (0.7, 0, −1) kN/m and C = (−3, −4, −2) kN with 0.6 sin(πs/5) m "
                "added to its elevation. No initial force makes F = C − P parallel to its tangent.")
    else:
        name = "Fig. 3: the funicular of the same loads"
        text = ("The funicular of p = (0.7, 0, −1) kN/m and C = (−3, −4, −2) kN, given as a table of "
                "points: the best initial force recovers C and the transverse force vanishes within "
                "the interpolation of the points.")
    p = Project(name=name, task="reaction_free")
    p.geometry = GeometrySpec(kind="points", points=_fig3_points(bump))
    p.loads = LoadSpec(vertical_mode="density", w=[1.0, 0, 0, 0], horizontal_mode="fixed", h=[0.7, 0, 0, 0])
    p.reaction_free = ReactionFreeSpec(mode="check")
    p.output = OutputSpec(abscissa="s", stations=41)
    p.notes = text
    return p


def _free(name, horizontal, notes, mode="initial"):
    p = Project(name=name, task="form_finding")
    p.form = FormSpec(length=5.0, start=[0.0, 0.0, 0.0], mode=mode, force=list(F0))
    p.loads = LoadSpec(vertical_mode="density", w=[1.0, 0, 0, 0], **horizontal)
    p.output = OutputSpec(abscissa="s", stations=26)
    p.notes = notes
    return p


def free_constant():
    return _free("Fig. 8: funicular under constant loads, h/w = 1",
                 dict(horizontal_mode="fixed", h=[1.0, 0, 0, 0], beta=0.0),
                 "p = (h, 0, −w) with w = 1 kN/m and h/w = 1, C = (−3, −4, −2) kN, L = 5 m. Constant "
                 "loads: the curve lies in the plane of C and the load direction, and its plan bends "
                 "toward e₁. The article also draws h/w = 0, 0.5 and 2: change the coefficient a₀ of h.")


def free_a():
    return _free("Fig. 11: free curve, case A (parallel loads)",
                 dict(horizontal_mode="fixed", h=[0.7, 0, 0, 0], beta=0.0),
                 "p = (0.7, 0, −1) kN/m, C = (−3, −4, −2) kN, L = 5 m. Parallel loads: the curve lies in "
                 "the plane of C and the load direction and has zero torsion. The closed form of "
                 "Appendix B checks the quadrature.")


def free_b():
    return _free("Fig. 11: free curve, case B",
                 dict(horizontal_mode="fixed", h=[0.7, 0.2, 0, 0], beta=0.0),
                 "p = (0.7 + 0.2 s, 0, −1) kN/m, C = (−3, −4, −2) kN, L = 5 m. The load direction varies "
                 "and the curve leaves the plane of case A, up to about 0.32 m.")


def free_c():
    return _free("Figs. 5 and 11: free curve, case C",
                 dict(horizontal_mode="components", p1=[0.7, 0.2, 0, 0], p2=[0.0, 0.3, 0, 0]),
                 "p = (0.7 + 0.2 s, 0.3 s, −1) kN/m, C = (−3, −4, −2) kN, L = 5 m. The final support "
                 "x*(5 m) ≈ (3.58655144, 3.46958475, −0.09396228) m is an output of the construction.")


def free_c_endpoint():
    p = free_c()
    p.name = "Fig. 6: case C with a prescribed second support"
    p.form.mode = "endpoint"
    p.form.target = [3.58655144, 3.46958475, -0.09396228]
    p.form.guess = [-2.5, -3.5, -1.5]
    p.notes = ("The second support of case C is prescribed and the initial force is found by the damped "
               "Newton correction from (−2.5, −3.5, −1.5) kN: four updates reduce the mismatch from "
               "0.37 m to below 10⁻¹³ m and recover (−3, −4, −2) kN.")
    return p


def free_c_point():
    p = free_c()
    p.name = "Reference: case C with a point force at mid-length"
    p.point_actions = [PointAction(s=2.5, G1=0.5, G2=0.0, G3=-1.0)]
    p.notes = ("Case C with G = (0.5, 0, −1) kN at s = 2.5 m and no point reaction: the force jumps by "
               "−G and the tangent turns at the node, where the curve has a kink.")
    return p


def catenary():
    a = 4.0
    p = Project(name="Reference: catenary arch under self-weight", task="form_finding")
    p.form = FormSpec(length=5.0, start=[0.0, 0.0, 0.0], mode="initial",
                      force=[-4.0, 0.0, float(-4.0 * np.sinh(5.0 / (2 * a)))])
    p.loads = LoadSpec(vertical_mode="actual", w=[1.0, 0, 0, 0], horizontal_mode="none")
    p.output = OutputSpec(abscissa="s", stations=26)
    p.notes = ("Weight w = 1 kN per metre of actual length and horizontal thrust 4 kN: the inverted "
               "catenary x₃ = a [cosh(L/2a) − cosh((s − L/2)/a)], a = H/w = 4 m, from the force ODE.")
    return p


def parabola():
    p = Project(name="Reference: parabolic arch under a load per projected length", task="form_finding")
    p.form = FormSpec(length=5.0, start=[0.0, 0.0, 0.0], mode="initial", force=[-4.0, 0.0, -2.5])
    p.loads = LoadSpec(vertical_mode="density", w=[1.0, 0, 0, 0], horizontal_mode="none")
    p.output = OutputSpec(abscissa="s", stations=26)
    p.notes = ("w = 1 kN per projected metre and horizontal thrust 4 kN: the parabola "
               "x₃ = w s (L − s) / (2H) with constant thrust S = −4 kN.")
    return p


def node_fig7():
    p = Project(name="Fig. 7: node under a concentrated multidirectional force", task="node")
    p.node = NodeSpec(force_before=[-3.0, -2.0, -1.0], load=[2.0, 0.0, -1.0], reaction=[0.0, 0.0, 0.0],
                      segment=2.0)
    p.notes = ("F⁻ = (−3, −2, −1) kN and G = (2, 0, −1) kN give F⁺ = (−5, −2, 0) kN and a change of "
               "tangent of 19.4463°. No point reaction is used.")
    return p


def node_horizontal():
    p = node_fig7()
    p.name = "Section 5.4: node under a horizontal point force"
    p.node.load = [2.0, 0.0, 0.0]
    p.notes = "F⁻ = (−3, −2, −1) kN and G = (2, 0, 0) kN: the tangent turns by 12.6044°."
    return p


def _plane(name, notes, **kw):
    p = Project(name=name, task="plane_funicular")
    p.funicular = FunicularSpec(**kw)
    p.output = OutputSpec(abscissa="s", stations=21)
    p.notes = notes
    return p


def plane_catenary():
    return _plane("Plane: catenary through a point", "Weight w = 1 kN per metre of actual length, span 10 m, "
                  "through the crown (5, 3) m: the inverted catenary z = z_c − a cosh((x − x_c)/a), a = H/w, "
                  "against the integration of the force.", vertical_mode="actual", w=[1.0, 0, 0, 0],
                  selection="point", through=[5.0, 3.0])


def plane_parabola():
    return _plane("Plane: parabola through a point", "Load w = 1 kN per metre of x, span 10 m, through the "
                  "crown (5, 3) m: the parabola with constant thrust H = w L² / (8 f).", vertical_mode="density",
                  w=[1.0, 0, 0, 0], selection="point", through=[5.0, 3.0])


def plane_horizontal():
    return _plane("Plane: constant vertical and horizontal loads", "w = 1 kN/m and h = 0.3 kN/m per metre of "
                  "x: the thrust varies linearly and the line is the logarithmic branch of Appendix B "
                  "(B = 0).", vertical_mode="density", w=[1.0, 0, 0, 0], horizontal_mode="density",
                  h=[0.3, 0, 0, 0], selection="point", through=[5.0, 3.0])


def plane_pseudo():
    return _plane("Plane: catenary under a pseudo-static action", "Weight w = 1 kN per metre of actual length "
                  "with a horizontal action 0.2 w in the same measure: the load keeps a fixed direction and the "
                  "line is a catenary with an inclined axis.", vertical_mode="actual", w=[1.0, 0, 0, 0],
                  horizontal_mode="proportional", gamma=0.2, selection="point", through=[5.0, 3.0])


def plane_polygon():
    p = _plane("Plane: funicular polygon of point loads", "Three point loads and no distributed load: the "
               "funicular polygon through the crown point, with the force constant between the nodes and "
               "jumping by −G at each.", vertical_mode="density", w=[0.0, 0, 0, 0], selection="point",
               through=[5.0, 3.0])
    p.plane_points = [[2.5, 0.0, -10.0], [5.0, 2.0, -20.0], [7.5, 0.0, -10.0]]
    return p


def plane_thrust():
    return _plane("Plane: catenary with a prescribed thrust and unequal supports", "w = 1 kN per metre of "
                  "actual length, H = 6 kN at A and a second support 1.5 m higher: the vertical force at A "
                  "that reaches B.", vertical_mode="actual", w=[1.0, 0, 0, 0], selection="thrust",
                  thrust=6.0, end_height=1.5)


def _arch(name, notes, plane_points=(), **kw):
    p = Project(name=name, task="arch")
    p.arch = ArchSpec(**kw)
    p.plane_points = [list(r) for r in plane_points]
    p.output = OutputSpec(abscissa="s", stations=21)
    p.notes = notes
    return p


def arch_semicircle_minimum():
    return _arch("Arch: semicircular arch of minimum thickness", "Semicircular arch R = 5 m, t = 1 m, under its "
                 "own weight with joints normal to the centre line. The least thickness that contains a thrust "
                 "line, the weight following the thickness, is t/R = 0.1075 (Milankovitch), with five hinges, "
                 "at the springings, near 54.5° from the crown and at the crown.", shape="circular", span=10.0,
                 rise=5.0, thickness=1.0, thickness_springing=1.0, minimum_thickness=True, variable="none")


def arch_semicircle_seismic():
    return _arch("Arch: semicircular arch under a horizontal action", "Semicircular arch R = 5 m, t = 0.75 m "
                 "(t/R = 0.15): the largest horizontal action λ W that a thrust line can carry, the four hinges "
                 "of the mechanism and the same multiplier by virtual work, and the thrusts admissible at every λ.",
                 shape="circular", span=10.0, rise=5.0, thickness=0.75, thickness_springing=0.75,
                 variable="horizontal")


def arch_segmental_point():
    return _arch("Arch: segmental arch with fill and a point load", "Segmental arch, span 10 m and rise 2.5 m, "
                 "t = 0.6 m, fill up to 3.6 m and a point load of 50 kN at a quarter of the span: the minimum and "
                 "maximum thrust and the collapse multiplier of the point load.", plane_points=[[2.5, 0.0, -50.0]],
                 shape="circular", span=10.0, rise=2.5, thickness=0.6, thickness_springing=0.6, fill=True,
                 fill_level=3.6, fill_weight=18.0, variable="points")


def arch_pointed():
    return _arch("Arch: pointed arch under a horizontal action", "Pointed arch, span 6 m and rise 4.5 m, "
                 "t = 0.5 m, with a horizontal action λ = 0.1 of the weight: the lines of minimum and maximum "
                 "thrust at that action and the collapse multiplier.", shape="pointed", span=6.0, rise=4.5,
                 thickness=0.5, thickness_springing=0.5, lam=0.1, variable="horizontal")


def arch_catenary():
    return _arch("Arch: catenary arch of finite thickness", "Catenary centre line, span 10 m and rise 4 m, "
                 "t = 0.4 m, under its own weight: the line through the centres of the springings and of the "
                 "crown is close to the centre line but not on it, since the weight of a ring of finite "
                 "thickness acts at the centroids of its slices.", shape="catenary", span=10.0, rise=4.0,
                 thickness=0.4, thickness_springing=0.4, line="points", eccentricities=[0.0, 0.0, 0.0],
                 variable="horizontal")


def arch_vertical():
    return _arch("Arch: thrust line on vertical sections", "The segmental arch with fill and a point load, "
                 "assessed on vertical sections, the sections at constant x of the projected abscissa, in "
                 "place of joints normal to the centre line.", plane_points=[[2.5, 0.0, -50.0]],
                 shape="circular", span=10.0, rise=2.5, thickness=0.6, thickness_springing=0.6, fill=True,
                 fill_level=3.6, fill_weight=18.0, joints="vertical", variable="points")


def arch_voussoirs():
    return _arch("Arch: voussoir arch of 15 voussoirs, haunched", "Semicircular arch of 15 voussoirs, 0.6 m "
                 "thick at the crown and 0.9 m at the springings, with the joints drawn: the lines of minimum and "
                 "maximum thrust and the geometric safety factor.", shape="circular", span=8.0, rise=4.0,
                 thickness=0.6, thickness_springing=0.9, count=15, variable="horizontal")


EXAMPLES = OrderedDict([
    ("Supported: Fig. 2, reaction shift on the circular path", supported_fig2),
    ("Supported: Figs. 12 and 13, circular benchmark with contact", supported_benchmark),
    ("Supported: Fig. 12, contact violated at h/w = 4", supported_h4),
    ("Supported: Section 5.3, pseudo-static action", supported_pseudo),
    ("Supported: Section 5.4, point force on the helix", supported_point),
    ("Supported: Fig. 10, ellipse with f = cθ", lambda: supported_ellipse("angle")),
    ("Supported: Fig. 10, ellipse with f = k_s s", lambda: supported_ellipse("arc")),
    ("Without reactions: Fig. 3, path that is not an axial equilibrium", lambda: reaction_free_check(0.6)),
    ("Without reactions: Fig. 3, the funicular of the same loads", lambda: reaction_free_check(0.0)),
    ("Without reactions: Fig. 4, three-component loading", reaction_free_three),
    ("Without reactions: Fig. 9, exceptional helical arc", reaction_free_arc),
    ("Form-finding: Fig. 8, constant loads", free_constant),
    ("Form-finding: Fig. 11, case A", free_a),
    ("Form-finding: Fig. 11, case B", free_b),
    ("Form-finding: Figs. 5 and 11, case C", free_c),
    ("Form-finding: Fig. 6, prescribed second support", free_c_endpoint),
    ("Form-finding: case C with a point force", free_c_point),
    ("Form-finding: catenary under self-weight", catenary),
    ("Form-finding: parabolic arch", parabola),
    ("Node: Fig. 7, concentrated multidirectional force", node_fig7),
    ("Node: Section 5.4, horizontal point force", node_horizontal),
    ("Plane: catenary through a point", plane_catenary),
    ("Plane: parabola through a point", plane_parabola),
    ("Plane: constant vertical and horizontal loads", plane_horizontal),
    ("Plane: catenary under a pseudo-static action", plane_pseudo),
    ("Plane: funicular polygon of point loads", plane_polygon),
    ("Plane: catenary with a prescribed thrust and unequal supports", plane_thrust),
    ("Arch: semicircular arch of minimum thickness", arch_semicircle_minimum),
    ("Arch: semicircular arch under a horizontal action", arch_semicircle_seismic),
    ("Arch: segmental arch with fill and a point load", arch_segmental_point),
    ("Arch: pointed arch under a horizontal action", arch_pointed),
    ("Arch: catenary arch of finite thickness", arch_catenary),
    ("Arch: thrust line on vertical sections", arch_vertical),
    ("Arch: voussoir arch of 15 voussoirs, haunched", arch_voussoirs),
])
