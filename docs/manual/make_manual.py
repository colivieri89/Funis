"""Build the user manual of Funis: docs/Funis_User_Manual.pdf.

Run from the repository root with the environment of the program:

    .venv/bin/python docs/manual/make_manual.py [--engine PATH] [--skip-figures]

1. Figures, in docs/manual/build/figures: the main window, the input sections,
   the result tabs and the export dialog drawn offscreen at twice the pixel
   density and reduced to 256 colours, and drawings of the examples written
   as PDF by the renderer of the program.
2. Generated LaTeX, in docs/manual/build/generated: version, date and the
   citation data of CITATION.cff, the catalogue of the examples, the summaries
   of the worked examples and the positions of the callouts on the main
   window, all read from the program, so that the manual follows it.
3. Compilation of docs/manual/funis_manual.tex with XeLaTeX: the engine given
   with --engine, otherwise tectonic, latexmk or xelatex found on the PATH.
4. The PDF is copied to docs/Funis_User_Manual.pdf and
   docs/manual/manual_record.json records the version, the tasks, the
   examples and the SHA-256 of the PDF. tests/test_manual.py compares this
   record with the program: a new version, task or example makes the tests
   fail until the manual is revised and rebuilt.

The settings of the installed program are not written. The figures of the
published manual were made on macOS; on another system the fonts of the
window differ.
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_SCALE_FACTOR", "2")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
BUILD = os.path.join(HERE, "build")
FIGURES = os.path.join(BUILD, "figures")
GENERATED = os.path.join(BUILD, "generated")
SOURCE = os.path.join(HERE, "funis_manual.tex")
OUTPUT = os.path.join(ROOT, "docs", "Funis_User_Manual.pdf")
RECORD = os.path.join(HERE, "manual_record.json")
sys.path.insert(0, ROOT)

SIZE = (1480, 920)
RESULT_SIZE = (1320, 860)
BENCHMARK = "Supported: Figs. 11 and 12, circular benchmark with contact"

# example, task-specific section keys to grab, file prefix
SECTION_SHOTS = [
    (BENCHMARK, ("geometry", "loads", "points", "support", "contact", "output"), ""),
    ("Supported: Fig. 9, ellipse with f = cθ", ("geometry",), "ellipse_"),
    ("Without reactions: Fig. 3, path that is not an axial equilibrium", ("geometry",), "points_"),
    ("Supported: Section 7.4, point force on the helix", ("points",), "actions_"),
    ("Without reactions: Fig. 8, exceptional helical arc", ("reaction_free",), ""),
    ("Form-finding: Fig. 6, prescribed second support", ("form",), ""),
    ("Node: Fig. 7, concentrated multidirectional force", ("node",), ""),
    ("Plane: catenary under a pseudo-static action", ("funicular", "plane_loads"), ""),
    ("Plane: funicular polygon of point loads", ("plane_points",), ""),
    ("Arch: segmental arch with fill and a point load", ("arch", "fill", "assessment"), ""),
]

# file name, example, index of the result tab
RESULT_SHOTS = [
    ("results_summary", BENCHMARK, 0),
    ("results_views", BENCHMARK, 1),
    ("results_graphs", BENCHMARK, 2),
    ("results_contact", BENCHMARK, 3),
    ("results_spatial", "Form-finding: Figs. 5 and 10, case C", 4),
    ("results_tables", BENCHMARK, 5),
    ("results_warning", "Supported: Fig. 11, contact violated at h/w = 4", 0),
    ("results_rf", "Without reactions: Fig. 3, path that is not an axial equilibrium", 1),
    ("results_ff", "Form-finding: Fig. 6, prescribed second support", 1),
    ("results_node", "Node: Fig. 7, concentrated multidirectional force", 1),
    ("results_funicular", "Plane: catenary under a pseudo-static action", 1),
    ("results_arch", "Arch: semicircular arch under a horizontal action", 1),
    ("results_arch_thrusts", "Arch: semicircular arch under a horizontal action", 3),
    ("results_arch_tables", "Arch: semicircular arch under a horizontal action", 5),
]

# file name, example, drawing key, width in cm
DRAWINGS = [
    ("sup_plan", BENCHMARK, "plan", 8.0),
    ("sup_cone", BENCHMARK, "cone", 8.0),
    ("sup_region", BENCHMARK, "region", 8.0),
    ("sup_domain", BENCHMARK, "domain", 8.0),
    ("rf_residual", "Without reactions: Fig. 3, path that is not an axial equilibrium", "residual", 8.0),
    ("rf_loads", "Without reactions: Fig. 8, exceptional helical arc", "loads", 8.0),
    ("ff_plan", "Form-finding: Figs. 5 and 10, case C", "plan", 8.0),
    ("ff_elevation", "Form-finding: Figs. 5 and 10, case C", "elevation", 8.0),
    ("ff_iterates", "Form-finding: Fig. 6, prescribed second support", "iterates", 8.0),
    ("ff_newton", "Form-finding: Fig. 6, prescribed second support", "newton", 8.0),
    ("node_polygon", "Node: Fig. 7, concentrated multidirectional force", "polygon", 8.0),
    ("node_plan", "Node: Fig. 7, concentrated multidirectional force", "node_plan", 8.0),
    ("pf_funicular", "Plane: catenary under a pseudo-static action", "funicular", 8.0),
    ("pf_polygon", "Plane: funicular polygon of point loads", "funicular", 8.0),
    ("arch_collapse", "Arch: semicircular arch under a horizontal action", "arch_collapse", 8.0),
    ("arch_domain", "Arch: semicircular arch under a horizontal action", "thrust_domain", 8.0),
    ("arch_gsf", "Arch: semicircular arch under a horizontal action", "arch_gsf", 8.0),
    ("arch_thickness", "Arch: semicircular arch of minimum thickness", "arch_thickness", 8.0),
]

# worked examples whose summary is printed in the manual: macro suffix, example
SUMMARIES = [
    ("Benchmark", BENCHMARK),
    ("Violated", "Supported: Fig. 11, contact violated at h/w = 4"),
    ("NotAxial", "Without reactions: Fig. 3, path that is not an axial equilibrium"),
    ("SecondSupport", "Form-finding: Fig. 6, prescribed second support"),
    ("Node", "Node: Fig. 7, concentrated multidirectional force"),
    ("Catenary", "Plane: catenary through a point"),
    ("ArchHorizontal", "Arch: semicircular arch under a horizontal action"),
    ("ArchThickness", "Arch: semicircular arch of minimum thickness"),
]

GROUPS = [("Supported", "Supported path"), ("Without reactions", "Path without reactions"),
          ("Form-finding", "Unknown geometry (form-finding)"), ("Node", "Node under a concentrated force"),
          ("Plane", "Plane funicular"), ("Arch", "Arch assessment")]


# ----------------------------------------------------------------- LaTeX text

SPECIAL = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_",
           "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}
SUB = dict(zip("₀₁₂₃₄₅₆₇₈₉ₜₙₕₓ", "0123456789tnhx"))
SUP = {"⁻": "−", "⁺": "+", "¹": "1"}


def tex(text):
    """Plain text of the program as LaTeX: specials escaped, Unicode sub- and superscripts converted."""
    out = []
    for ch in str(text):
        if ch in SPECIAL:
            out.append(SPECIAL[ch])
        elif ch in SUB:
            out.append(r"\textsubscript{%s}" % SUB[ch])
        elif ch in SUP:
            out.append(r"\textsuperscript{%s}" % SUP[ch])
        else:
            out.append(ch)
    s = "".join(out)
    # break long values at commas and semicolons of the program text
    return s.replace("; ", r";\allowbreak{} ")


def citation():
    """Fields of CITATION.cff read without a YAML parser (the file has a simple fixed layout)."""
    with open(os.path.join(ROOT, "CITATION.cff"), encoding="utf-8") as fh:
        text = fh.read()

    def field(name):
        m = re.search(r"^\s*-?\s*%s:\s*\"?([^\"\n]+)\"?\s*$" % re.escape(name), text, re.M)
        return m.group(1).strip() if m else ""

    return dict(doi=field("doi"), repository=field("repository-code"), given=field("given-names"),
                family=field("family-names"), orcid=field("orcid"), affiliation=field("affiliation"),
                license=field("license"), title=field("title"))


def write_generated(examples, results, callouts):
    from funis import __version__
    from funis.model import TASKS
    from funis.render import MIN_WIDTH_CM

    os.makedirs(GENERATED, exist_ok=True)
    c = citation()
    today = datetime.date.today()
    lines = [
        r"\newcommand{\FunisVersion}{%s}" % __version__,
        r"\newcommand{\ManualDate}{%d %s %d}" % (today.day, today.strftime("%B"), today.year),
        r"\newcommand{\ManualYear}{%d}" % today.year,
        r"\newcommand{\FunisDOI}{%s}" % c["doi"],
        r"\newcommand{\FunisRepository}{%s}" % c["repository"],
        r"\newcommand{\FunisAuthor}{%s %s}" % (c["given"], c["family"]),
        r"\newcommand{\FunisORCID}{%s}" % c["orcid"],
        r"\newcommand{\FunisAffiliation}{%s}" % tex(c["affiliation"]),
        r"\newcommand{\FunisLicense}{%s}" % c["license"],
        r"\newcommand{\FunisTitle}{%s}" % tex(c["title"]),
        r"\newcommand{\NumberOfExamples}{%d}" % len(examples),
        r"\newcommand{\NumberOfTasks}{%d}" % len(TASKS),
        r"\newcommand{\MinWidth}{%g}" % MIN_WIDTH_CM,
    ]
    with open(os.path.join(GENERATED, "metadata.tex"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")

    # catalogue of the examples, grouped as in the Examples menu
    rows = []
    for prefix, title in GROUPS:
        names = [n for n in examples if n.split(":")[0] == prefix]
        if not names:
            continue
        rows.append(r"\multicolumn{2}{@{}l}{\textbf{\sffamily %s}}\\[2pt]" % tex(title))
        for n in names:
            label = n.split(":", 1)[1].strip()
            notes = results[n]["notes"]
            rows.append(r"%s & %s\\" % (tex(label), tex(notes) if notes else "\\textendash"))
        rows.append(r"\addlinespace[4pt]")
    unknown = [n for n in examples if n.split(":")[0] not in dict(GROUPS)]
    if unknown:
        raise SystemExit("examples outside the known groups: %s (add the group to GROUPS)" % unknown)
    with open(os.path.join(GENERATED, "examples.tex"), "w", encoding="utf-8") as fh:
        fh.write("\\newcommand{\\ExamplesRows}{%%\n%s}\n" % "\n".join(rows))

    # summaries of the worked examples, as the Summary tab shows them
    with open(os.path.join(GENERATED, "summaries.tex"), "w", encoding="utf-8") as fh:
        for suffix, name in SUMMARIES:
            r = results[name]
            body = "\n".join(r"%s & %s\\" % (tex(k), tex(v)) for k, v in r["summary"])
            fh.write("\\newcommand{\\Summary%s}{%%\n%s}\n" % (suffix, body))
            msgs = "\n".join(r"\item %s" % tex(m) for m in r["messages"])
            fh.write("\\newcommand{\\Messages%s}{%%\n%s}\n" % (suffix, msgs or r"\item none"))
            fh.write("\\newcommand{\\Name%s}{%s}\n" % (suffix, tex(name)))

    # callouts on the main window: fractions of the width and height
    if callouts is None:
        return
    with open(os.path.join(GENERATED, "callouts.tex"), "w", encoding="utf-8") as fh:
        for n, (x, y), side, shift in callouts:
            bx, by = {"top": (x + shift, 1.065), "bottom": (x + shift, -0.065),
                      "left": (-0.035, 1.0 - y + shift), "right": (1.035, 1.0 - y + shift)}[side]
            fh.write("\\callout{%d}{%.4f}{%.4f}{%.4f}{%.4f}\n" % (n, x, 1.0 - y, bx, by))


# ----------------------------------------------------------------- figures

def _save_png(pixmap, path, tmp, trim=False):
    """Save reduced to 256 colours; with trim, cut the rows of plain background at the bottom."""
    from PIL import Image, ImageChops
    raw = os.path.join(tmp, "raw.png")
    pixmap.save(raw)
    image = Image.open(raw).convert("RGB")
    if trim:
        bg = Image.new("RGB", image.size, image.getpixel((image.width // 2, image.height - 2)))
        box = ImageChops.difference(image, bg).getbbox()
        if box is not None and box[3] < image.height - 40:
            image = image.crop((0, 0, image.width, box[3] + 40))
    image = image.quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    image.save(path, optimize=True)
    return image.size


def _settle(app, window):
    app.processEvents()
    focus = app.focusWidget()
    if focus is not None:
        focus.clearFocus()
    for page in (window.results.views, window.results.graphs, window.results.contact, window.results.spatial):
        page.canvas.draw()
    app.processEvents()


def solve_examples():
    """Results of every example, with the notes, summary and messages as the program shows them."""
    from funis import analysis
    from funis.examples import EXAMPLES
    results = {}
    for name, fn in EXAMPLES.items():
        project = fn()
        r = analysis.run(project)
        results[name] = dict(notes=project.notes, summary=[(str(k), str(v)) for k, v in r.summary],
                             messages=list(r.messages), task=project.task, result=r)
    return results


def make_figures(results):
    """Screenshots and drawings; returns the positions of the callouts on the main window."""
    import matplotlib
    matplotlib.use("QtAgg")
    from PySide6.QtCore import QPoint, QSettings, Qt
    from PySide6.QtWidgets import QApplication, QDockWidget, QToolBar

    from funis import __app_name__
    from funis.examples import EXAMPLES
    from funis.render import figure_for
    from funis.ui import theme
    from funis.ui.dialogs import ExportDrawingsDialog
    from funis.ui.main_window import MainWindow

    if os.path.isdir(FIGURES):
        shutil.rmtree(FIGURES)  # inside docs/manual/build, ignored by git: no stale figure survives
    os.makedirs(FIGURES)
    app = QApplication([__app_name__])
    app.setApplicationName(__app_name__)
    theme.apply(app)
    with tempfile.TemporaryDirectory() as tmp:
        window = MainWindow()
        window.settings = QSettings(os.path.join(tmp, "settings.ini"), QSettings.IniFormat)
        window.resize(*SIZE)
        window.show()
        app.processEvents()

        def load(example):
            window.load_project(EXAMPLES[example](), run=True)
            if window.result is None:
                raise SystemExit("the example did not solve: %s" % example)

        # main window with callouts
        load(BENCHMARK)
        window.results.setCurrentIndex(1)
        _settle(app, window)
        _save_png(window.grab(), os.path.join(FIGURES, "window_overview.png"), tmp)
        W, H = window.width(), window.height()

        def at(widget, fx=0.5, fy=0.5):
            p = widget.mapTo(window, QPoint(0, 0))
            return ((p.x() + fx * widget.width()) / W, (p.y() + fy * widget.height()) / H)

        panel = window.panel
        toolbar = window.findChild(QToolBar, "main_toolbar")
        bar = window.menuBar()
        tabs = window.results.tabBar()

        def rect_point(widget, rect, fx=0.5, fy=0.5):
            p = widget.mapTo(window, QPoint(rect.x(), rect.y()))
            return ((p.x() + fx * rect.width()) / W, (p.y() + fy * rect.height()) / H)

        # number, target (fractions of width and height from the top left), side of the badge, shift
        callouts = [
            (1, rect_point(bar, bar.actionGeometry(bar.actions()[0]), 0.5, 0.0), "top", 0.0),
            (2, at(toolbar.widgetForAction(window.act_run), 0.5, 0.1), "top", 0.0),
            (3, at(panel.name.parentWidget(), 0.0, 0.5), "left", 0.0),
            (4, at(panel.sections["geometry"], 0.0, 0.06), "left", 0.0),
            (5, rect_point(tabs, tabs.tabRect(1), 0.5, 0.1), "top", -0.03),
            (6, at(window.results.views.selector, 0.5, 0.0), "top", 0.03),
            (7, at(window.results.views.toolbar, 0.5, 0.05), "top", 0.0),
            (8, at(window.results.views.canvas, 1.0, 0.45), "right", 0.0),
            (9, at(window.results.views.note, 0.04, 0.95), "bottom", 0.0),
            (10, at(window.status, 0.03, 0.95), "bottom", 0.0),
        ]
        print("window_overview.png")

        # input sections, with the panel at its least width so that the text stays legible in print
        dock = window.findChild(QDockWidget, "model_dock")
        window.resizeDocks([dock], [480], Qt.Horizontal)
        for example, keys, prefix in SECTION_SHOTS:
            load(example)
            _settle(app, window)
            for key in keys:
                sec = panel.sections[key]
                if not sec.isVisible():
                    raise SystemExit("section %s not visible for %s" % (key, example))
                path = os.path.join(FIGURES, "section_%s%s.png" % (prefix, key))
                _save_png(sec.grab(), path, tmp)
                print(os.path.basename(path))
        load(BENCHMARK)
        _settle(app, window)
        _save_png(panel.name.parentWidget().grab(), os.path.join(FIGURES, "section_problem.png"), tmp)

        # result tabs, in a smaller window
        window.resize(*RESULT_SIZE)
        window.resizeDocks([dock], [480], Qt.Horizontal)
        for fname, example, tab in RESULT_SHOTS:
            load(example)
            window.results.setCurrentIndex(tab)
            _settle(app, window)
            _save_png(window.results.grab(), os.path.join(FIGURES, fname + ".png"), tmp, trim=True)
            print(fname + ".png")

        # export dialog
        load(BENCHMARK)
        dlg = ExportDrawingsDialog(window.result, os.path.expanduser("~"), window)
        dlg.base.setText(os.path.join("Documents", "Funis", "benchmark"))
        dlg.show()
        app.processEvents()
        _save_png(dlg.grab(), os.path.join(FIGURES, "export_dialog.png"), tmp)
        dlg.close()
        print("export_dialog.png")
        window.dirty = False
        window.hide()

    # drawings written by the renderer of the program
    for fname, example, key, width in DRAWINGS:
        d = results[example]["result"].drawings[key]
        fig = figure_for(d, width_cm=width)
        # saved as File > Export > Drawings writes it
        fig.savefig(os.path.join(FIGURES, fname + ".pdf"), facecolor="white")
        print(fname + ".pdf")
    return callouts


# ----------------------------------------------------------------- compilation and record

def find_engine(given):
    if given:
        return given
    for name in ("tectonic", "latexmk", "xelatex"):
        path = shutil.which(name)
        if path:
            return path
    raise SystemExit("No XeLaTeX engine found: install tectonic or a TeX distribution, or pass --engine")


def compile_tex(engine):
    out = os.path.join(BUILD, "tex")
    os.makedirs(out, exist_ok=True)
    name = os.path.basename(engine)
    if name.startswith("tectonic"):
        cmds = [[engine, "--keep-logs", "--outdir", out, SOURCE]]
    elif name.startswith("latexmk"):
        cmds = [[engine, "-xelatex", "-interaction=nonstopmode", "-halt-on-error", "-outdir=" + out, SOURCE]]
    else:
        cmds = [[engine, "-interaction=nonstopmode", "-halt-on-error", "-output-directory", out, SOURCE]] * 3
    for cmd in cmds:
        subprocess.run(cmd, cwd=HERE, check=True)
    return os.path.join(out, "funis_manual.pdf")


def write_record(pdf):
    from funis import __version__
    from funis.examples import EXAMPLES
    from funis.model import TASKS
    with open(pdf, "rb") as fh:
        digest = hashlib.sha256(fh.read()).hexdigest()
    record = dict(version=__version__, built=datetime.date.today().isoformat(),
                  pdf="docs/Funis_User_Manual.pdf", pdf_sha256=digest,
                  tasks=list(TASKS.values()), examples=list(EXAMPLES))
    with open(RECORD, "w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    return digest


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--engine", help="path of tectonic, latexmk or xelatex")
    ap.add_argument("--skip-figures", action="store_true",
                    help="reuse the figures of the previous build (the generated LaTeX is written again)")
    args = ap.parse_args()
    from funis.examples import EXAMPLES
    results = solve_examples()
    if args.skip_figures:
        if not os.path.isfile(os.path.join(GENERATED, "callouts.tex")):
            raise SystemExit("no previous build in %s" % BUILD)
        callouts = None
    else:
        callouts = make_figures(results)
    write_generated(list(EXAMPLES), results, callouts)
    pdf = compile_tex(find_engine(args.engine))
    shutil.copyfile(pdf, OUTPUT)
    digest = write_record(OUTPUT)
    print("%s  %d kB  sha256 %s" % (os.path.relpath(OUTPUT, ROOT), os.path.getsize(OUTPUT) // 1024, digest[:12]))


if __name__ == "__main__":
    main()
