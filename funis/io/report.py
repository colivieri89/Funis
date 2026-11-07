"""Self-contained HTML report with the input, the summary, the tables and the drawings."""
import base64
import html
import io
from datetime import datetime

from .. import __app_name__, __version__
from ..render import figure_for

CSS = """
body { font-family: -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif; color: #243b53;
       margin: 0; background: #f4f6f9; }
main { max-width: 1100px; margin: 0 auto; padding: 24px 32px 48px; background: white; }
h1 { font-size: 24px; margin: 0 0 4px; }
h2 { font-size: 17px; margin: 28px 0 8px; border-bottom: 1px solid #dfe5ec; padding-bottom: 4px; }
.sub { color: #6b7a8c; font-size: 13px; }
table { border-collapse: collapse; font-size: 12.5px; margin: 8px 0 4px; }
th { background: #243b53; color: white; padding: 5px 9px; text-align: left; font-weight: 600; }
td { padding: 4px 9px; border-bottom: 1px solid #e6ebf0; white-space: nowrap; }
tr:nth-child(even) td { background: #f8fafc; }
.note { color: #6b7a8c; font-size: 12px; margin: 2px 0 10px; }
.warn { background: #fff4e5; border-left: 4px solid #b57726; padding: 8px 12px; margin: 10px 0; }
figure { margin: 12px 0 20px; }
figure img { max-width: 100%; border: 1px solid #e6ebf0; }
figcaption { font-size: 12px; color: #6b7a8c; margin-top: 4px; }
.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
pre { white-space: pre-wrap; font-size: 12px; background: #f8fafc; padding: 10px; }
"""


def _figure_png(drawing, width_cm=12.0, dpi=160):
    fig = figure_for(drawing, width_cm=width_cm, dpi=dpi)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, facecolor="white")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _table_html(table):
    out = ["<table><thead><tr>"]
    out += ["<th>%s</th>" % html.escape(str(c)) for c in table.columns]
    out.append("</tr></thead><tbody>")
    for row in table.rows:
        out.append("<tr>" + "".join("<td>%s</td>" % html.escape(_fmt(v)) for v in row) + "</tr>")
    out.append("</tbody></table>")
    if table.note:
        out.append('<p class="note">%s</p>' % html.escape(table.note))
    return "".join(out)


def _fmt(v):
    if isinstance(v, float):
        return "%.4g" % v if abs(v) < 1e-3 and v != 0 else "%.4f" % v
    return str(v)


def write(result, path, include_drawings=True):
    p = result.project
    parts = ["<!DOCTYPE html><html><head><meta charset='utf-8'><title>%s</title><style>%s</style></head><body><main>"
             % (html.escape(result.title), CSS)]
    parts.append("<h1>%s</h1>" % html.escape(p.name))
    parts.append('<p class="sub">%s · %s %s · %s</p>' % (
        html.escape(p.task_label), __app_name__, __version__,
        datetime.now().strftime("%d %B %Y, %H:%M")))
    if p.notes:
        parts.append("<p>%s</p>" % html.escape(p.notes))
    for m in result.messages:
        parts.append('<div class="warn">%s</div>' % html.escape(m))
    parts.append("<h2>Summary</h2><table><tbody>")
    for k, v in result.summary:
        parts.append("<tr><td><b>%s</b></td><td>%s</td></tr>" % (html.escape(str(k)), html.escape(str(v))))
    parts.append("</tbody></table>")
    if include_drawings and result.drawings:
        parts.append("<h2>Drawings</h2><div class='grid'>")
        for key, drawing in result.drawings.items():
            parts.append("<figure><img src='data:image/png;base64,%s'><figcaption>%s</figcaption></figure>"
                         % (_figure_png(drawing), html.escape(drawing.name)))
        parts.append("</div>")
    for key, table in result.tables.items():
        if key == "summary":
            continue
        parts.append("<h2>%s</h2>" % html.escape(table.name))
        parts.append(_table_html(table))
    parts.append("<h2>Input</h2><pre>%s</pre>" % html.escape(_input_text(p)))
    parts.append("</main></body></html>")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("".join(parts))


def _input_text(project):
    import json
    return json.dumps(project.to_dict(), indent=2, ensure_ascii=False)
