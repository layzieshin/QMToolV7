"""OPS00-B loopback HTTPS contract: file-PEM TLS and same-origin static fixture."""
from __future__ import annotations

import datetime
import importlib
import socket
import ssl
import sys
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from qm_platform.events.event_bus import EventBus
from qm_platform.logging.audit_logger import AuditLogger
from qm_platform.logging.logger_service import LoggerService
from qm_platform.runtime.container import RuntimeContainer
from qm_platform.settings.testing import build_settings_service_for_tests
from src.backend.bootstrap import BackendBootstrapError
from src.backend.service_host import ServiceHost, ServiceHostState, probe_health, probe_url


def write_ephemeral_self_signed_pem(tmp_path: Path) -> tuple[Path, Path]:
    """Create a short-lived localhost self-signed cert/key pair for loopback HTTPS tests."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    now = datetime.datetime.now(datetime.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=1))
        .not_valid_after(now + datetime.timedelta(days=1))
        .add_extension(
            x509.SubjectAlternativeName(
                [x509.DNSName("localhost"), x509.IPAddress(ipaddress_from_text("127.0.0.1"))]
            ),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    cert_path = tmp_path / "localhost.pem"
    key_path = tmp_path / "localhost-key.pem"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    return cert_path, key_path


def ipaddress_from_text(text: str):
    import ipaddress

    return ipaddress.ip_address(text)


def ssl_context_trusting(cert_path: Path) -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.load_verify_locations(cafile=str(cert_path))
    ctx.check_hostname = False
    return ctx


def _minimal_container(tmp_path: Path) -> RuntimeContainer:
    container = RuntimeContainer()
    container.register_port("logger", LoggerService(tmp_path / "platform.log"))
    container.register_port("audit_logger", AuditLogger(tmp_path / "audit.log"))
    container.register_port("event_bus", EventBus())
    container.register_port(
        "settings_service",
        build_settings_service_for_tests(tmp_path),
    )
    container.register_port("app_home", tmp_path)
    container.register_port("resource_root", tmp_path)
    return container


def _reserve_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def test_tls_module_has_no_windows_cert_store_imports() -> None:
    forbidden = (
        "win32crypt",
        "win32api",
        "win32service",
        "win32serviceutil",
        "servicemanager",
        "pywintypes",
        "certifi_win32",
    )
    for name in forbidden:
        assert name not in sys.modules, f"unexpected import of {name!r} before tls_config load"
    importlib.import_module("src.backend.tls_config")
    for name in forbidden:
        assert name not in sys.modules, f"tls_config must not import {name!r}"


def test_production_valid_self_signed_pem_serves_https_health(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cert_path, key_path = write_ephemeral_self_signed_pem(tmp_path)
    bind_port = _reserve_port()

    monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
    monkeypatch.setenv("QMTOOL_RUNTIME_PROFILE", "production")
    monkeypatch.setenv("QMTOOL_TLS_CERT_FILE", str(cert_path))
    monkeypatch.setenv("QMTOOL_TLS_KEY_FILE", str(key_path))
    monkeypatch.setenv("QMTOOL_BIND_HOST", "127.0.0.1")
    monkeypatch.setenv("QMTOOL_BIND_PORT", str(bind_port))

    container = _minimal_container(tmp_path)
    monkeypatch.setattr(
        "src.backend.service_host.build_backend_container",
        lambda: container,
    )

    host = ServiceHost()
    host.start(timeout=20.0)
    try:
        status = host.status()
        assert status.state == ServiceHostState.RUNNING
        assert status.https_enabled is True

        ctx = ssl_context_trusting(cert_path)
        payload = probe_health(
            status.bind_host,
            status.bind_port,
            use_https=True,
            ssl_context=ctx,
        )
        assert payload == {"status": "ok", "service": "qmtool-backend"}
    finally:
        host.stop(timeout=15.0)


@pytest.mark.parametrize(
    ("cert_text", "key_text", "match"),
    [
        ("not-a-pem-cert", "not-a-pem-key", "not valid PEM"),
        (None, None, "TLS certificate configuration"),
    ],
)
def test_production_invalid_or_missing_pem_rejected_before_serve(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    cert_text: str | None,
    key_text: str | None,
    match: str,
) -> None:
    monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
    monkeypatch.setenv("QMTOOL_RUNTIME_PROFILE", "production")

    if cert_text is None:
        monkeypatch.delenv("QMTOOL_TLS_CERT_FILE", raising=False)
        monkeypatch.delenv("QMTOOL_TLS_KEY_FILE", raising=False)
    else:
        cert = tmp_path / "cert.pem"
        key = tmp_path / "key.pem"
        cert.write_text(cert_text, encoding="utf-8")
        key.write_text(key_text or "", encoding="utf-8")
        monkeypatch.setenv("QMTOOL_TLS_CERT_FILE", str(cert))
        monkeypatch.setenv("QMTOOL_TLS_KEY_FILE", str(key))

    container = _minimal_container(tmp_path)
    monkeypatch.setattr(
        "src.backend.service_host.build_backend_container",
        lambda: container,
    )

    host = ServiceHost()
    with pytest.raises(BackendBootstrapError, match=match):
        host.start(timeout=5.0)
    assert host.status().state == ServiceHostState.STOPPED
    assert not host.is_serving()


def test_production_cert_key_mismatch_rejected_before_serve(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cert_a, key_a = write_ephemeral_self_signed_pem(tmp_path / "a")
    cert_b, _key_b = write_ephemeral_self_signed_pem(tmp_path / "b")

    monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
    monkeypatch.setenv("QMTOOL_RUNTIME_PROFILE", "production")
    monkeypatch.setenv("QMTOOL_TLS_CERT_FILE", str(cert_b))
    monkeypatch.setenv("QMTOOL_TLS_KEY_FILE", str(key_a))

    container = _minimal_container(tmp_path)
    monkeypatch.setattr(
        "src.backend.service_host.build_backend_container",
        lambda: container,
    )

    host = ServiceHost()
    with pytest.raises(BackendBootstrapError, match="do not match"):
        host.start(timeout=5.0)
    assert host.status().state == ServiceHostState.STOPPED


def test_same_origin_static_fixture_reachable_over_https(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cert_path, key_path = write_ephemeral_self_signed_pem(tmp_path)
    bind_port = _reserve_port()
    fixture_dir = tmp_path / "webclient-fixture"
    fixture_dir.mkdir()
    fixture_dir.joinpath("index.html").write_text(
        "<!doctype html><html><body>ops00-b-fixture</body></html>",
        encoding="utf-8",
    )

    monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
    monkeypatch.setenv("QMTOOL_RUNTIME_PROFILE", "production")
    monkeypatch.setenv("QMTOOL_TLS_CERT_FILE", str(cert_path))
    monkeypatch.setenv("QMTOOL_TLS_KEY_FILE", str(key_path))
    monkeypatch.setenv("QMTOOL_BIND_HOST", "127.0.0.1")
    monkeypatch.setenv("QMTOOL_BIND_PORT", str(bind_port))
    monkeypatch.setenv("QMTOOL_WEBCLIENT_DIST", str(fixture_dir))

    container = _minimal_container(tmp_path)
    monkeypatch.setattr(
        "src.backend.service_host.build_backend_container",
        lambda: container,
    )

    host = ServiceHost()
    host.start(timeout=20.0)
    try:
        ctx = ssl_context_trusting(cert_path)
        status = host.status()
        health = probe_health(
            status.bind_host,
            status.bind_port,
            use_https=True,
            ssl_context=ctx,
        )
        assert health["status"] == "ok"

        status_code, body = probe_url(
            f"https://{status.bind_host}:{status.bind_port}/",
            ssl_context=ctx,
        )
        assert status_code == 200
        assert b"ops00-b-fixture" in body

        api_status_code, _ = probe_url(
            f"https://{status.bind_host}:{status.bind_port}/api/v1/auth/csrf",
            ssl_context=ctx,
        )
        assert api_status_code in {200, 204}
    finally:
        host.stop(timeout=15.0)
