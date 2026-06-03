# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec that bundles the Paris Sender FastAPI backend.

Produces a single self-contained executable named ``paris-backend`` (with the
platform-appropriate ``.exe`` suffix on Windows). The Electron desktop shell
launches this binary as a child process and talks to it over loopback HTTP.

Build:

    pip install -r requirements.txt -r packaging/requirements-build.txt
    pyinstaller packaging/paris-backend.spec --clean --noconfirm

The output binary is written to ``dist/paris-backend`` and is copied into the
Electron app as an extra resource by electron-builder.
"""

from PyInstaller.utils.hooks import collect_submodules

# Backend packages and their dynamic dependencies that PyInstaller's static
# analysis can miss (uvicorn loads its protocol/loop implementations lazily).
hidden_imports = []
for package in ("backend", "uvicorn", "fastapi", "starlette", "pydantic", "anyio"):
    hidden_imports += collect_submodules(package)

block_cipher = None

a = Analysis(
    ["backend_entry.py"],
    pathex=[".."],
    binaries=[],
    datas=[],
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Heavy optional/legacy dependencies that are not needed by the API
        # server process keep the bundle small.
        "tkinter",
        "matplotlib",
        "selenium",
        "undetected_chromedriver",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="paris-backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
