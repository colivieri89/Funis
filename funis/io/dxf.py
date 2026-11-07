"""DXF export of the views to scale, one block of layers per view.

Plans and elevations are written in metres and diagrams of forces or
densities at the chosen scale (drawing units per kN or kN/m), each view
offset from the previous one. Graphs of functions are not written. The
spatial path is written as a 3D polyline.
"""
import re

import numpy as np
import ezdxf

from ..drawing import Arrow, Circle, Fill, Marker, Polyline, Text

COLORS = {"ink": 5, "vertical": 3, "horizontal": 30, "reaction": 6, "trial": 8, "gray": 8,
          "light": 9, "accent": 4, "fill": 254, "cone": 254, "violation": 254, "soil": 253}
LINETYPES = {"solid": "CONTINUOUS", "dashed": "DASHED", "dotted": "DOT"}


def _layer(doc, name, role):
    name = re.sub(r"[^A-Za-z0-9_\-]+", "_", name).strip("_")[:120] or "layer"
    if name not in doc.layers:
        doc.layers.add(name, color=COLORS.get(role, 7))
    return name


def _ensure_linetypes(doc):
    for name, pattern in (("DASHED", [0.6, 0.4, -0.2]), ("DOT", [0.2, 0.0, -0.2])):
        if name not in doc.linetypes:
            doc.linetypes.add(name, pattern=pattern)


def write(result, path, force_scale=0.1, gap=2.0, text_height=0.12):
    """Write every drawing of the result to one DXF file."""
    doc = ezdxf.new("R2010", setup=True)
    _ensure_linetypes(doc)
    msp = doc.modelspace()
    x_offset = 0.0
    for key, drawing in result.drawings.items():
        if drawing.aspect != "equal":
            continue
        unit_scale = 1.0 if drawing.unit == "m" else force_scale
        x0, x1, y0, y1 = drawing.extent()
        shift = np.array([x_offset - x0 * unit_scale, -y0 * unit_scale])
        prefix = drawing.name.replace(" ", "_").replace(":", "")[:40]
        for it in drawing.items:
            layer = _layer(doc, "%s_%s" % (prefix, (it.layer or it.role).replace(" ", "_")), it.role)
            attrs = {"layer": layer}
            if isinstance(it, Polyline):
                pts = np.asarray(it.points, float)[:, :2] * unit_scale + shift
                attrs["linetype"] = LINETYPES[it.style]
                msp.add_lwpolyline(pts.tolist(), close=it.closed, dxfattribs=attrs)
                if it.markers:
                    for p in pts:
                        msp.add_circle(p.tolist(), 0.03, dxfattribs=attrs)
            elif isinstance(it, Fill):
                pts = np.asarray(it.points, float)[:, :2] * unit_scale + shift
                hatch = msp.add_hatch(color=COLORS.get(it.role, 254), dxfattribs=attrs)
                hatch.paths.add_polyline_path(pts.tolist(), is_closed=True)
            elif isinstance(it, Arrow):
                tail = np.asarray(it.tail) * unit_scale + shift
                head = np.asarray(it.head) * unit_scale + shift
                attrs["linetype"] = LINETYPES[it.style]
                msp.add_line(tail.tolist(), head.tolist(), dxfattribs=attrs)
                d = head - tail
                size = np.linalg.norm(d)
                if size > 1e-9:
                    u = d / size
                    n = np.array([-u[1], u[0]])
                    h = min(0.12, 0.3 * size)
                    for s in (1, -1):
                        msp.add_line(head.tolist(), (head - h * u + 0.4 * h * s * n).tolist(),
                                     dxfattribs=attrs)
            elif isinstance(it, Marker):
                p = np.asarray(it.point) * unit_scale + shift
                msp.add_circle(p.tolist(), 0.012 * it.size, dxfattribs=attrs)
            elif isinstance(it, Text):
                p = (np.asarray(it.point) + np.asarray(it.offset)) * unit_scale + shift
                msp.add_text(it.text, height=text_height, dxfattribs=attrs).set_placement(
                    p.tolist(), align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)
            elif isinstance(it, Circle):
                c = np.asarray(it.centre) * unit_scale + shift
                r = it.radius * unit_scale
                if it.arc is None:
                    msp.add_circle(c.tolist(), r, dxfattribs=attrs)
                else:
                    a0, a1 = np.degrees(it.arc)
                    msp.add_arc(c.tolist(), r, min(a0, a1), max(a0, a1), dxfattribs=attrs)
        title_layer = _layer(doc, "titles", "ink")
        msp.add_text(drawing.name, height=1.6 * text_height,
                     dxfattribs={"layer": title_layer}).set_placement(
            [x_offset, (y1 - y0) * unit_scale + 3 * text_height],
            align=ezdxf.enums.TextEntityAlignment.BOTTOM_LEFT)
        x_offset += (x1 - x0) * unit_scale + gap
    if result.curve3d is not None:
        layer = _layer(doc, "spatial_path", "ink")
        nodes = np.asarray(result.curve3d, float)
        msp.add_polyline3d(nodes.tolist(), dxfattribs={"layer": layer})
    doc.saveas(path)
