"""Service exports."""

from .deliverability import DeliverabilityService
from .delivery import DeliveryProvider, DeliveryResult, DeliveryService, NonSmtpDeliveryProvider, OutboundMessage, SMTPConfig, SMTPDeliveryProvider
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
from .logging_service import LoggingService, start_log_archiver, stop_log_archiver
from .mime import build_mime_message
from .security import SecurityService
from .warmup import WarmupDecision, WarmupService, start_warmup_scheduler, stop_warmup_scheduler

__all__ = [
    "DeliverabilityService",
    "DeliveryProvider",
    "DeliveryResult",
    "DeliveryService",
    "DomainError",
    "DomainService",
    "HealthMonitorService",
    "LoggingService",
    "NonSmtpDeliveryProvider",
    "OutboundMessage",
    "SMTPConfig",
    "SMTPDeliveryProvider",
    "SecurityService",
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
    "start_log_archiver",
    "start_warmup_scheduler",
    "stop_health_monitor",
    "stop_log_archiver",
    "stop_warmup_scheduler",
]
