from backend.api import create_app
from backend.repositories import LedgerRepository
from backend.services import DeliveryProvider, DeliveryResult


class FakeProvider(DeliveryProvider):
    def send(self, message):
        return DeliveryResult(True, provider_message_id="api-id")


def test_api_create_send_status_and_health():
    from fastapi.testclient import TestClient

    repo = LedgerRepository(":memory:")
    app = create_app(repository=repo, provider=FakeProvider())
    client = TestClient(app)

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}

    created = client.post("/campaigns", json={"name": "API Campaign"})
    assert created.status_code == 201
    campaign_id = created.json()["id"]

    sent = client.post(
        f"/campaigns/{campaign_id}/send",
        json={"recipients": ["a@example.com"], "subject": "Hi", "content": "Body", "sender": "s@example.com"},
    )
    assert sent.status_code == 200
    assert sent.json()["sent"] == 1

    status = client.get(f"/campaigns/{campaign_id}")
    assert status.status_code == 200
    assert status.json()["status_rollups"]["SENT"] == 1
