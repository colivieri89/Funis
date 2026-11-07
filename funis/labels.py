"""Placement of the labels of a drawing clear of its geometry.

Every Text primitive names the point it labels and a preferred direction. The
labels of an axes are drawn by one LabelSet artist, which places them when the
axes is rendered, so that the positions follow the size of the window and the
limits of the view, and are measured with the renderer of the file being
written. Each label is tried at increasing distances from its point, first
along the preferred direction and then around it, and takes the first position
whose box keeps the required clearance from every line, arrow, marker and arc
of the drawing, from the labels already placed, from the other texts of the
axes and from the edges of the axes. When no position keeps the clearance, the
best one is taken.

measure() checks the result from the drawn artists, independently of the
placement, and is used by the tests.
"""
import numpy as np
from matplotlib.artist import Artist
from matplotlib.patches import Arc, FancyArrowPatch
from matplotlib.text import Text as MplText
from matplotlib.transforms import Bbox, IdentityTransform

from .drawing import Arrow, Circle, Marker, Polyline, ROLES, Text

CLEARANCE = 2.0
"""Clearance sought between a label box and any other item, in points."""

LEAST_CLEARANCE = 1.0
"""Clearance below which a label is left out rather than drawn over the geometry, in points."""

DISTANCES = (4.0, 6.0, 8.0, 11.0, 15.0, 20.0, 26.0, 34.0, 44.0)
"""Distances tried from the labelled point to the box of the label, in points."""

DEVIATIONS = (0, 15, -15, 30, -30, 45, -45, 60, -60, 75, -75, 90, -90, 105, -105, 120, -120,
              135, -135, 150, -150, 165, -165, 180)
"""Deviations tried from the preferred direction, in degrees, in order of preference."""

BOX_PAD = 0.12
"""Padding of the white box behind a label, in units of its font size."""

HEAD_LENGTH = 5.5
"""Length of the head of an arrow taken from its tip, in points."""

HEAD_RADIUS = 2.0
"""Half width of the head of an arrow, in points."""

DEFAULT_DIRECTION = {"left": (1.0, 0.0), "right": (-1.0, 0.0), "center": (0.0, 1.0)}


class LabelSet(Artist):
    """The labels of one drawing on one axes, placed at draw time.

    A label that finds no position with at least LEAST_CLEARANCE is not drawn
    and is listed in `hidden`: on screen it appears again when the view is
    enlarged or zoomed, and every value remains in the tables.
    """

    def __init__(self, ax, drawing, font_size):
        super().__init__()
        self.ax = ax
        self.drawing = drawing
        self.font_size = font_size
        self.set_transform(IdentityTransform())
        self.set_zorder(5)
        self.items = []
        for it in drawing.items:
            if isinstance(it, Text):
                artist = MplText(0.0, 0.0, it.text, color=ROLES[it.role],
                                 fontsize=font_size * it.size / 9.0, ha="left", va="bottom",
                                 bbox=dict(boxstyle="round,pad=%g" % BOX_PAD, fc="white",
                                           ec="none", alpha=0.75))
                artist.set_figure(ax.figure)
                artist.axes = ax
                artist.set_transform(IdentityTransform())
                artist.set_clip_box(ax.bbox)
                self.items.append((it, artist))
        self._key = None
        self._boxes = []
        self.hidden = []

    # ------------------------------------------------------------------ artist interface
    def draw(self, renderer):
        if not self.get_visible():
            return
        self.place(renderer)
        for _, artist in self.items:
            if artist.get_visible():
                artist.draw(renderer)
        self.stale = False

    def get_window_extent(self, renderer=None):
        if not self._boxes:
            return Bbox.null()
        b = np.asarray(self._boxes)
        return Bbox([[b[:, 0].min(), b[:, 1].min()], [b[:, 2].max(), b[:, 3].max()]])

    # ------------------------------------------------------------------ placement
    def place(self, renderer):
        """Place every label for the current geometry of the axes."""
        ax = self.ax
        k = renderer.points_to_pixels(1.0)
        key = (tuple(np.round(ax.bbox.extents, 2)), tuple(ax.get_xlim()), tuple(ax.get_ylim()),
               round(k, 5), type(renderer).__name__)
        if key == self._key:
            return
        self._key = key
        T = ax.transData
        segs, srad, pts, prad, boxes = self._obstacles(T, k, renderer)
        clear = CLEARANCE * k
        bounds = ax.bbox.extents + np.array([clear, clear, -clear, -clear])
        placed, hidden = [], []
        for it, artist in self.items:
            p = T.transform(it.point)
            offset = np.asarray(it.offset, dtype=float)
            if np.linalg.norm(offset) > 1e-12:
                u = T.transform(np.asarray(it.point, dtype=float) + offset) - p
            else:
                u = np.asarray(DEFAULT_DIRECTION[it.anchor], dtype=float)
            size = np.linalg.norm(u)
            u = u / size if size > 1e-12 else np.array([0.0, 1.0])
            artist.set_position((0.0, 0.0))
            ext = artist.get_window_extent(renderer)
            pad = BOX_PAD * artist.get_fontsize() * k
            w, h = ext.width + 2 * pad, ext.height + 2 * pad
            box, best = None, -np.inf
            for d in DISTANCES:
                cand = _candidates(p, u, w, h, d * k)
                cl = _clearance(cand, segs, srad, pts, prad, boxes)
                outside = np.maximum.reduce([bounds[0] - cand[:, 0], cand[:, 2] - bounds[2],
                                             bounds[1] - cand[:, 1], cand[:, 3] - bounds[3],
                                             np.zeros(len(cand))])
                cl = np.where(outside > 0, np.minimum(cl, -outside), cl)
                ok = cl >= clear
                if ok.any():
                    box, best = cand[int(np.argmax(ok))], clear
                    break
                idx = int(np.argmax(cl))
                if cl[idx] > best:
                    box, best = cand[idx], cl[idx]
            if best < LEAST_CLEARANCE * k:
                artist.set_visible(False)
                hidden.append(it.text)
                continue
            artist.set_visible(True)
            artist.set_position((box[0] + pad, box[1] + pad))
            boxes.append(box)
            placed.append(box)
        self._boxes = placed
        self.hidden = hidden

    def _obstacles(self, T, k, renderer):
        segs, srad, pts, prad, boxes = [], [], [], [], []
        for it in self.drawing.items:
            if isinstance(it, Polyline):
                P = T.transform(np.asarray(it.points, dtype=float)[:, :2])
                if it.closed and len(P) > 1:
                    P = np.vstack([P, P[:1]])
                if len(P) > 1:
                    segs.extend(zip(P[:-1], P[1:]))
                    srad.extend([0.5 * it.width * k] * (len(P) - 1))
                if it.markers:
                    pts.extend(P)
                    prad.extend([1.6 * k] * len(P))
            elif isinstance(it, Arrow):
                a, b = T.transform([it.tail, it.head])
                segs.append((a, b))
                srad.append(0.5 * it.width * k)
                length = np.linalg.norm(b - a)
                if length > 1e-9:
                    segs.append((b, b - (b - a) / length * HEAD_LENGTH * k))
                    srad.append(HEAD_RADIUS * k)
            elif isinstance(it, Marker):
                pts.append(T.transform(it.point))
                prad.append(0.5 * it.size * k)
            elif isinstance(it, Circle):
                if it.arc is None:
                    th = np.linspace(0.0, 2 * np.pi, 97)
                else:
                    th = np.linspace(min(it.arc), max(it.arc), 65)
                c = np.asarray(it.centre, dtype=float)
                P = T.transform(c + it.radius * np.column_stack((np.cos(th), np.sin(th))))
                segs.extend(zip(P[:-1], P[1:]))
                srad.extend([0.5 * it.width * k] * (len(P) - 1))
        for line in self.ax.lines:
            if line.get_gid() == "scale-bar":
                P = line.get_transform().transform(line.get_xydata())
                segs.extend(zip(P[:-1], P[1:]))
                srad.extend([0.5 * line.get_linewidth() * k] * (len(P) - 1))
        for t in self.ax.texts:
            if t.get_visible() and t.get_text().strip():
                boxes.append(t.get_window_extent(renderer).extents)
        segs = np.asarray(segs, dtype=float).reshape(-1, 2, 2)
        pts = np.asarray(pts, dtype=float).reshape(-1, 2)
        return segs, np.asarray(srad, dtype=float), pts, np.asarray(prad, dtype=float), boxes


def _candidates(p, u, w, h, d):
    """Boxes [x0, y0, x1, y1] of size w x h at the distance d from the point p, one per deviation."""
    a = np.radians(DEVIATIONS)
    v = np.column_stack((u[0] * np.cos(a) - u[1] * np.sin(a), u[0] * np.sin(a) + u[1] * np.cos(a)))
    q = p + d * v
    x0 = np.where(v[:, 0] > 0.3, q[:, 0], np.where(v[:, 0] < -0.3, q[:, 0] - w, q[:, 0] - 0.5 * w))
    y0 = np.where(v[:, 1] > 0.3, q[:, 1], np.where(v[:, 1] < -0.3, q[:, 1] - h, q[:, 1] - 0.5 * h))
    return np.column_stack((x0, y0, x0 + w, y0 + h))


def _clearance(boxes, segs, srad, pts, prad, others):
    """Clearance of every box from the segments, the points and the other boxes.

    Segments and points carry a radius (half the drawn width). The value is
    negative when the box meets an item.
    """
    boxes = np.asarray(boxes, dtype=float)
    x0, y0, x1, y1 = (boxes[:, i][:, None] for i in range(4))
    cl = np.full(len(boxes), np.inf)
    if len(segs):
        A, B = segs[:, 0], segs[:, 1]
        d = np.minimum(_point_box(A, x0, y0, x1, y1), _point_box(B, x0, y0, x1, y1))
        corners = np.stack([np.hstack([x0, y0]), np.hstack([x1, y0]),
                            np.hstack([x0, y1]), np.hstack([x1, y1])], axis=1)
        AB = B - A
        L2 = np.maximum((AB ** 2).sum(1), 1e-12)
        PA = corners[:, :, None, :] - A[None, None, :, :]
        t = np.clip((PA * AB[None, None]).sum(-1) / L2, 0.0, 1.0)
        closest = A[None, None] + t[..., None] * AB[None, None]
        d = np.minimum(d, np.linalg.norm(corners[:, :, None, :] - closest, axis=-1).min(1))
        hit = _crosses(x0, y0, x1, y1, A, B)
        d = np.where(hit, -np.minimum(x1 - x0, y1 - y0), d)
        cl = np.minimum(cl, (d - srad[None, :]).min(1))
    if len(pts):
        px, py = pts[None, :, 0], pts[None, :, 1]
        d = _point_box(pts, x0, y0, x1, y1)
        pen = np.minimum(np.minimum(px - x0, x1 - px), np.minimum(py - y0, y1 - py))
        d = np.where(pen > 0, -pen, d)
        cl = np.minimum(cl, (d - prad[None, :]).min(1))
    if others:
        O = np.asarray(others, dtype=float)
        dx = np.maximum(x0 - O[None, :, 2], O[None, :, 0] - x1)
        dy = np.maximum(y0 - O[None, :, 3], O[None, :, 1] - y1)
        both = (dx < 0) & (dy < 0)
        d = np.where(both, np.maximum(dx, dy), np.hypot(np.maximum(dx, 0.0), np.maximum(dy, 0.0)))
        cl = np.minimum(cl, d.min(1))
    return cl


def _point_box(P, x0, y0, x1, y1):
    """Distance from points (N, 2) to boxes (C,) as a (C, N) array, zero inside."""
    px, py = P[None, :, 0], P[None, :, 1]
    dx = np.maximum(np.maximum(x0 - px, px - x1), 0.0)
    dy = np.maximum(np.maximum(y0 - py, py - y1), 0.0)
    return np.hypot(dx, dy)


def _crosses(x0, y0, x1, y1, A, B):
    """Whether the segments A-B (N, 2) cross the boxes (C,), as a (C, N) array (Liang and Barsky)."""
    ax_, ay_ = A[None, :, 0], A[None, :, 1]
    dx, dy = (B - A)[None, :, 0], (B - A)[None, :, 1]
    shape = np.broadcast(x0, ax_).shape
    t0, t1 = np.zeros(shape), np.ones(shape)
    ok = np.ones(shape, dtype=bool)
    for p, q in ((-dx, ax_ - x0), (dx, x1 - ax_), (-dy, ay_ - y0), (dy, y1 - ay_)):
        p = np.broadcast_to(p, shape)
        q = np.broadcast_to(q, shape)
        with np.errstate(divide="ignore", invalid="ignore"):
            t = np.where(p != 0, q / np.where(p != 0, p, 1.0), 0.0)
        ok &= ~((p == 0) & (q < 0))
        t0 = np.where(p < 0, np.maximum(t0, t), t0)
        t1 = np.where(p > 0, np.minimum(t1, t), t1)
    return ok & (t0 <= t1)


# ---------------------------------------------------------------------- measurement

def measure(fig):
    """Clearance of every label of a drawn figure, from the artists on the axes.

    Returns a list of (axes index, text, clearance in points, kind), where the
    kind names the nearest item: line, marker, arrow, patch, text or edge. The
    figure must have been drawn with its canvas.
    """
    renderer = fig.canvas.get_renderer()
    k = renderer.points_to_pixels(1.0)
    out = []
    for ai, ax in enumerate(fig.axes):
        labelsets = [a for a in ax.artists if isinstance(a, LabelSet)]
        if not labelsets:
            continue
        items = _artist_geometry(ax, k)
        labels = []
        for ls in labelsets:
            for _, t in ls.items:
                if not t.get_visible():
                    continue
                t.update_bbox_position_size(renderer)
                labels.append((t.get_text(), t.get_bbox_patch().get_window_extent(renderer).extents))
        others = [t.get_window_extent(renderer).extents for t in ax.texts
                  if t.get_visible() and t.get_text().strip()]
        edge = ax.bbox.extents
        for n, (text, box) in enumerate(labels):
            best, kind = np.inf, "none"
            for name, P, rad, closed in items:
                d = _box_polyline(box, P, closed) - rad
                if d < best:
                    best, kind = d, name
            for m, (_, other) in enumerate(labels):
                if m != n:
                    d = _box_box(box, other)
                    if d < best:
                        best, kind = d, "text"
            for other in others:
                d = _box_box(box, other)
                if d < best:
                    best, kind = d, "text"
            d = min(box[0] - edge[0], box[1] - edge[1], edge[2] - box[2], edge[3] - box[3])
            if d < best:
                best, kind = d, "edge"
            out.append((ai, text, float(best / k), kind))
    return out


def _artist_geometry(ax, k):
    """(kind, points, radius, closed) of every drawn line, marker, arrow and patch, in pixels."""
    items = []
    for line in ax.lines:
        if not line.get_visible():
            continue
        P = line.get_transform().transform(line.get_xydata())
        if line.get_linestyle() not in ("None", "none", "", " ") and len(P) > 1:
            items.append(("line", P, 0.5 * line.get_linewidth() * k, False))
        if line.get_marker() not in (None, "None", "none", ""):
            items.append(("marker", P, 0.5 * line.get_markersize() * k, None))
    for pa in ax.patches:
        if not pa.get_visible():
            continue
        if isinstance(pa, FancyArrowPatch):
            path = pa.get_transform().transform_path(pa.get_path())
            for poly in path.to_polygons(closed_only=False):
                if len(poly) > 1:
                    items.append(("arrow", np.asarray(poly), 0.5 * pa.get_linewidth() * k, False))
        elif isinstance(pa, Arc):
            th = np.radians(np.linspace(pa.theta1, pa.theta2, 65))
            P = np.column_stack((pa.center[0] + 0.5 * pa.width * np.cos(th),
                                 pa.center[1] + 0.5 * pa.height * np.sin(th)))
            items.append(("patch", ax.transData.transform(P), 0.5 * pa.get_linewidth() * k, False))
        elif pa.get_edgecolor()[3] > 0 and pa.get_linewidth() > 0:
            path = pa.get_transform().transform_path(pa.get_path())
            for poly in path.to_polygons(closed_only=False):
                if len(poly) > 1:
                    items.append(("patch", np.asarray(poly), 0.5 * pa.get_linewidth() * k, True))
    return items


def _box_polyline(box, P, closed):
    """Distance from a box to a polyline (closed=None: to its points only), negative inside."""
    P = np.asarray(P, dtype=float)
    x0, y0, x1, y1 = box
    if closed is None or len(P) == 1:
        d = _point_box(P, np.array([[x0]]), np.array([[y0]]), np.array([[x1]]), np.array([[y1]]))[0]
        pen = np.minimum(np.minimum(P[:, 0] - x0, x1 - P[:, 0]), np.minimum(P[:, 1] - y0, y1 - P[:, 1]))
        return float(np.where(pen > 0, -pen, d).min())
    if closed:
        P = np.vstack([P, P[:1]])
    segs = np.stack([P[:-1], P[1:]], axis=1)
    return float(_clearance(np.array([box]), segs, np.zeros(len(segs)), np.zeros((0, 2)),
                            np.zeros(0), [])[0])


def _box_box(a, b):
    dx = max(a[0] - b[2], b[0] - a[2])
    dy = max(a[1] - b[3], b[1] - a[3])
    if dx < 0 and dy < 0:
        return max(dx, dy)
    return float(np.hypot(max(dx, 0.0), max(dy, 0.0)))
