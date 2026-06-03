# Paris Sender — Desktop Packaging

This directory contains the build tooling that turns the FastAPI backend into a
single, self-contained executable so the Electron desktop app can ship as a
Windows installer (`.exe`) or a macOS disk image (`.dmg`).

## Components

| File | Purpose |
| --- | --- |
| `backend_entry.py` | Frozen entrypoint wrapping `backend.server.main`. |
| `paris-backend.spec` | PyInstaller spec that bundles the backend into `paris-backend`. |
| `build_backend.py` | Runs PyInstaller and stages the binary for electron-builder. |
| `requirements-build.txt` | Build-only dependencies (PyInstaller). |

## Build the backend binary

```bash
pip install -r requirements.txt -r packaging/requirements-build.txt
python packaging/build_backend.py
```

The binary is written to `dist/paris-backend` and copied to
`electron/resources/backend/` (gitignored) where electron-builder picks it up as
an `extraResources` entry.

## Build the full desktop app

From the `electron/` directory:

```bash
npm install
npm run dist        # current platform
npm run dist:win    # Windows NSIS installer (.exe)
npm run dist:mac    # macOS disk image (.dmg)
```

`npm run dist` runs the backend build, the Vite renderer build, and
electron-builder in sequence. Installers are written to `electron/out/`.

## Runtime model

* In **development** (`npm run dev`), the backend is expected to already be
  running on `:8000`; Electron loads the Vite dev server.
* In the **packaged app**, the Electron main process picks a free loopback port,
  launches the bundled `paris-backend` binary on it, waits for `/health`, then
  opens the UI. The backend is terminated when the app quits. The selected port
  is exported via `PARIS_PORT` and read by the preload script.
