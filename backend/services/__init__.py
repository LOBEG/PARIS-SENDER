"""Service exports."""

from .deliverability import DeliverabilityService
from .delivery import DeliveryProvider, DeliveryResult, DeliveryService, OutboundMessage, SMTPConfig, SMTPDeliveryProvider
from .domain import (
    DomainError,
    DomainService,
    build_dkim_record,
    build_dmarc_record,
    build_spf_record,
    generate_dkim_keypair,
    is_valid_domain,
)
from .health import HealthMonitorService, ServerProbe, SmtplibProbe, start_health_monitor, stop_health_monitor
from .mime import build_mime_message
from .warmup import WarmupDecision, WarmupService, start_warmup_scheduler, stop_warmup_scheduler

__all__ = [
    "DeliverabilityService",
    "DeliveryProvider",
    "DeliveryResult",
    "DeliveryService",
    "DomainError",
    "DomainService",
    "HealthMonitorService",
    "OutboundMessage",
    "SMTPConfig",
    "SMTPDeliveryProvider",
    "ServerProbe",
    "SmtplibProbe",
    "WarmupDecision",
    "WarmupService",
    "build_dkim_record",
    "build_dmarc_record",
    "build_mime_message",
    "build_spf_record",
    "generate_dkim_keypair",
    "is_valid_domain",
    "start_health_monitor",
    "start_warmup_scheduler",
    "stop_health_monitor",
    "stop_warmup_scheduler",
]
