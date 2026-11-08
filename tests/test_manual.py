"""The user manual follows the program.

docs/manual/make_manual.py writes docs/Funis_User_Manual.pdf and records in
docs/manual/manual_record.json the version, the tasks and the examples it
describes, with the SHA-256 of the PDF. A new version, task or example, or a
PDF replaced by hand, makes these tests fail until the manual is revised and
rebuilt:

    .venv/bin/python docs/manual/make_manual.py
"""
import hashlib
import json
import os

from funis import __version__
from funis.examples import EXAMPLES
from funis.model import TASKS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RECORD = os.path.join(ROOT, "docs", "manual", "manual_record.json")
REBUILD = "rebuild the user manual: python docs/manual/make_manual.py"


def _record():
    with open(RECORD, encoding="utf-8") as fh:
        return json.load(fh)


def test_manual_describes_this_version():
    assert _record()["version"] == __version__, REBUILD


def test_manual_describes_every_task_and_example():
    record = _record()
    assert record["tasks"] == list(TASKS.values()), REBUILD
    assert record["examples"] == list(EXAMPLES), REBUILD


def test_manual_pdf_is_the_recorded_build():
    record = _record()
    with open(os.path.join(ROOT, record["pdf"]), "rb") as fh:
        digest = hashlib.sha256(fh.read()).hexdigest()
    assert digest == record["pdf_sha256"], REBUILD
