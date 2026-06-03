"""FastAPI application exposing the backend service seam."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from backend.models import Status
from backend.repositories import DomainRepository, LedgerRepository
from backend.services import (
    DeliverabilityService,
    DeliveryProvider,
    DeliveryResult,
    DeliveryService,
    DomainError,
    DomainService,
    OutboundMessage,
)
from backend.validators import AutograbService
from backend.validators.compose import analyze_compose


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
    non_smtp_delivery: bool = False


class PredictRequest(BaseModel):
    """Request to predict deliverability before sending."""

    recipients: list[str] = Field(default_factory=list)
    subject: str = Field("", min_length=0)
    content: str = Field(..., min_length=1)
    sender: str = Field("sender@example.com", min_length=1)
    html: bool = False


class DomainCreate(BaseModel):
    """Request to onboard a sending domain."""

    name: str = Field(..., min_length=1)
    selector: str = Field("paris", min_length=1)
    dmarc_policy: str = Field("none")
    spf_includes: list[str] = Field(default_factory=list)


class DmarcPolicyUpdate(BaseModel):
    """Request to change a domain's DMARC policy."""

    policy: str = Field(..., min_length=1)


class PreviewRequest(BaseModel):
    """Request to render a template preview with autograb personalization."""

    template: str = Field(..., min_length=1)
    email: str = Field("recipient@example.com", min_length=1)
    html: bool = False


class AnalyzeRequest(BaseModel):
    """Request to analyze compose content for spam/ratio/placeholder issues."""

    content: str = Field(..., min_length=1)
    html: bool = False


class ProviderNotConfigured(DeliveryProvider):
    """Default provider that makes missing dependency wiring explicit."""

    def send(self, message: OutboundMessage) -> DeliveryResult:
        raise RuntimeError("delivery provider is not configured")


def _sender_domain(sender: str) -> str | None:
    if "@" not in sender:
        return None
    return sender.split("@", 1)[1].strip().lower() or None


def create_app(
    *,
    repository: LedgerRepository | None = None,
    provider: DeliveryProvider | None = None,
    domain_repository: DomainRepository | None = None,
    domain_service: DomainService | None = None,
    repository_factory: Callable[[], LedgerRepository] | None = None,
    provider_factory: Callable[[], DeliveryProvider] | None = None,
    deliverability_service: DeliverabilityService | None = None,
    enforce_verified_domains: bool = True,
    min_deliverability_score: int = 70,
) -> FastAPI:
    """Create a FastAPI app with injectable ledger, delivery, domain, and score services."""
    app = FastAPI(title="Paris Sender Backend")
    repo_singleton = repository or (repository_factory() if repository_factory else LedgerRepository(":memory:"))
    provider_singleton = provider or (provider_factory() if provider_factory else ProviderNotConfigured())
    domain_service_singleton = domain_service or DomainService(domain_repository or DomainRepository(":memory:"))
    deliverability_singleton = deliverability_service or DeliverabilityService(
        repo_singleton, domain_service_singleton, threshold=min_deliverability_score
    )
    autograb = AutograbService()

    def get_repository() -> LedgerRepository:
        return repo_singleton

    def get_provider() -> DeliveryProvider:
        return provider_singleton

    def get_domain_service() -> DomainService:
        return domain_service_singleton

    def get_deliverability_service() -> DeliverabilityService:
        return deliverability_singleton

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
        domains: DomainService = Depends(get_domain_service),
        deliverability: DeliverabilityService = Depends(get_deliverability_service),
    ) -> dict[str, Any]:
        campaign = repo.get_campaign(campaign_id)
        if campaign is None:
            raise HTTPException(status_code=404, detail="campaign not found")
        _enforce_domain(domains, payload.sender, enforce_verified_domains)
        score = deliverability.predict(
            _score_content(payload.subject, payload.content),
            payload.recipients,
            sender=payload.sender,
            html=payload.html,
        )
        if not score.passed:
            raise HTTPException(
                status_code=400,
                detail=f"deliverability score {score.score} is below required threshold {score.threshold}",
            )
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

    @app.get("/campaigns/{campaign_id}/score")
    def get_campaign_score(
        campaign_id: int,
        content: str | None = None,
        sender: str | None = None,
        html: bool = False,
        repo: LedgerRepository = Depends(get_repository),
        deliverability: DeliverabilityService = Depends(get_deliverability_service),
    ) -> dict[str, Any]:
        campaign = repo.get_campaign(campaign_id)
        if campaign is None:
            raise HTTPException(status_code=404, detail="campaign not found")
        return deliverability.score_campaign(campaign_id, content=content, html=html, sender=sender).to_dict()

    @app.post("/campaigns/{campaign_id}/predict")
    def predict_campaign(
        campaign_id: int,
        payload: PredictRequest,
        repo: LedgerRepository = Depends(get_repository),
        deliverability: DeliverabilityService = Depends(get_deliverability_service),
    ) -> dict[str, Any]:
        campaign = repo.get_campaign(campaign_id)
        if campaign is None:
            raise HTTPException(status_code=404, detail="campaign not found")
        return deliverability.predict(
            _score_content(payload.subject, payload.content),
            payload.recipients,
            sender=payload.sender,
            html=payload.html,
        ).to_dict()

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

    # ------------------------------------------------------------------ compose
    @app.post("/compose/preview")
    def compose_preview(payload: PreviewRequest) -> dict[str, Any]:
        rendered = autograb.render(payload.template, payload.email)
        context = autograb.context_from_email(payload.email)
        return {"rendered": rendered, "context": context, "html": payload.html}

    @app.post("/compose/analyze")
    def compose_analyze(payload: AnalyzeRequest) -> dict[str, Any]:
        return analyze_compose(payload.content, html=payload.html)

    # ------------------------------------------------------------------ domains
    @app.get("/domains")
    def list_domains(domains: DomainService = Depends(get_domain_service)) -> dict[str, Any]:
        return {"domains": [domain.to_dict() for domain in domains.list_domains()]}

    @app.post("/domains", status_code=201)
    def add_domain(payload: DomainCreate, domains: DomainService = Depends(get_domain_service)) -> dict[str, Any]:
        try:
            domain = domains.add_domain(
                payload.name,
                selector=payload.selector,
                dmarc_policy=payload.dmarc_policy,
                spf_includes=payload.spf_includes,
            )
        except DomainError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return _domain_payload(domains, domain)

    @app.get("/domains/{domain_id}")
    def get_domain(domain_id: int, domains: DomainService = Depends(get_domain_service)) -> dict[str, Any]:
        domain = domains.get_domain(domain_id)
        if domain is None:
            raise HTTPException(status_code=404, detail="domain not found")
        return _domain_payload(domains, domain)

    @app.post("/domains/{domain_id}/verify")
    def verify_domain(domain_id: int, domains: DomainService = Depends(get_domain_service)) -> dict[str, Any]:
        try:
            domain = domains.verify_domain(domain_id)
        except DomainError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return _domain_payload(domains, domain)

    @app.patch("/domains/{domain_id}/dmarc")
    def update_dmarc(
        domain_id: int, payload: DmarcPolicyUpdate, domains: DomainService = Depends(get_domain_service)
    ) -> dict[str, Any]:
        try:
            domain = domains.update_dmarc_policy(domain_id, payload.policy)
        except DomainError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return _domain_payload(domains, domain)

    @app.post("/domains/{domain_id}/dkim/rotate")
    def rotate_dkim(domain_id: int, domains: DomainService = Depends(get_domain_service)) -> dict[str, Any]:
        try:
            domain = domains.regenerate_dkim(domain_id)
        except DomainError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return _domain_payload(domains, domain)

    @app.delete("/domains/{domain_id}", status_code=200)
    def delete_domain(domain_id: int, domains: DomainService = Depends(get_domain_service)) -> dict[str, Any]:
        if not domains.delete_domain(domain_id):
            raise HTTPException(status_code=404, detail="domain not found")
        return {"deleted": True, "id": domain_id}

    @app.get("/domains/{domain_id}/history")
    def domain_history(domain_id: int, domains: DomainService = Depends(get_domain_service)) -> dict[str, Any]:
        domain = domains.get_domain(domain_id)
        if domain is None:
            raise HTTPException(status_code=404, detail="domain not found")
        return {"id": domain_id, "history": domains.repository.health_history(domain_id)}

    return app


def _score_content(subject: str, content: str) -> str:
    subject = subject.strip()
    return f"{subject}\n\n{content}" if subject else content


def _domain_payload(domains: DomainService, domain: Any) -> dict[str, Any]:
    data = domain.to_dict()
    data["records"] = [record.to_dict() for record in domains.required_records(domain)]
    return data


def _enforce_domain(domains: DomainService, sender: str, enforce: bool) -> None:
    if not enforce:
        return
    sender_domain = _sender_domain(sender)
    if sender_domain is None:
        return
    registered = domains.get_domain_by_name(sender_domain)
    # Backward compatible: only enforce verification once the domain is managed.
    if registered is not None and not registered.is_verified:
        raise HTTPException(
            status_code=400,
            detail=f"sender domain '{sender_domain}' is not verified; verify DKIM/SPF/DMARC before sending",
        )


app = create_app()
