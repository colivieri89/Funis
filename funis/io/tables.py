"""Export of the result tables to CSV, Excel and JSON."""
import csv
import json

import numpy as np


def _cell(v):
    if isinstance(v, (np.floating, float)):
        return "" if np.isnan(v) else float(v)
    if isinstance(v, np.integer):
        return int(v)
    return v


def to_csv(result, path):
    """One file with every table, each introduced by its title."""
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow([result.title])
        w.writerow([])
        for table in result.tables.values():
            w.writerow([table.name])
            w.writerow(table.columns)
            for row in table.rows:
                w.writerow([_cell(v) for v in row])
            if table.note:
                w.writerow(["Note", table.note])
            w.writerow([])


def to_xlsx(result, path):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    wb = Workbook()
    wb.remove(wb.active)
    head = Font(bold=True, color="FFFFFF")
    fill = PatternFill("solid", fgColor="243B53")
    for key, table in result.tables.items():
        ws = wb.create_sheet(title=table.name[:31])
        ws.append([result.title])
        ws["A1"].font = Font(bold=True, size=12)
        ws.append([])
        ws.append(table.columns)
        for c in range(1, len(table.columns) + 1):
            cell = ws.cell(row=3, column=c)
            cell.font, cell.fill = head, fill
            cell.alignment = Alignment(horizontal="center")
        for row in table.rows:
            ws.append([_cell(v) for v in row])
        if table.note:
            ws.append([])
            ws.append([table.note])
        for c in range(1, len(table.columns) + 1):
            width = max(len(str(table.columns[c - 1])), 8)
            for row in table.rows:
                width = max(width, len(str(_cell(row[c - 1]))) if c - 1 < len(row) else width)
            ws.column_dimensions[get_column_letter(c)].width = min(width + 2, 48)
        ws.freeze_panes = "A4"
    if "summary" in result.tables:
        wb.move_sheet(result.tables["summary"].name, offset=-len(wb.sheetnames) + 1)
    wb.save(path)


def to_json(result, path):
    data = {"title": result.title, "project": result.project.to_dict(),
            "summary": [list(s) for s in result.summary],
            "tables": {k: {"name": t.name, "columns": t.columns,
                           "rows": [[_cell(v) for v in r] for r in t.rows], "note": t.note}
                       for k, t in result.tables.items()},
            "messages": list(result.messages)}
    if result.curve3d is not None:
        data["path"] = np.asarray(result.curve3d).tolist()
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
