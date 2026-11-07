"""Project data: the input of every task, serialisable to JSON.

Lengths in m, forces in kN, densities in kN per metre of projected length,
angles in degrees. Polynomials are lists of coefficients a0, a1, a2, a3 of
a0 + a1 s + a2 s^2 + a3 s^3 with s in m. The plane tasks use the abscissa x
along e1 in place of s, and their point loads are rows (x, G1, G3) in
plane_points.
"""
import dataclasses
from dataclasses import dataclass, field, fields, is_dataclass
from typing import List

TASKS = {
    "supported": "Supported path (assessment)",
    "reaction_free": "Path without reactions",
    "form_finding": "Unknown geometry (form-finding)",
    "node": "Node under a concentrated force",
    "plane_funicular": "Plane funicular (catenary)",
    "arch": "Arch assessment (thrust line)",
}


@dataclass
class HelixSpec:
    radius: float = 2.0
    pitch: float = -1.0
    theta_start: float = 0.0
    theta_end: float = 360.0


@dataclass
class EllipseSpec:
    a: float = 3.0
    b: float = 2.0
    pitch: float = -1.0
    mode: str = "angle"
    theta_start: float = 0.0
    theta_end: float = 360.0


@dataclass
class GeometrySpec:
    kind: str = "helix"
    helix: HelixSpec = field(default_factory=HelixSpec)
    ellipse: EllipseSpec = field(default_factory=EllipseSpec)
    points: List[List[float]] = field(default_factory=lambda: [
        [2.0, 0.0, 0.0], [1.0, 1.7320508, -1.0471976], [-1.0, 1.7320508, -2.0943951],
        [-2.0, 0.0, -3.1415927]])
    samples: int = 2001


@dataclass
class LoadSpec:
    vertical_mode: str = "density"
    w: List[float] = field(default_factory=lambda: [1.0, 0.0, 0.0, 0.0])
    w_table: List[List[float]] = field(default_factory=lambda: [[0.0, 1.0], [10.0, 1.0]])
    horizontal_mode: str = "none"
    h: List[float] = field(default_factory=lambda: [1.0, 0.0, 0.0, 0.0])
    h_table: List[List[float]] = field(default_factory=lambda: [[0.0, 1.0], [10.0, 1.0]])
    beta: float = 0.0
    gamma: float = 0.2
    p1: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0])
    p2: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0])
    multiplier: float = 1.0


@dataclass
class PointAction:
    s: float = 1.0
    G1: float = 0.0
    G2: float = 0.0
    G3: float = -1.0


@dataclass
class SupportSpec:
    preload: float = 8.0
    wall: str = "right"


@dataclass
class ContactSpec:
    enabled: bool = True
    mu: float = 0.6
    strip: float = 0.8
    delta: float = 0.0
    T_max: float = 0.0
    lam_max: float = 0.0


@dataclass
class ReactionFreeSpec:
    mode: str = "check"
    B: float = 3.0
    beta: float = 0.0
    thrust: List[float] = field(default_factory=lambda: [-8.0, -2.0, 0.0, 0.0])


@dataclass
class FormSpec:
    length: float = 5.0
    start: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    mode: str = "initial"
    force: List[float] = field(default_factory=lambda: [-3.0, -4.0, -2.0])
    target: List[float] = field(default_factory=lambda: [3.58655144, 3.46958475, -0.09396228])
    guess: List[float] = field(default_factory=lambda: [-2.5, -3.5, -1.5])
    samples: int = 2001


@dataclass
class NodeSpec:
    force_before: List[float] = field(default_factory=lambda: [-3.0, -2.0, -1.0])
    load: List[float] = field(default_factory=lambda: [2.0, 0.0, -1.0])
    reaction: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    segment: float = 2.0


@dataclass
class FunicularSpec:
    """Plane funicular between A = (0, 0) and B = (L, z_B), loads in the vertical plane."""
    span: float = 10.0
    end_height: float = 0.0
    vertical_mode: str = "actual"
    w: List[float] = field(default_factory=lambda: [1.0, 0.0, 0.0, 0.0])
    w_table: List[List[float]] = field(default_factory=lambda: [[0.0, 1.0], [10.0, 1.0]])
    horizontal_mode: str = "none"
    h: List[float] = field(default_factory=lambda: [0.2, 0.0, 0.0, 0.0])
    gamma: float = 0.1
    selection: str = "point"
    through: List[float] = field(default_factory=lambda: [5.0, 3.0])
    thrust: float = 4.0
    force: List[float] = field(default_factory=lambda: [-4.0, -2.5])
    samples: int = 2001


@dataclass
class ArchSpec:
    """Arch of finite thickness: centre line, thickness, materials, fill and the assessment."""
    shape: str = "circular"
    span: float = 10.0
    rise: float = 5.0
    points: List[List[float]] = field(default_factory=lambda: [
        [0.0, 0.0], [2.5, 3.2], [5.0, 4.0], [7.5, 3.2], [10.0, 0.0]])
    thickness: float = 1.0
    thickness_springing: float = 1.0
    depth: float = 1.0
    unit_weight: float = 20.0
    fill: bool = False
    fill_level: float = 6.0
    fill_weight: float = 18.0
    fill_inertia: bool = True
    surcharge: float = 0.0
    joints: str = "normal"
    count: int = 200
    lam: float = 0.0
    direction: str = "right"
    variable: str = "horizontal"
    friction: float = 0.0
    line: str = "min"
    eccentricities: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    minimum_thickness: bool = False


@dataclass
class OutputSpec:
    abscissa: str = "theta"
    stations: int = 41


@dataclass
class Project:
    name: str = "Untitled"
    task: str = "supported"
    geometry: GeometrySpec = field(default_factory=GeometrySpec)
    loads: LoadSpec = field(default_factory=LoadSpec)
    point_actions: List[PointAction] = field(default_factory=list)
    support: SupportSpec = field(default_factory=SupportSpec)
    contact: ContactSpec = field(default_factory=ContactSpec)
    reaction_free: ReactionFreeSpec = field(default_factory=ReactionFreeSpec)
    form: FormSpec = field(default_factory=FormSpec)
    node: NodeSpec = field(default_factory=NodeSpec)
    funicular: FunicularSpec = field(default_factory=FunicularSpec)
    arch: ArchSpec = field(default_factory=ArchSpec)
    plane_points: List[List[float]] = field(default_factory=list)
    output: OutputSpec = field(default_factory=OutputSpec)
    notes: str = ""

    def to_dict(self):
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data):
        return _build(cls, data)

    def copy(self):
        return Project.from_dict(self.to_dict())

    @property
    def task_label(self):
        return TASKS.get(self.task, self.task)


def _build(cls, data):
    """Instance of a dataclass from a dict, ignoring unknown keys."""
    if not isinstance(data, dict):
        return cls()
    kwargs = {}
    for f in fields(cls):
        if f.name not in data:
            continue
        value = data[f.name]
        if is_dataclass(f.type) and isinstance(f.type, type):
            kwargs[f.name] = _build(f.type, value)
        elif f.name == "point_actions":
            kwargs[f.name] = [_build(PointAction, v) for v in value]
        else:
            kwargs[f.name] = value
    return cls(**kwargs)
