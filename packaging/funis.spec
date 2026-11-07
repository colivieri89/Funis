# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller specification: one-folder build, bundled as Funis.app on macOS."""
import importlib.util
import os
import sys

from PyInstaller.utils.hooks import collect_data_files

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(SPEC)), ".."))
sys.path.insert(0, ROOT)
import funis  # noqa: E402

VERSION = funis.__version__
ASSETS = os.path.join(ROOT, "funis", "assets")

datas = [(ASSETS, os.path.join("funis", "assets"))]
datas += collect_data_files("matplotlib", subdir="mpl-data")
datas += collect_data_files("ezdxf", includes=["**/*.json", "**/*.shx", "**/*.lff"])


def _present(name):
    try:
        return importlib.util.find_spec(name) is not None
    except ModuleNotFoundError:
        return False


# linprog, used by the thrust line analysis of arches, reaches HiGHS through a compiled module whose
# name depends on the scipy version. The static import is normally found; this is a safeguard.
highs = [m for m in ("scipy.optimize._highspy", "scipy.optimize._highs._highs_wrapper",
                     "scipy.optimize._highs._highs_constants") if _present(m)]

excludes = [
    "tkinter", "_tkinter", "test", "IPython", "jupyter", "notebook",  # not pydoc: recent SciPy imports it at start
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
    "PySide6.QtWebChannel", "PySide6.QtWebSockets", "PySide6.QtQml", "PySide6.QtQuick",
    "PySide6.QtQuickWidgets", "PySide6.QtQuick3D", "PySide6.Qt3DCore", "PySide6.Qt3DRender",
    "PySide6.Qt3DInput", "PySide6.Qt3DLogic", "PySide6.Qt3DAnimation", "PySide6.Qt3DExtras",
    "PySide6.QtCharts", "PySide6.QtDataVisualization", "PySide6.QtGraphs", "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets", "PySide6.QtPdf", "PySide6.QtPdfWidgets", "PySide6.QtBluetooth",
    "PySide6.QtNfc", "PySide6.QtPositioning", "PySide6.QtLocation", "PySide6.QtSensors",
    "PySide6.QtSerialPort", "PySide6.QtSerialBus", "PySide6.QtRemoteObjects", "PySide6.QtScxml",
    "PySide6.QtStateMachine", "PySide6.QtTextToSpeech", "PySide6.QtNetworkAuth", "PySide6.QtDesigner",
    "PySide6.QtHelp", "PySide6.QtUiTools", "PySide6.QtTest", "PySide6.QtSql", "PySide6.QtXml",
    "PySide6.QtHttpServer", "PySide6.QtSpatialAudio", "PySide6.QtSvgWidgets", "PySide6.QtOpenGLWidgets",
]

a = Analysis(
    [os.path.join(ROOT, "run_funis.py")],
    pathex=[ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=["matplotlib.backends.backend_qtagg", "matplotlib.backends.backend_pdf",
                   "matplotlib.backends.backend_svg", "matplotlib.backends.backend_agg",
                   "openpyxl", "ezdxf", "PIL"] + highs,
    hookspath=[],
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)
pyz = PYZ(a.pure)

icon = os.path.join(ASSETS, "icon.icns" if sys.platform == "darwin" else "icon.ico")

exe = EXE(
    pyz,
    a.scripts,
    exclude_binaries=True,
    name="Funis",
    debug=False,
    strip=False,
    upx=False,
    console=False,
    icon=icon if os.path.exists(icon) else None,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="Funis")

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="Funis.app",
        icon=icon,
        bundle_identifier="org.funis.app",
        version=VERSION,
        info_plist={
            "CFBundleName": "Funis",
            "CFBundleDisplayName": "Funis",
            "CFBundleShortVersionString": VERSION,
            "CFBundleVersion": VERSION,
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "12.0",
            "NSHumanReadableCopyright": "Funis",
            "CFBundleDocumentTypes": [{
                "CFBundleTypeName": "Funis project",
                "CFBundleTypeExtensions": ["funis"],
                "CFBundleTypeRole": "Editor",
                "LSHandlerRank": "Owner",
            }],
        },
    )
