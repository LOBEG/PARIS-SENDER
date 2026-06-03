"""Service exports."""

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
from .mime import build_mime_message

__all__ = [
    "DeliveryProvider",
    "DeliveryResult",
    "DeliveryService",
    "DomainError",
    "DomainService",
    "OutboundMessage",
    "SMTPConfig",
    "SMTPDeliveryProvider",
    "build_dkim_record",
    "build_dmarc_record",
    "build_mime_message",
    "build_spf_record",
    "generate_dkim_keypair",
    "is_valid_domain",
]
