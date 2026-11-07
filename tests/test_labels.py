"""The labels of every diagram keep clear of the geometry, on screen and in the files."""
import numpy as np
import pytest
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

from funis import analysis, labels
from funis.diagrams import GROUPS
from funis.examples import EXAMPLES
from funis.render import apply_style, draw, figure_for

MIN_CLEARANCE = 1.0
"""Points. The placement aims at labels.CLEARANCE, the check allows for font metrics."""

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
    d = RESULTS[name].drawings[key]
    for fig in (figure_for(d, width_cm=14.0, dpi=100), figure_for(d, width_cm=9.0, dpi=150)):
        worst, _ = _worst(fig)
        assert worst[2] >= MIN_CLEARANCE, "%s / %s: %r at %.1f pt from %s" % (name, key, worst[1], worst[2], worst[3])


@pytest.mark.parametrize("name,key", [(n, k) for n, k in CASES if RESULTS[n].drawings[k].aspect == "equal"])
def test_labels_clear_in_the_figures_to_scale(name, key):
    d = RESULTS[name].drawings[key]
    x0, x1, y0, y1 = d.extent()
    scale = 10.0 / max(x1 - x0, y1 - y0, 1e-9)
    worst, _ = _worst(figure_for(d, scale=scale, dpi=100))
    assert worst[2] >= MIN_CLEARANCE, "%s / %s: %r at %.1f pt from %s" % (name, key, worst[1], worst[2], worst[3])


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
    d = RESULTS["Supported: Section 7.4, point force on the helix"].drawings["plan"]
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
