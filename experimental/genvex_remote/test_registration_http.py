"""HTTP transport tests using fake local opener; no network access."""
from io import BytesIO
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs
import unittest

from registration_http import CA_URL, CARegistrationTransport, RegistrationTransportError


class Response:
    def __init__(self, code=200, body=b"0\nFake reply\n"):
        self.status = code
        self.stream = BytesIO(body)

    def read(self, n=-1):
        return self.stream.read(n)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class Opener:
    def __init__(self, response=None, error=None):
        self.response = response or Response()
        self.error = error
        self.requests = []

    def open(self, request, *, timeout):
        self.requests.append((request, timeout))
        if self.error is not None:
            raise self.error
        return self.response


class CAHTTPTests(unittest.TestCase):
    def test_fixed_https_url_form_fields_and_timeout(self):
        opener = Opener()
        transport = CARegistrationTransport(timeout=9, opener=opener)
        raw = transport(
            "fake@example.org", "fake-account-password",
            b"-----BEGIN CERTIFICATE REQUEST-----\nFAKE\n-----END CERTIFICATE REQUEST-----",
        )
        self.assertTrue(raw.startswith(b"0"))
        request, timeout = opener.requests[0]
        self.assertEqual(request.full_url, CA_URL)
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(timeout, 9)
        fields = parse_qs(request.data.decode())
        self.assertEqual(fields["email"], ["fake@example.org"])
        self.assertEqual(fields["password"], ["fake-account-password"])
        self.assertEqual(len(fields["csr"]), 1)
        self.assertNotIn("fake-account-password", request.full_url)

    def test_reject_non_200(self):
        with self.assertRaises(RegistrationTransportError):
            CARegistrationTransport(opener=Opener(response=Response(302)))(
                "fake@example.org", "fake-account-password",
                b"-----BEGIN CERTIFICATE REQUEST-----\nX",
            )

    def test_reject_large_response(self):
        with self.assertRaises(RegistrationTransportError):
            CARegistrationTransport(opener=Opener(response=Response(body=b"x" * 65537)))(
                "fake@example.org", "fake-account-password",
                b"-----BEGIN CERTIFICATE REQUEST-----\nX",
            )

    def test_redacts_transport_error(self):
        opener = Opener(error=URLError("password fake-account-password"))
        with self.assertRaises(RegistrationTransportError) as caught:
            CARegistrationTransport(opener=opener)(
                "fake@example.org", "fake-account-password",
                b"-----BEGIN CERTIFICATE REQUEST-----\nX",
            )
        self.assertNotIn("fake-account-password", str(caught.exception))

    def test_invalid_request_never_posts(self):
        opener = Opener()
        with self.assertRaises(RegistrationTransportError):
            CARegistrationTransport(opener=opener)(
                "fake@example.org", "fake-account-password", b"not a CSR"
            )
        self.assertEqual(opener.requests, [])


if __name__ == "__main__":
    unittest.main()
