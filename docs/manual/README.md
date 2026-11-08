# User manual

`funis_manual.tex` is the source of the user manual, `docs/Funis_User_Manual.pdf`.

The manual follows the program: revise it and rebuild it whenever the program changes, and always
before a release. From the repository root, with the environment of the program:

```bash
.venv/bin/python docs/manual/make_manual.py            # figures, generated LaTeX, PDF
.venv/bin/python docs/manual/make_manual.py --skip-figures   # text changes only
```

The script draws the window, the input sections, the result tabs and the export dialog offscreen,
exports drawings of the examples with the renderer of the program, writes the version, the catalogue
of the examples and the summaries of the worked examples into `build/generated/`, compiles the source
with XeLaTeX (`tectonic`, `latexmk` or `xelatex`, or the engine given with `--engine`) and copies the
PDF to `docs/Funis_User_Manual.pdf`. Everything under `build/` is regenerated and ignored by git.

`manual_record.json` records the version, the tasks and the examples of the build with the SHA-256 of
the PDF. `tests/test_manual.py` compares it with the program, so a new version, task or example makes
the tests fail until the manual is rebuilt. Text that describes the interface or the method (fields,
menus, equations) is written by hand in `funis_manual.tex` and must be revised with the program.

Fonts: STIX Two (text and mathematics), TeX Gyre Heros (headings and interface) and Inconsolata
(code), all in TeX Live and in the Tectonic bundle. The screenshots of the published manual were made
on macOS.
