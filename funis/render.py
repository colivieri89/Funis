"""Rendering of Drawing objects with matplotlib, on screen and to files."""
import re

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
        _title(ax, drawing.name, font_size)
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


def _title(ax, text, font_size):
    """The title of the drawing, at the left of the axes; returns the text artist."""
    return ax.set_title(text, fontsize=font_size + 1, loc="left", color="#243b53", pad=8)


MARGIN = 3.0
"""Clearance between the outermost text of an exported figure and the edge of the sheet, in points."""

GRAPH_RATIO = 0.53
"""Height over width of the axes of a graph fitted to a width (the proportions of Funis 1.0.0)."""

GRAPH_MIN_HEIGHT = 80.0
"""Least height of the axes of a graph fitted to a width, in points: room for the labels of the curves."""

VIEW_RATIO = (0.45, 2.5)
"""Least and greatest height over width of the axes of a view fitted to a width."""

VIEW_FLAT_HEIGHT = 150.0
"""Greatest value of the least height of the axes of a view, in points: a flat view (a line seen
edge on) keeps about the height of Funis 1.0.0 however wide the figure."""

VIEW_ROOM = 24.0
"""Least room around a view fitted to a width, in points: a label beside the outermost point.
It exceeds the margin of 8 % that the view has on screen only below a width of about 14 cm."""

MIN_WIDTH_CM = 5.0
"""Least width of a figure fitted to a width: below it the texts at 9 pt leave no room for the drawing."""


def figure_for(drawing, width_cm=14.0, scale=None, dpi=100, grid=True, font_size=9.0):
    """Figure with one drawing, at a width in cm or at a scale in cm per unit.

    With a scale the figure is a drawing to scale without axes, with a scale
    bar and the title, as in a plate (views to scale only: a graph of
    functions is always fitted to the width). Without it the drawing fills the given
    width with its axes and grid. The margins follow the texts actually drawn
    (tick labels, axis labels, title), the title is broken into lines that fit
    the sheet and the height of the sheet follows the drawing, so that no text
    is cut; a width below MIN_WIDTH_CM is raised to it. The figure has an Agg
    canvas and is not registered with pyplot: save it with fig.savefig and let
    it go.
    """
    apply_style()
    if drawing.aspect != "equal":
        scale = None
    if scale is not None:
        return _figure_to_scale(drawing, scale, dpi, font_size)
    width_cm = max(float(width_cm), MIN_WIDTH_CM)
    fig = Figure(figsize=(width_cm / 2.54, 0.62 * width_cm / 2.54), dpi=dpi)
    FigureCanvasAgg(fig)
    ax = fig.add_axes([0.13, 0.17, 0.83, 0.71])
    draw(ax, drawing, grid=grid, frame=True, title=False, font_size=font_size)
    shape = _view_shape(ax, drawing) if drawing.aspect == "equal" else _graph_shape
    _fit_to_width(fig, ax, _title(ax, drawing.name, font_size), drawing.name, shape)
    return fig


def _graph_shape(width, k, apply=False):
    """Height of the axes of a graph for a width, both in pixels (k pixels per point)."""
    return max(GRAPH_RATIO * width, GRAPH_MIN_HEIGHT * k)


def _view_shape(ax, drawing):
    """Height of the axes of a view for a width: the view with its margin (apply: set it on the axes).

    The margin is 8 % of the larger side, as on screen, or VIEW_ROOM points
    if more, so that a narrow figure keeps room for the labels at its edges.
    """
    x0, x1, y0, y1 = drawing.extent()
    dx, dy = max(x1 - x0, 1e-6), max(y1 - y0, 1e-6)

    def shape(width, k, apply=False):
        room = VIEW_ROOM * k
        pad = max(0.08 * max(dx, dy), room * dx / max(width - 2 * room, room))
        if apply:
            ax.set_xlim(x0 - pad, x1 + pad)
            ax.set_ylim(y0 - pad, y1 + pad)
        least = min(VIEW_RATIO[0] * width, VIEW_FLAT_HEIGHT * k)
        return min(max((dy + 2 * pad) / (dx + 2 * pad) * width, least), VIEW_RATIO[1] * width)
    return shape


def _fit_to_width(fig, ax, title, text, shape):
    """Place the axes inside the sheet with room for every text, and set the height of the sheet.

    shape(width, k, apply) gives the height of the axes for their width
    (pixels, k pixels per point) and, with apply, sets the limits of a view
    for that width before the texts are measured. The title is broken into
    lines that end within the right margin and the x label into lines as wide
    as the axes; a y label longer than the axes is broken into two lines of
    even length, and the axes grow if it is still longer; once broken it
    stays so. The tick labels change with the size of the axes, so the
    placement is repeated; after the first steps the margins at the sides and
    below can only grow, until the placement no longer changes (where the
    ticks alternate between two or three sets, a margin may then exceed its
    texts by a few points).
    """
    ylabel = ax.yaxis.label
    ylength = ylabel.get_window_extent(fig.canvas.get_renderer()).height if ylabel.get_text() else 0.0
    floor = np.zeros(3)
    for step in range(16):
        sides, top = _margins(fig, ax, title, text, shape, ylength)
        if step > 6:
            sides = np.maximum(sides, floor)
        floor = sides
        if _place(fig, ax, shape, sides, top):
            break


def _margins(fig, ax, title, text, shape, ylength):
    """Room taken by the texts at the left, right and bottom of the axes, and above them, in pixels.

    The limits of a view are set for the present width of the axes, the title
    and the x label are broken for it, and a long y label is halved.
    """
    renderer = fig.canvas.get_renderer()
    k = renderer.points_to_pixels(1.0)
    box = ax.get_position().transformed(fig.transFigure)
    shape(box.width, k, apply=True)
    _wrap(text, fig.bbox.width - MARGIN * k - box.x0, title, renderer)
    xlabel, ylabel = ax.xaxis.label, ax.yaxis.label
    if xlabel.get_text():
        _wrap(xlabel.get_text().replace("\n", " "), box.width, xlabel, renderer)
    if ylabel.get_text() and "\n" not in ylabel.get_text() and ylength > box.height:
        _halve(ylabel.get_text(), ylabel, renderer)
    # the sides measured with an empty title, since matplotlib counts a title in its
    # full width; the top with the title, as matplotlib places it (above the
    # exponent of the y axis, if any)
    wrapped = title.get_text()
    title.set_text("")
    tight = ax.get_tightbbox(renderer)
    title.set_text(wrapped)
    top = max(ax.get_tightbbox(renderer).y1 - box.y1, 0.0)
    sides = np.array([box.x0 - tight.x0, tight.x1 - box.x1, box.y0 - tight.y0]).clip(0.0)
    return sides, top


def _place(fig, ax, shape, sides, top):
    """Set the axes and the height of the sheet for the given margins; True if nothing changed."""
    renderer = fig.canvas.get_renderer()
    k = renderer.points_to_pixels(1.0)
    m = MARGIN * k
    W = fig.bbox.width
    left, right, bottom = sides
    ylabel = ax.yaxis.label
    aw = max(W - 2 * m - left - right, 4 * m)
    ah = max(shape(aw, k), 1.04 * ylabel.get_window_extent(renderer).height if ylabel.get_text() else 0.0)
    H = ah + bottom + top + 2 * m
    new = np.array([(m + left) / W, (m + bottom) / H, aw / W, ah / H])
    old = np.array(ax.get_position().bounds)
    if abs(H - fig.bbox.height) < 0.5 and np.all(np.abs(new - old) * [W, H, W, H] < 0.5):
        return True
    fig.set_size_inches(W / fig.dpi, H / fig.dpi)
    ax.set_position(new)
    return False


def _wrap(text, length, artist, renderer, along="width"):
    """Set on the artist the text broken at spaces into lines no longer than length (pixels).

    The length of a line is its width, or its height for a rotated text
    (along="height"). A single word longer than the length keeps its line, and
    so does an equality such as "T = 8 kN" (see _words).
    """
    def size():
        box = artist.get_window_extent(renderer)
        return box.width if along == "width" else box.height

    lines, line = [], ""
    for word in _words(text):
        trial = line + " " + word if line else word
        artist.set_text(trial)
        if line and size() > length:
            lines.append(line)
            line = word
        else:
            line = trial
    lines.append(line)
    artist.set_text("\n".join(lines))


def _halve(text, artist, renderer):
    """Set on a rotated artist the text broken into the two lines of most even length."""
    words = _words(text)
    best, best_length = text, np.inf
    for i in range(1, len(words)):
        artist.set_text(" ".join(words[:i]) + "\n" + " ".join(words[i:]))
        length = artist.get_window_extent(renderer).height
        if length < best_length:
            best, best_length = artist.get_text(), length
    artist.set_text(best)


def _words(text):
    """The words of a text between which a line may break: not around "=", nor between a number and its unit."""
    text = re.sub(r" = ", "\u00a0=\u00a0", text.strip())
    text = re.sub(r"(?<=\d) (?=[^\s\d]\S{0,3}(?: |$))", "\u00a0", text)
    return [w.replace("\u00a0", " ") for w in text.split(" ") if w]


SHEET_MARGIN = 0.4
"""Distance of the title and of the texts of the scale bar from the edges of a sheet to scale, in cm."""


def _figure_to_scale(drawing, scale, dpi, font_size):
    """A view to scale on a sheet without axes: title above, drawing, scale bar below.

    The sheet is the drawing with 1 cm at each side, 1.8 cm below for the scale
    bar and room above for the title; it widens when the title (one word per
    line at most) or the text of the scale bar would not fit. The title is a
    text of the axes, so the labels keep clear of it.
    """
    x0, x1, y0, y1 = drawing.extent()
    dx, dy = max(x1 - x0, 1e-6), max(y1 - y0, 1e-6)
    w_cm = scale * dx + 2.0
    fig = Figure(figsize=(w_cm / 2.54, (scale * dy + 2.8) / 2.54), dpi=dpi)
    FigureCanvasAgg(fig)
    ax = fig.add_axes([0.0, 0.0, 1.0, 1.0])
    draw(ax, drawing, grid=False, frame=False, title=False, font_size=font_size)
    ax.set_aspect("equal", adjustable="box")
    ax.axis("off")
    renderer = fig.canvas.get_renderer()
    cm = renderer.points_to_pixels(72.0 / 2.54)
    bar = None
    if drawing.unit:
        length = _nice(5.0 / scale)
        if length * scale > w_cm - 1.3:
            length = _nice_below((w_cm - 1.3) / scale)
        label = ax.text(0.0, 0.0, "%g %s  (%.3g cm/%s)" % (length, drawing.unit, scale, drawing.unit),
                        ha="center", va="bottom", fontsize=8, color="#7a7a7a")
        text_cm = label.get_window_extent(renderer).width / cm
        w_cm = max(w_cm, text_cm + 2 * SHEET_MARGIN)
        bar = (length, label, text_cm)
    title = ax.text(0.0, 1.0, "", transform=ax.transAxes, ha="left", va="top",
                    fontsize=font_size + 1, color="#243b53")
    for word in _words(drawing.name):
        title.set_text(word)
        w_cm = max(w_cm, title.get_window_extent(renderer).width / cm + 2 * SHEET_MARGIN)
    _wrap(drawing.name, (w_cm - 2 * SHEET_MARGIN) * cm, title, renderer)
    top_cm = SHEET_MARGIN + title.get_window_extent(renderer).height / cm + 0.35
    h_cm = top_cm + scale * dy + 1.8
    fig.set_size_inches(w_cm / 2.54, h_cm / 2.54)
    left, bottom = 0.5 * (x0 + x1) - 0.5 * w_cm / scale, y0 - 1.8 / scale
    ax.set_xlim(left, left + w_cm / scale)
    ax.set_ylim(bottom, bottom + h_cm / scale)
    title.set_position((SHEET_MARGIN / w_cm, 1.0 - SHEET_MARGIN / h_cm))
    if bar is not None:
        length, label, text_cm = bar
        centre = min(max(0.8 + 0.5 * length * scale, SHEET_MARGIN + 0.5 * text_cm),
                     w_cm - SHEET_MARGIN - 0.5 * text_cm)
        _scale_bar(ax, length, scale, (left + 0.8 / scale, bottom + 0.7 / scale), label, left + centre / scale)
    return fig


def _scale_bar(ax, length, scale, origin, label, text_x):
    x, y = origin
    ax.plot([x, x + length], [y, y], color="#7a7a7a", lw=1.4, solid_capstyle="butt", gid="scale-bar")
    for xx in (x, x + length):
        ax.plot([xx, xx], [y - 0.1 / scale, y + 0.1 / scale], color="#7a7a7a", lw=1.0, gid="scale-bar")
    label.set_position((text_x, y + 0.25 / scale))


def _nice_below(v):
    """The greatest of 1, 2 and 5 times a power of ten not above v."""
    e = 10 ** np.floor(np.log10(max(v, 1e-12)))
    for m in (5, 2, 1):
        if m * e <= v * (1 + 1e-9):
            return m * e
    return e


def _nice(v):
    e = 10 ** np.floor(np.log10(max(v, 1e-12)))
    for m in (1, 2, 5, 10):
        if m * e >= v:
            return m * e
    return 10 * e
