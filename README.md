# PARIS-SENDER

Paris Sender is now an Electron/React UI backed by FastAPI services. The former desktop monolith and its source-inspection unittest suite were retired in Phase 12; active sends flow through FastAPI, `DeliveryService`, an injected SMTP or non-SMTP provider, the ledger, and centralized logging.

## Test

```bash
python -m pytest tests/ -q
```