"""Application icon: a descending helical path with its horizontal reactions.

Writes assets/icon.png (1024 px), assets/icon.ico (Windows) and, on macOS,
assets/icon.icns through iconutil.
"""
import os
import platform
import shutil
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "funis", "assets")
INK = (36, 59, 83)
ACCENT = (31, 111, 235)
VERT = (0, 124, 131)
WHITE = (255, 255, 255)


def rounded_background(size):
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    r = int(size * 0.22)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=r, fill=INK)
    return im


def draw_icon(size=1024):
    """Oblique view of one descending turn of a helix with reactions toward its axis.

    Drawn with matplotlib for smooth antialiased lines, then laid on the
    rounded background.
    """
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    from matplotlib.patches import FancyArrowPatch

    fig = Figure(figsize=(size / 100.0, size / 100.0), dpi=100)
    canvas = FigureCanvasAgg(fig)
    fig.patch.set_alpha(0.0)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(-1, 1)
    ax.set_ylim(-1, 1)
    ax.axis("off")
    ax.patch.set_alpha(0.0)
    th = np.linspace(-0.1 * np.pi, 2.6 * np.pi, 900)
    R, k = 0.56, 0.34
    x = R * np.cos(th)
    y = k * R * np.sin(th) + 0.44 - 0.86 * (th - th[0]) / (th[-1] - th[0])
    front = np.sin(th) < 0
    white, back, pink = "#ffffff", "#7f93ab", "#e08aa8"
    for mask, color, lw, z in ((~front, back, 22, 1), (front, white, 34, 3)):
        idx = np.where(mask)[0]
        for run in np.split(idx, np.where(np.diff(idx) > 1)[0] + 1):
            if len(run) > 1:
                r = np.r_[max(run[0] - 1, 0), run, min(run[-1] + 1, len(th) - 1)]
                ax.plot(x[r], y[r], color=color, lw=lw, solid_capstyle="round", zorder=z)
    for t0 in (1.2 * np.pi, 1.5 * np.pi, 1.8 * np.pi):
        i = int(np.argmin(np.abs(th - t0)))
        p = np.array([x[i], y[i]])
        out = np.array([np.cos(th[i]), np.sin(th[i]) / k])
        out = out / np.linalg.norm(out)
        tail = p + 0.34 * out
        head = p + 0.06 * out
        ax.add_patch(FancyArrowPatch(tuple(tail), tuple(head), arrowstyle="-|>", mutation_scale=80,
                                     color=pink, lw=14, shrinkA=0, shrinkB=0, zorder=4,
                                     capstyle="round"))
    for i in (0, len(th) - 1):
        ax.plot([x[i]], [y[i]], "o", color=white if front[i] else back, ms=40 if front[i] else 30,
                zorder=5 if front[i] else 1.5)
    canvas.draw()
    art = Image.frombuffer("RGBA", canvas.get_width_height(), canvas.buffer_rgba(), "raw", "RGBA", 0, 1)
    im = rounded_background(size)
    im.alpha_composite(art.resize((size, size), Image.LANCZOS))
    return im


def main():
    os.makedirs(ASSETS, exist_ok=True)
    im = draw_icon(1024)
    png = os.path.join(ASSETS, "icon.png")
    im.save(png)
    im.save(os.path.join(ASSETS, "icon.ico"), sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    if platform.system() == "Darwin" and shutil.which("iconutil"):
        tmp = tempfile.mkdtemp()
        iconset = os.path.join(tmp, "icon.iconset")
        os.makedirs(iconset)
        for n in (16, 32, 128, 256, 512):
            im.resize((n, n), Image.LANCZOS).save(os.path.join(iconset, "icon_%dx%d.png" % (n, n)))
            im.resize((2 * n, 2 * n), Image.LANCZOS).save(os.path.join(iconset, "icon_%dx%d@2x.png" % (n, n)))
        subprocess.run(["iconutil", "-c", "icns", iconset, "-o", os.path.join(ASSETS, "icon.icns")], check=True)
        shutil.rmtree(tmp)
    print("icon written to", ASSETS)


if __name__ == "__main__":
    sys.exit(main())
