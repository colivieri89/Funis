"""Project files (.funis, JSON)."""
import json
from datetime import datetime

from .. import __version__
from ..model import Project

EXTENSION = ".funis"


def save(project, path):
    data = {"application": "Funis", "version": __version__,
            "saved": datetime.now().isoformat(timespec="seconds"),
            "project": project.to_dict()}
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)


def load(path):
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if "project" not in data:
        raise ValueError("Not a Funis project file")
    return Project.from_dict(data["project"])
