"""Drawings as lists of primitives, rendered by matplotlib or written to DXF.

A Drawing is a view to scale (a plan or an elevation in m, a diagram of
forces or densities in kN or kN/m, aspect "equal") or a graph of functions
along the path (aspect "auto"). Every primitive carries a role, which fixes
its colour and layer: ink for geometry and internal forces, vertical for
vertical loads, horizontal for horizontal loads, reaction for the reactions
of the lateral support, gray and light for auxiliary lines.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np

ROLES = {
    "ink": "#243b53",
    "vertical": "#007c83",
    "horizontal": "#b57726",
    "reaction": "#a04460",
    "trial": "#7a7a7a",
    "gray": "#7a7a7a",
    "light": "#c8c8c8",
    "accent": "#1f6feb",
    "fill": "#dfe7f0",
    "cone": "#e6eef7",
    "violation": "#f4e6ea",
    "soil": "#efe9df",
}


@dataclass
class Polyline:
    points: np.ndarray
    role: str = "ink"
    width: float = 1.2
    style: str = "solid"
    markers: bool = False
    closed: bool = False
    layer: Optional[str] = None


@dataclass
class Arrow:
    tail: Tuple[float, float]
    head: Tuple[float, float]
    role: str = "ink"
    width: float = 1.2
    style: str = "solid"
    layer: Optional[str] = None


@dataclass
class Marker:
    point: Tuple[float, float]
    role: str = "ink"
    size: float = 4.0
    filled: bool = True
    layer: Optional[str] = None


@dataclass
class Text:
    point: Tuple[float, float]
    text: str
    role: str = "ink"
    anchor: str = "center"
    offset: Tuple[float, float] = (0.0, 0.0)
    size: float = 9.0
    layer: Optional[str] = None


@dataclass
class Circle:
    centre: Tuple[float, float]
    radius: float
    role: str = "gray"
    width: float = 0.9
    style: str = "solid"
    layer: Optional[str] = None
    arc: Optional[Tuple[float, float]] = None


@dataclass
class Fill:
    points: np.ndarray
    role: str = "fill"
    alpha: float = 1.0
    layer: Optional[str] = None


@dataclass
class Drawing:
    name: str
    unit: str = "m"
    items: List[object] = field(default_factory=list)
    xlabel: str = ""
    ylabel: str = ""
    notes: List[str] = field(default_factory=list)
    aspect: str = "equal"
    xlim: Optional[Tuple[float, float]] = None
    ylim: Optional[Tuple[float, float]] = None
    xticks: Optional[List[Tuple[float, str]]] = None

    def add(self, item):
        self.items.append(item)
        return item

    def polyline(self, points, **kw):
        return self.add(Polyline(np.asarray(points, dtype=float), **kw))

    def arrow(self, tail, head, **kw):
        return self.add(Arrow(tuple(map(float, tail)), tuple(map(float, head)), **kw))

    def marker(self, point, **kw):
        return self.add(Marker(tuple(map(float, point)), **kw))

    def text(self, point, text, **kw):
        return self.add(Text(tuple(map(float, point)), text, **kw))

    def circle(self, centre, radius, **kw):
        return self.add(Circle(tuple(map(float, centre)), float(radius), **kw))

    def fill(self, points, **kw):
        return self.add(Fill(np.asarray(points, dtype=float), **kw))

    def extent(self):
        """Bounding box (xmin, xmax, ymin, ymax) of the drawn geometry."""
        pts = []
        for it in self.items:
            if isinstance(it, (Polyline, Fill)):
                pts.extend(it.points[:, :2])
            elif isinstance(it, Arrow):
                pts.extend([it.tail, it.head])
            elif isinstance(it, (Marker, Text)):
                pts.append(it.point)
            elif isinstance(it, Circle):
                c = np.asarray(it.centre)
                pts.extend([c - it.radius, c + it.radius])
        if not pts:
            return (-1.0, 1.0, -1.0, 1.0)
        p = np.asarray(pts, dtype=float)
        return (float(p[:, 0].min()), float(p[:, 0].max()),
                float(p[:, 1].min()), float(p[:, 1].max()))


def label_offset(direction, distance):
    """Offset of a label along a direction, for use with Text.offset (data units)."""
    d = np.asarray(direction, dtype=float)
    size = np.linalg.norm(d)
    if size < 1e-12:
        return (0.0, distance)
    return tuple(distance * d / size)
