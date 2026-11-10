"""The labels of every diagram keep clear of the geometry, on screen and in the files,
and every text of an exported figure lies inside the sheet."""
import numpy as np
import pytest
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

from funis import analysis, labels
from funis.diagrams import GROUPS
from funis.examples import EXAMPLES
from funis.render import MIN_WIDTH_CM, apply_style, draw, figure_for

MIN_CLEARANCE = 1.0
"""Points. The placement aims at labels.CLEARANCE, the check allows for font metrics."""

OUTSIDE = 0.01
"""Points: a text may touch the edge of the sheet within rounding, not pass it."""

CASES = [(name, key) for name in EXAMPLES for key in analysis.run(EXAMPLES[name]()).drawings]


def _results():
    return {name: analysis.run(fn()) for name, fn in EXAMPLES.items()}


RESULTS = _results()


def _worst(fig):
    """The label with the least clearance, or a dummy row for a drawing without labels."""
    fig.canvas.draw()
    rows = labels.measure(fig)
    if not rows:
        return (0, "", float("inf"), "none"), rows
    return min(rows, key=lambda r: r[2]), rows


def _outside(fig):
    """How far, in points, the texts of a drawn figure pass the edges of the sheet (0 when inside).

    A view to scale fills the sheet with its axes, so their edges are the edges of the sheet.

    The labels of the drawings are not part of the layout: their distance from
    the edges of the axes is checked by labels.measure.
    """
    tight = fig.get_tightbbox(fig.canvas.get_renderer())
    W, H = fig.get_size_inches()
    return 72.0 * max(-tight.x0, -tight.y0, tight.x1 - W, tight.y1 - H, 0.0)


def _grid_figure(drawings, width_px=900, height_px=680, font_size=8.5):
    """The figure of the Diagrams tab: up to four panels on the canvas of the window."""
    apply_style()
    fig = Figure(figsize=(width_px / 100.0, height_px / 100.0), dpi=100)
    FigureCanvasAgg(fig)
    n = len(drawings)
    cols = 1 if n == 1 else 2
    rows = (n + cols - 1) // cols
    for k, d in enumerate(drawings):
        ax = fig.add_subplot(rows, cols, k + 1)
        draw(ax, d, grid=True, font_size=font_size)
    fig.subplots_adjust(left=0.07, right=0.98, top=0.94, bottom=0.08, wspace=0.22,
                        hspace=0.32 if rows < 3 else 0.55)
    return fig


@pytest.mark.parametrize("name,key", CASES)
def test_labels_clear_in_the_exported_figures(name, key):
    """Fitted to the usual widths and to the least one of the export dialog."""
    d = RESULTS[name].drawings[key]
    for width, dpi in ((14.0, 100), (9.0, 150), (MIN_WIDTH_CM, 150)):
        fig = figure_for(d, width_cm=width, dpi=dpi)
        worst, _ = _worst(fig)
        assert worst[2] >= MIN_CLEARANCE, "%s / %s at %g cm: %r at %.1f pt from %s" % (
            name, key, width, worst[1], worst[2], worst[3])
        assert _outside(fig) < OUTSIDE, "%s / %s at %g cm: a text %.1f pt outside the sheet" % (
            name, key, width, _outside(fig))


@pytest.mark.parametrize("name,key", [(n, k) for n, k in CASES if RESULTS[n].drawings[k].aspect == "equal"])
def test_labels_clear_in_the_figures_to_scale(name, key):
    """Drawn 10 cm and 2 cm long: on the small sheet the scale bar shortens and the title is broken."""
    d = RESULTS[name].drawings[key]
    x0, x1, y0, y1 = d.extent()
    for size in (10.0, 2.0):
        scale = size / max(x1 - x0, y1 - y0, 1e-9)
        fig = figure_for(d, scale=scale, dpi=100)
        worst, _ = _worst(fig)
        assert worst[2] >= MIN_CLEARANCE, "%s / %s at %g cm: %r at %.1f pt from %s" % (
            name, key, size, worst[1], worst[2], worst[3])
        assert _outside(fig) < OUTSIDE, "%s / %s at %g cm: a text %.1f pt outside the sheet" % (
            name, key, size, _outside(fig))


def test_a_narrow_figure_keeps_its_texts():
    """A long title and a long axis label are broken into lines; no width below the least one."""
    res = RESULTS["Arch: catenary arch of finite thickness"]
    loads = figure_for(res.drawings["arch_loads"], width_cm=MIN_WIDTH_CM, dpi=100)
    domain = figure_for(res.drawings["thrust_domain"], width_cm=MIN_WIDTH_CM, dpi=100)
    for fig in (loads, domain):
        fig.canvas.draw()
        assert fig.get_size_inches()[0] * 2.54 == pytest.approx(MIN_WIDTH_CM)
        assert _outside(fig) < OUTSIDE
    assert "\n" in loads.axes[0].get_title(loc="left")
    assert "\n" in domain.axes[0].get_xlabel()
    narrow = figure_for(res.drawings["arch_loads"], width_cm=1.0, dpi=100)
    assert narrow.get_size_inches()[0] * 2.54 == pytest.approx(MIN_WIDTH_CM)


def test_the_margins_follow_the_texts():
    """No band of empty sheet beyond the outermost texts, at any width."""
    d = RESULTS["Supported: Figs. 12 and 13, circular benchmark with contact"].drawings["plan"]
    for width in (MIN_WIDTH_CM, 9.0, 14.0, 40.0):
        fig = figure_for(d, width_cm=width, dpi=100)
        tight = fig.get_tightbbox(fig.canvas.get_renderer())
        W, H = fig.get_size_inches()
        assert 72.0 * max(tight.x0, tight.y0, W - tight.x1, H - tight.y1) < 20.0


def test_labels_far_from_their_point_on_large_axes():
    """At a large width the thrust lines lie far apart in points: the labels find a place further out."""
    d = RESULTS["Arch: catenary arch of finite thickness"].drawings["arch_lines"]
    fig = figure_for(d, width_cm=100.0, dpi=30)
    fig.canvas.draw()
    assert not [t for a in fig.axes[0].artists if isinstance(a, labels.LabelSet) for t in a.hidden]
    worst, _ = _worst(fig)
    assert worst[2] >= MIN_CLEARANCE


@pytest.mark.parametrize("name", list(EXAMPLES))
def test_labels_clear_in_the_window_panels(name):
    res = RESULTS[name]
    groups = [[res.drawings[k] for k in keys if k in res.drawings] for keys in GROUPS.values()]
    for group in groups:
        if not group:
            continue
        worst, _ = _worst(_grid_figure(group))
        assert worst[2] >= MIN_CLEARANCE, "%s: %r at %.1f pt from %s" % (name, worst[1], worst[2], worst[3])
        for d in group:
            worst, _ = _worst(_grid_figure([d], font_size=9.5))
            assert worst[2] >= MIN_CLEARANCE, "%s / %s: %r at %.1f pt from %s" % (name, d.name, worst[1], worst[2], worst[3])


def test_labels_follow_a_resize():
    """The same drawing placed on two canvas sizes keeps its clearance on both."""
    d = RESULTS["Supported: Section 5.4, point force on the helix"].drawings["plan"]
    fig = _grid_figure([d], 600, 400)
    worst, _ = _worst(fig)
    assert worst[2] >= MIN_CLEARANCE
    fig.set_size_inches(12, 9)
    worst, _ = _worst(fig)
    assert worst[2] >= MIN_CLEARANCE


def test_clearance_geometry():
    box = np.array([[0.0, 0.0, 10.0, 5.0]])
    segs = np.array([[[12.0, 0.0], [12.0, 5.0]], [[-5.0, 2.0], [20.0, 2.0]], [[0.0, 8.0], [10.0, 8.0]]])
    cl = labels._clearance(box, segs[:1], np.zeros(1), np.zeros((0, 2)), np.zeros(0), [])
    assert cl[0] == pytest.approx(2.0)
    cl = labels._clearance(box, segs[1:2], np.zeros(1), np.zeros((0, 2)), np.zeros(0), [])
    assert cl[0] < 0
    cl = labels._clearance(box, segs[2:], np.array([1.0]), np.zeros((0, 2)), np.zeros(0), [])
    assert cl[0] == pytest.approx(2.0)
    cl = labels._clearance(box, np.zeros((0, 2, 2)), np.zeros(0), np.array([[5.0, 2.5]]), np.array([1.0]), [])
    assert cl[0] < 0
    cl = labels._clearance(box, np.zeros((0, 2, 2)), np.zeros(0), np.zeros((0, 2)), np.zeros(0), [[13.0, 9.0, 20.0, 12.0]])
    assert cl[0] == pytest.approx(5.0)
