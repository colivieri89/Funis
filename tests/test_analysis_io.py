"""Every example runs, and the project and result files round-trip."""
import json

import numpy as np
import pytest

from funis import analysis
from funis.examples import EXAMPLES
from funis.io import dxf, project_file, report, tables
from funis.model import Project


@pytest.mark.parametrize("name", list(EXAMPLES))
def test_example_runs(name):
    res = analysis.run(EXAMPLES[name]())
    assert res.summary and res.tables and res.drawings
    assert "balance" in res.tables or res.project.task == "node"
    for d in res.drawings.values():
        x0, x1, y0, y1 = d.extent()
        if d.aspect == "equal":
            assert x1 - x0 + y1 - y0 > 0
        else:
            assert x1 > x0 and d.ylim[1] > d.ylim[0]


def test_examples_reproduce_the_article():
    r = analysis.run(EXAMPLES["Supported: Figs. 12 and 13, circular benchmark with contact"]())
    assert r.data["critical"] == pytest.approx(2.27890, abs=1e-4)
    assert r.data["critical_exact"] == pytest.approx(2.27890, abs=1e-5)
    assert r.data["T_min"] == pytest.approx(r.data["T_min_exact"], abs=1e-5)
    r = analysis.run(EXAMPLES["Supported: Section 5.3, pseudo-static action"]())
    assert r.data["T_min"] == pytest.approx(5.6667, abs=1e-4)
    r = analysis.run(EXAMPLES["Supported: Fig. 12, contact violated at h/w = 4"]())
    assert np.min(r.data["margin"]) < 0 and r.messages
    r = analysis.run(EXAMPLES["Form-finding: Fig. 6, prescribed second support"]())
    assert r.data["C"] == pytest.approx([-3, -4, -2], abs=1e-5)
    assert r.data["K_eigenvalues"] == pytest.approx([0.00304553, 0.693717], abs=1e-6)
    r = analysis.run(EXAMPLES["Form-finding: Fig. 11, case A"]())
    assert r.data["closed_form_error"] < 1e-10
    r = analysis.run(EXAMPLES["Without reactions: Fig. 3, path that is not an axial equilibrium"]())
    assert r.messages
    r = analysis.run(EXAMPLES["Without reactions: Fig. 3, the funicular of the same loads"]())
    assert not r.messages
    r = analysis.run(EXAMPLES["Node: Fig. 7, concentrated multidirectional force"]())
    assert r.data["node"]["angle"] == pytest.approx(19.4463, abs=1e-4)


def test_balance_of_every_example():
    """Every computed state balances, except the force of an incompatible path, whose moment does not."""
    for name, fn in EXAMPLES.items():
        res = analysis.run(fn())
        if "balance" not in res.tables or "not an axial equilibrium" in name:
            continue
        values = [float(row[-1]) for row in res.tables["balance"].rows[:2]]
        assert max(values) < 1e-6, name


def test_project_file_round_trip(tmp_path):
    for name, fn in EXAMPLES.items():
        p = fn()
        path = tmp_path / "p.funis"
        project_file.save(p, path)
        q = project_file.load(path)
        assert q.to_dict() == p.to_dict()


def test_unknown_keys_are_ignored():
    d = Project().to_dict()
    d["geometry"]["unknown"] = 1
    d["future_field"] = True
    assert Project.from_dict(d).geometry.kind == "helix"


def test_exports(tmp_path):
    res = analysis.run(EXAMPLES["Supported: Section 5.4, point force on the helix"]())
    tables.to_csv(res, tmp_path / "r.csv")
    tables.to_xlsx(res, tmp_path / "r.xlsx")
    tables.to_json(res, tmp_path / "r.json")
    dxf.write(res, tmp_path / "r.dxf")
    report.write(res, tmp_path / "r.html")
    data = json.loads((tmp_path / "r.json").read_text())
    assert data["tables"]["points"]["rows"][0][6] == pytest.approx(-0.8986, abs=1e-4)
    assert data["tables"]["stations"]["rows"][0][6] == pytest.approx(-8.0)
    assert len(data["path"]) > 100
    assert (tmp_path / "r.dxf").stat().st_size > 1000
    assert "<html" in (tmp_path / "r.html").read_text()[:50]


def test_input_errors_are_reported():
    p = EXAMPLES["Form-finding: Fig. 6, prescribed second support"]()
    p.form.target = [100.0, 0.0, 0.0]
    with pytest.raises(analysis.InputError):
        analysis.run(p)
    p = EXAMPLES["Supported: Figs. 12 and 13, circular benchmark with contact"]()
    p.geometry.helix.pitch = 0.0
    with pytest.raises(analysis.InputError):
        analysis.run(p)
    p.geometry.helix.pitch = -1.0
    p.geometry.helix.radius = -1.0
    with pytest.raises(analysis.InputError):
        analysis.run(p)


def test_point_action_outside_the_path_is_reported():
    p = EXAMPLES["Supported: Section 5.4, point force on the helix"]()
    p.point_actions[0].s = 100.0
    res = analysis.run(p)
    assert any("ignored" in m for m in res.messages)
