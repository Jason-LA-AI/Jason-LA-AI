"""Regression tests for the default outbound-network safety boundary."""

import socket

import pytest
import requests


def test_external_http_is_blocked() -> None:
    with pytest.raises(
        AssertionError,
        match="External HTTP requests are disabled during tests",
    ):
        requests.get("https://example.invalid", timeout=1)


def test_external_socket_is_blocked() -> None:
    with socket.socket() as outbound_socket:
        with pytest.raises(
            AssertionError,
            match="External network connections are disabled during tests",
        ):
            outbound_socket.connect(("192.0.2.1", 443))
