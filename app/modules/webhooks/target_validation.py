import asyncio
import ipaddress
import socket
from urllib.parse import urlsplit

from app.core.config import get_settings


def _address_is_public(value: str) -> bool:
    return ipaddress.ip_address(value).is_global


async def validate_webhook_target(url: str) -> None:
    """Reject non-public webhook targets outside explicitly local development environments."""
    settings = get_settings()
    if settings.webhook_allow_private_targets:
        return

    parsed = urlsplit(url)
    host = parsed.hostname
    if not host:
        raise ValueError("Webhook target must contain a hostname")

    try:
        direct_ip = ipaddress.ip_address(host)
    except ValueError:
        direct_ip = None
    if direct_ip is not None:
        if not direct_ip.is_global:
            raise ValueError("Webhook target must resolve to a public IP address")
        return

    try:
        addresses = await asyncio.to_thread(
            socket.getaddrinfo,
            host,
            parsed.port or (443 if parsed.scheme == "https" else 80),
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror as exc:
        raise ValueError("Webhook target hostname could not be resolved") from exc

    resolved = {str(entry[4][0]) for entry in addresses}
    if not resolved or any(not _address_is_public(address) for address in resolved):
        raise ValueError("Webhook target must resolve only to public IP addresses")
