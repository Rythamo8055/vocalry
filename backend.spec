# -*- mode: python ; coding: utf-8 -*-
import os
import audio_separator

from PyInstaller.utils.hooks import collect_submodules

hiddenimports = (
    collect_submodules("audio_separator")
    + collect_submodules("librosa")
    + collect_submodules("ml_collections")
    + ["scipy.signal", "scipy.fft"]
)

as_pkg = os.path.dirname(os.path.abspath(audio_separator.__file__))

a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=[],
    datas=[
        (os.path.join(SPECPATH, "static"), "static"),
        (os.path.join(SPECPATH, "renderer", "8d_render.py"), "."),
        (os.path.join(SPECPATH, "renderer", "hrtf", "full.zip"), "hrtf"),
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
