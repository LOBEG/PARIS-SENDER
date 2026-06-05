# PARIS-SENDER — Full Audit & Implementation Report

**Scope:** End-to-end audit and implementation pass across auto-updates, non-SMTP
campaign failures, domain verification, desktop packaging, and observability.

**Guiding constraint (honored):** No placeholders, no mock success responses, no
fake verification states, no simulated delivery results. Every status surfaced in
the UI reflects a real backend probe or a real provider/DNS/updater result.

---

## 1. Root causes discovered

### Part 2 — Non-SMTP campaign failures (`{sent:0, failed:1}`)
The reported failure was **real**, not a UI artifact: the `DirectMxDeliveryProvider`
returns specific errors (e.g. *"no MX records found for domain X"*) and the
`DeliveryService` already recorded them to the `events` table. **The bug was that
the send endpoint and UI discarded the per-recipient error and surfaced only the
`sent`/`failed` counts**, so the actual reason was invisible to the user. This is a
classic "generic failed response that hides the root cause".

### Parts 1, 4 — Auto-update & packaging gaps
Packaging and the updater existed but were incomplete for production use:
- The updater logged only to stdout, had **no renderer UI**, no periodic checks,
  no release-channel support, and no actionable failure diagnostics.
- electron-builder produced an NSIS installer but **no portable Windows build**.
- **No CI/CD existed at all** (`.github/workflows/` was absent), so versioned
  installers and update manifests were never produced automatically.

### Part 3 — Domain verification
Audit finding: verification was **already genuine live DNS** (multi-resolver
dnspython against system + Google/Cloudflare/Quad9, real SPF/DKIM/DMARC lookups,
multi-selector DKIM with early-exit). No mock validation was found. The gap was
the absence of a single consolidated live-verification result object for the UI.

### Part 5 — Observability
Rich health/logging endpoints already existed, but there was **no backend version
exposed** and **no single aggregated diagnostics surface** for the desktop app.

---

## 2. Files modified

### Backend
- `backend/services/delivery.py` — retry with exponential backoff
  (`_deliver_with_retries`, `_backoff_delay`, `_attempt_send`, `_log_failure`),
  `SendReceipt.attempts`, configurable `DeliveryService.__init__`
  (`max_attempts`, `backoff_base`, `backoff_factor`, `backoff_cap`, injectable
  `sleeper`). Default `max_attempts=1` preserves prior single-shot behavior.
- `backend/repositories/ledger.py` — `list_campaigns`, `delete_campaign`,
  `latest_error_for_message`, `list_message_statuses`.
- `backend/api/app.py` — send endpoint now returns `failures[]` with real reasons
  and attempt counts; new endpoints `GET /campaigns/{id}/messages` (dead-letter
  view), `POST /domains/{id}/verify/live`, `GET /version`, `GET /diagnostics`;
  `/health` now includes `version`; retry config params on `create_app`.
- `backend/services/domain.py` — `resolve_a`/`resolve_mx` on `DnspythonResolver`,
  `_resolve_optional`, and `live_verification_report()` returning the required
  result shape with `verification_source="live_dns"`.
- `backend/version.py` — **new**: single source of truth for backend version.

### Electron (main)
- `electron/main/updater.js` — rewritten: IPC status events (`update:status`),
  startup + 6-hour periodic checks, stable/beta channel via
  `PARIS_UPDATE_CHANNEL`, release-notes normalization, file-logged diagnostics
  (`userData/logs/updater.log`), `update:check` / `update:install` /
  `update:get-status` / `update:get-channel` IPC handlers.
- `electron/main/preload.js` — `parisAPI.updates` bridge (onStatus/getStatus/
  getChannel/check/install).
- `electron/main/main.js` — captures the main window and wires
  `initAutoUpdate(() => mainWindowRef)`; IPC registered in dev too.

### Electron (renderer)
- `electron/renderer/components/UpdateBanner.jsx` — **new**: live update banner
  (available → downloading % → ready-to-install + release notes + restart).
- `electron/renderer/pages/Diagnostics.jsx` — **new**: centralized diagnostics
  panel (frontend/backend version + mismatch detection, DB status, overall health
  + components, update status/channel, last recorded error).
- `electron/renderer/App.jsx` — registers the Diagnostics screen and renders the
  update banner.
- `electron/renderer/pages/CampaignManager.jsx` — real failure reasons + per-message
  delivery status table.
- `electron/renderer/pages/DomainManager.jsx` — "Live DNS report" panel.
- `electron/renderer/api/client.js` — `getDiagnostics`, `getBackendVersion`,
  `getCampaignMessages`, `liveVerifyDomain`, `listCampaigns`, `deleteCampaign`.
- `electron/renderer/styles.css` — banner/diagnostics/delivery styles.
- `electron/package.json` — added `portable` Windows target.

### CI/CD
- `.github/workflows/backend-tests.yml` — **new**: runs pytest on push/PR.
- `.github/workflows/desktop-release.yml` — **new**: builds backend exe + renderer,
  packages NSIS + portable Windows builds, publishes installers and the
  electron-updater manifest (`latest.yml`) to GitHub Releases on tag push.

### Tests
- `tests/test_delivery_failure_surfacing.py` — **new** (4 tests).
- `tests/test_domain_live_verification.py` — **new** (3 tests).
- `tests/test_diagnostics_endpoint.py` — **new** (3 tests).
- `tests/test_api.py`, `tests/conftest.py` — updated for new contracts.

---

## 3. Architecture changes

- **Delivery is now observable end-to-end:** provider → real error → `events`
  table (`error` column) → `latest_error_for_message` → API `failures[]` /
  `GET /campaigns/{id}/messages` → UI. FAILED status **is** the dead-letter set
  (inspectable, no fabricated "delivered").
- **Retry/backoff** is a first-class, injectable concern in `DeliveryService`
  (deterministic in tests via `sleeper`).
- **Auto-update is event-driven** across the process boundary (main → IPC →
  renderer), with channels and persisted diagnostics.
- **Single backend version source** (`backend/version.py`) surfaced through the
  API and consumed by the diagnostics panel for mismatch detection.
- **Build provenance** moved from manual local commands to reproducible CI/CD.

---

## 4. Remaining risks

1. **Auto-update / packaging cannot be runtime-verified in this sandbox.** The
   Electron main process and electron-builder require a desktop runner. Main-process
   JS was syntax-checked (`node --check`) and the renderer builds, but the full
   packaged update flow must be validated on a Windows runner / real install.
2. **Delta updates** rely on electron-updater's NSIS blockmap (`latest.yml` +
   `.blockmap`), which the release workflow uploads; this is standard but unverified
   end-to-end here. The portable target does not support differential updates.
3. **Release signing** is not configured. Unsigned Windows builds will show
   SmartScreen warnings and some corporate environments may block updates. Add code
   signing certs (`CSC_LINK`/`CSC_KEY_PASSWORD`) to the release workflow for
   production.
4. **CI secrets:** `desktop-release.yml` publishes with the default `GITHUB_TOKEN`;
   org policies may require a PAT for cross-repo release uploads.
5. **DKIM selector coverage** is broad (~45 common selectors) but not exhaustive;
   a domain using an uncommon custom selector not configured on the record may read
   as `dkim_valid:false` — this is reported honestly, not masked.
6. **macOS/Linux release jobs** were intentionally scoped out of the Windows-focused
   acceptance criteria; the existing `dist:mac` script remains available.

---

## 5. Verification evidence

| Task | Evidence |
| --- | --- |
| Part 2 — failure reason visible | `tests/test_delivery_failure_surfacing.py` (4 tests) assert `failures[]` carries the real provider error and attempt counts; `GET /campaigns/{id}/messages` returns per-message status + latest error. |
| Part 2 — retry/backoff | FlakyProvider test asserts injected `sleeper` recorded `[0.5, 1.0]` (base·factor^(n-1)) and the message ultimately reflects the real terminal outcome. |
| Part 2 — no fake success | Messages are only marked delivered on a real provider `accepted` receipt; failures persist as FAILED with the recorded `error`. |
| Part 3 — live DNS | `tests/test_domain_live_verification.py` (3 tests) assert `live_verification_report` returns `verification_source="live_dns"` and real per-field booleans; resolver is multi-provider dnspython with timeouts. |
| Part 5 — version/diagnostics | `tests/test_diagnostics_endpoint.py` (3 tests): `/health` includes `version`, `/version` returns it, `/diagnostics` returns a real DB probe + health snapshot + last_error. |
| Full suite | `python -m pytest tests/ -q` → **143 passed, 1 skipped**. |
| Renderer | `npx vite build` → builds cleanly (39 modules). |
| Electron main | `node --check main/updater.js main/preload.js main/main.js` → OK. |
| CI workflows | YAML validated with `yaml.safe_load`. |

### How to reproduce
```bash
# Backend
pip install -r requirements.txt -r requirements-dev.txt "httpx<0.28"
python -m pytest tests/ -q

# Renderer
cd electron && npm install && npx vite build

# Packaged Windows build (on a Windows runner / locally)
cd electron && npm run dist:win   # produces NSIS Setup + Portable + latest.yml
```
