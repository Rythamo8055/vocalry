# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = (
    collect_submodules("audio_separator")
    + collect_submodules("librosa")
    + collect_submodules("ml_collections")
    + ["scipy.signal", "scipy.fft"]
)

as_pkg = os.path.join(os.environ.get("VIRTUAL_ENV", os.path.expanduser("~/.local")), "lib", "python3.14", "site-packages", "audio_separator")

a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=[],
    datas=[
        ("static", "static"),
        ("../renderer/8d_render.py", "."),
        ("../renderer/hrtf/full.zip", "hrtf"),
        (os.path.join(as_pkg, "models-scores.json"), "audio_separator"),
        (os.path.join(as_pkg, "models.json"), "audio_separator"),
        (os.path.join(as_pkg, "model-data.json"), "audio_separator"),
        (os.path.join(as_pkg, "ensemble_presets.json"), "audio_separator"),
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["matplotlib", "tkinter", "IPython", "pytest", "jax"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="8d-backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="8d-backend",
)
