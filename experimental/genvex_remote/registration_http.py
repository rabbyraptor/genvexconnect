"""Fail-closed HTTPS client for the observed LS Control legacy CA endpoint.

Network requests happen ONLY when an authorized caller explicitly invokes
CARegistrationTransport(...). No network activity at import or startup.

This is a staging component, not yet wired to HA, not an endorsement of
RSA-1024 and not permission to register certificates without user consent.
"""
from __future__ import annotations

import ssl
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import (
    HTTPRedirectHandler, HTTPSHandler, Request, build_opener,
)

CA_URL = "https://lscontrol.nabto.com/service/register"


class RegistrationTransportError(Exception):
    """Sanitized transport error; never expose upstream bodies or credentials."""


class _NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


class CARegistrationTransport:
    """One bounded, TLS-verified form POST with no redirects."""

    def __init__(self, *, timeout: int = 20, opener=None):
        if not isinstance(timeout, int) or isinstance(timeout, bool) or not 1 <= timeout <= 60:
            raise ValueError("Timeout must be between 1 and 60 seconds")
        self._timeout = timeout
        self._opener = opener or build_opener(
            HTTPSHandler(context=ssl.create_default_context()),
            _NoRedirects(),
        )

    def __call__(self, email: str, account_password: str, csr_pem: bytes) -> bytes:
        """Submit user-authorized CSR. The password is never put into a URL."""
        if (not isinstance(email, str) or not isinstance(account_password, str)
                or not email or not account_password or len(email) > 254
                or not isinstance(csr_pem, bytes) or not 1 <= len(csr_pem) <= 16384
                or b"-----BEGIN CERTIFICATE REQUEST-----" not in csr_pem):
            raise RegistrationTransportError("Invalid certificate registration request")
        try:
            payload = urlencode({
                "email": email,
                "password": account_password,
                "csr": csr_pem.decode("ascii"),
            }).encode("ascii")
            request = Request(
                CA_URL, data=payload,
                headers={"Content-Type": "application/x-www-form-urlencoded",
                         "Accept": "text/plain"},
                method="POST",
            )
            with self._opener.open(request, timeout=self._timeout) as response:
                if response.status != 200:
                    raise RegistrationTransportError("Certificate registration HTTP failure")
                result = response.read(65537)
                if len(result) > 65536:
                    raise RegistrationTransportError("Oversized certificate registration response")
                return result
        except RegistrationTransportError:
            raise
        except (HTTPError, URLError, OSError, ValueError, UnicodeError):
            raise RegistrationTransportError("Certificate registration transport failed") from None
