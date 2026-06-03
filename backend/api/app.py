"""FastAPI application exposing the backend service seam."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from backend.models import Status
from backend.repositories import LedgerRepository
from backend.services import DeliveryProvider, DeliveryResult, DeliveryService, OutboundMessage


class CampaignCreate(BaseModel):
    """Request to create a campaign."""

    name: str = Field(..., min_length=1)


class SendRequest(BaseModel):
    """Request to send a campaign."""

    recipients: list[str] = Field(..., min_length=1)
    subject: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)
    sender: str = Field("sender@example.com", min_length=1)
    html: bool = False


class ProviderNotConfigured(DeliveryProvider):
    """Default provider that makes missing dependency wiring explicit."""

    def send(self, message: OutboundMessage) -> DeliveryResult:
        raise RuntimeError("delivery provider is not configured")


def create_app(
    *,
    repository: LedgerRepository | None = None,
    provider: DeliveryProvider | None = None,
    repository_factory: Callable[[], LedgerRepository] | None = None,
    provider_factory: Callable[[], DeliveryProvider] | None = None,
) -> FastAPI:
    """Create a FastAPI app with injectable ledger and delivery provider."""
    app = FastAPI(title="Paris Sender Backend")
    repo_singleton = repository or (repository_factory() if repository_factory else LedgerRepository(":memory:"))
    provider_singleton = provider or (provider_factory() if provider_factory else ProviderNotConfigured())

    def get_repository() -> LedgerRepository:
        return repo_singleton

    def get_provider() -> DeliveryProvider:
        return provider_singleton

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/campaigns", status_code=201)
    def create_campaign(payload: CampaignCreate, repo: LedgerRepository = Depends(get_repository)) -> dict[str, Any]:
        campaign = repo.create_campaign(payload.name)
        return {"id": campaign.id, "name": campaign.name, "created_at": campaign.created_at.isoformat()}

    @app.post("/campaigns/{campaign_id}/send")
    def send_campaign(
        campaign_id: int,
        payload: SendRequest,
        repo: LedgerRepository = Depends(get_repository),
        delivery_provider: DeliveryProvider = Depends(get_provider),
    ) -> dict[str, Any]:
        campaign = repo.get_campaign(campaign_id)
        if campaign is None:
            raise HTTPException(status_code=404, detail="campaign not found")
        service = DeliveryService(repo, delivery_provider)
        receipts = service.send_campaign(
            campaign,
            payload.recipients,
            payload.subject,
            payload.content,
            sender=payload.sender,
            html=payload.html,
        )
        return {
            "campaign_id": campaign_id,
            "sent": sum(1 for receipt in receipts if receipt.result.success),
            "failed": sum(1 for receipt in receipts if not receipt.result.success),
            "messages": [receipt.message.id for receipt in receipts],
        }

    @app.get("/campaigns/{campaign_id}")
    def get_campaign(campaign_id: int, repo: LedgerRepository = Depends(get_repository)) -> dict[str, Any]:
        campaign = repo.get_campaign(campaign_id)
        if campaign is None:
            raise HTTPException(status_code=404, detail="campaign not found")
        rollups = repo.recipient_status_rollups(campaign_id)
        return {
            "id": campaign.id,
            "name": campaign.name,
            "status_rollups": {status.value: rollups.get(status, 0) for status in Status},
        }

    return app


app = create_app()
