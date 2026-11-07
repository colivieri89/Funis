"""Rendering of Drawing objects with matplotlib, on screen and to files."""
import numpy as np
import matplotlib
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.patches import Arc, FancyArrowPatch, Polygon as MplPolygon

from .drawing import Arrow, Circle, Fill, Marker, Polyline, ROLES, Text
from .labels import LabelSet

LINESTYLES = {"solid": "-", "dashed": (0, (4, 2.5)), "dotted": (0, (1, 2))}
FONT = {"font.family": "DejaVu Sans", "font.size": 9, "mathtext.fontset": "dejavusans",
        "axes.linewidth": 0.6, "pdf.fonttype": 42, "ps.fonttype": 42}


def apply_style():
    matplotlib.rcParams.update(FONT)


def draw(ax, drawing, grid=True, frame=True, title=True, font_size=9.0):
    """Draw every primitive of the drawing on the axes.

    Views to scale keep an equal aspect, graphs of functions fill the axes.

    The labels are placed when the axes is rendered, clear of the geometry
    (see labels.LabelSet), so they follow the size of the window and the
    limits of the view.
    """
    equal = drawing.aspect == "equal"
    if equal:
        ax.set_aspect("equal", adjustable="datalim")
    for it in drawing.items:
        if isinstance(it, Fill):
            ax.add_patch(MplPolygon(it.points[:, :2], closed=True, facecolor=ROLES[it.role],
                                    edgecolor="none", alpha=it.alpha, zorder=0.5))
        elif isinstance(it, Polyline):
            pts = np.asarray(it.points, dtype=float)
            if it.closed:
                pts = np.vstack([pts, pts[:1]])
            ax.plot(pts[:, 0], pts[:, 1], color=ROLES[it.role], lw=it.width,
                    ls=LINESTYLES[it.style], marker="o" if it.markers else None,
                    ms=3.2, zorder=2 if it.role in ("ink",) else 1.5, solid_capstyle="round")
        elif isinstance(it, Arrow):
            ax.add_patch(FancyArrowPatch(it.tail, it.head, arrowstyle="-|>", mutation_scale=9,
                                         color=ROLES[it.role], lw=it.width,
                                         ls=LINESTYLES[it.style], zorder=3, shrinkA=0, shrinkB=0))
        elif isinstance(it, Marker):
            ax.plot([it.point[0]], [it.point[1]], marker="o", ms=it.size, mfc=ROLES[it.role] if it.filled else "white",
                    mec=ROLES[it.role], ls="none", zorder=4)
        elif isinstance(it, Circle):
            if it.arc is None:
                ax.add_patch(matplotlib.patches.Circle(it.centre, it.radius, fill=False,
                                                       ec=ROLES[it.role], lw=it.width, zorder=1.5))
            else:
                a0, a1 = np.degrees(it.arc)
                ax.add_patch(Arc(it.centre, 2 * it.radius, 2 * it.radius, theta1=min(a0, a1),
                                 theta2=max(a0, a1), ec=ROLES[it.role], lw=it.width, zorder=1.5))
    x0, x1, y0, y1 = drawing.extent()
    dx, dy = max(x1 - x0, 1e-6), max(y1 - y0, 1e-6)
    if equal:
        pad = 0.08 * max(dx, dy)
        ax.set_xlim(x0 - pad, x1 + pad)
        ax.set_ylim(y0 - pad, y1 + pad)
    else:
        ax.set_xlim(*(drawing.xlim or (x0, x1)))
        ax.set_ylim(*(drawing.ylim or (y0 - 0.1 * dy, y1 + 0.1 * dy)))
        if drawing.xticks:
            ax.set_xticks([v for v, _ in drawing.xticks], [lab for _, lab in drawing.xticks])
    if any(isinstance(it, Text) for it in drawing.items):
        ax.add_artist(LabelSet(ax, drawing, font_size))
    if title:
        ax.set_title(drawing.name, fontsize=font_size + 1, loc="left", color="#243b53", pad=8)
    ax.set_xlabel(drawing.xlabel, fontsize=font_size)
    ax.set_ylabel(drawing.ylabel, fontsize=font_size)
    ax.tick_params(labelsize=font_size - 1, colors="#555555", length=3)
    if grid:
        ax.grid(True, color="#e3e7ec", lw=0.6)
        ax.set_axisbelow(True)
    for s in ax.spines.values():
        s.set_color("#c9d0d8")
    if not frame:
        ax.axis("off")
    return ax


def figure_for(drawing, width_cm=14.0, scale=None, dpi=100, grid=True, font_size=9.0):
    """Figure with one drawing, at a width in cm or at a scale in cm per unit.

    With a scale the figure is a drawing to scale without axes, with a scale
    bar and the title, as in a plate (views to scale only: a graph of
    functions is always fitted to the width). Without it the drawing fills the given
    width with its axes and grid. The figure has an Agg canvas and is not
    registered with pyplot: save it with fig.savefig and let it go.
    """
    apply_style()
    x0, x1, y0, y1 = drawing.extent()
    dx, dy = max(x1 - x0, 1e-6), max(y1 - y0, 1e-6)
    if drawing.aspect != "equal":
        scale = None
        h_cm = 0.62 * width_cm
        fig = Figure(figsize=(width_cm / 2.54, h_cm / 2.54), dpi=dpi)
        FigureCanvasAgg(fig)
        ax = fig.add_axes([0.13, 0.17, 0.83, 0.71])
        draw(ax, drawing, grid=grid, frame=True, font_size=font_size)
        return fig
    if scale is not None:
        w_cm = scale * dx + 2.0
        h_cm = scale * dy + 2.8
        fig = Figure(figsize=(w_cm / 2.54, h_cm / 2.54), dpi=dpi)
        FigureCanvasAgg(fig)
        ax = fig.add_axes([0.0, 0.0, 1.0, 1.0])
        draw(ax, drawing, grid=False, frame=False, title=False, font_size=font_size)
        ax.set_aspect("equal", adjustable="box")
        cx, cy = 0.5 * (x0 + x1), 0.5 * (y0 + y1) - 0.4 / scale
        ax.set_xlim(cx - 0.5 * w_cm / scale, cx + 0.5 * w_cm / scale)
        ax.set_ylim(cy - 0.5 * h_cm / scale, cy + 0.5 * h_cm / scale)
        ax.axis("off")
        _scale_bar(ax, drawing, scale, (cx - 0.5 * w_cm / scale + 0.8 / scale,
                                        cy - 0.5 * h_cm / scale + 0.7 / scale))
        fig.text(0.03, 0.97, drawing.name, ha="left", va="top", fontsize=font_size + 1,
                 color="#243b53")
        return fig
    h_cm = min(max(width_cm * dy / dx * 0.84 + 3.0, 7.0), 2.5 * width_cm)
    fig = Figure(figsize=(width_cm / 2.54, h_cm / 2.54), dpi=dpi)
    FigureCanvasAgg(fig)
    ax = fig.add_axes([0.12, 0.16, 0.85, 0.74])
    draw(ax, drawing, grid=grid, frame=True, font_size=font_size)
    return fig


def _scale_bar(ax, drawing, scale, origin):
    unit = drawing.unit or ""
    if not unit:
        return
    length = _nice(5.0 / scale)
    x, y = origin
    ax.plot([x, x + length], [y, y], color="#7a7a7a", lw=1.4, solid_capstyle="butt", gid="scale-bar")
    for xx in (x, x + length):
        ax.plot([xx, xx], [y - 0.1 / scale, y + 0.1 / scale], color="#7a7a7a", lw=1.0, gid="scale-bar")
    ax.text(x + 0.5 * length, y + 0.25 / scale, "%g %s  (%.3g cm/%s)" % (length, unit, scale, unit),
            ha="center", va="bottom", fontsize=8, color="#7a7a7a")


def _nice(v):
    e = 10 ** np.floor(np.log10(max(v, 1e-12)))
    for m in (1, 2, 5, 10):
        if m * e >= v:
            return m * e
    return 10 * e
