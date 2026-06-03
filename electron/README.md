# Paris Sender Electron Frontend

Phase 2 replaces the legacy Tkinter UI with an Electron shell and a Vite + React renderer.

## Prerequisites

- Node.js 20+
- The Paris Sender FastAPI backend running at `http://127.0.0.1:8000`

## Install

```bash
cd electron
npm install
```

## Development

```bash
npm run dev
```

The dev script starts Vite on port 5173, waits for it, then launches Electron with hot reload from the Vite dev server.

## Build

```bash
npm run build
```

This runs `vite build` and packages the app with `electron-builder`. Build output goes to `electron/out`.

## Notes

All backend calls are centralized in `renderer/api/client.js` and target the FastAPI backend on port 8000 by default.
