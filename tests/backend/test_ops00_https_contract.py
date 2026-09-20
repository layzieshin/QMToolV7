"""OPS00-B loopback HTTPS contract: file-PEM TLS and same-origin static fixture."""
from __future__ import annotations

import datetime
import json
import socket
import ssl
import subprocess
import sys
import urllib.error
import urllib.request
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


def probe_request(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    timeout: float = 2.0,
    ssl_context: ssl.SSLContext | None = None,
) -> tuple[int, bytes, dict[str, str]]:
    """Issue an HTTP request and return status, body, and lowercase response headers."""
    request = urllib.request.Request(url, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=ssl_context) as response:
            response_headers = {name.lower(): value for name, value in response.headers.items()}
            return response.status, response.read(), response_headers
    except urllib.error.HTTPError as exc:
        response_headers = {name.lower(): value for name, value in exc.headers.items()}
        return exc.code, exc.read(), response_headers
    except urllib.error.URLError as exc:
        raise RuntimeError(f"{method} probe failed for {url}: {exc}") from exc


def assert_module_imports_no_windows_modules(module_name: str, forbidden: tuple[str, ...]) -> None:
    script = """
import importlib
import sys

forbidden = set(sys.argv[2].split(","))
preloaded = sorted(forbidden.intersection(sys.modules))
if preloaded:
    raise SystemExit(f"unexpected modules loaded before target import: {preloaded!r}")
importlib.import_module(sys.argv[1])
loaded = sorted(forbidden.intersection(sys.modules))
if loaded:
    raise SystemExit(f"target import loaded forbidden modules: {loaded!r}")
"""
    completed = subprocess.run(
        [sys.executable, "-c", script, module_name, ",".join(forbidden)],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


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
    assert_module_imports_no_windows_modules("src.backend.tls_config", forbidden)


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


_FIXTURE_INDEX_HTML = "<!doctype html><html><body>ops00-b-fixture</body></html>"
_FIXTURE_404_HTML = "<!doctype html><html><body>ops00-b-404-page</body></html>"
_FIXTURE_API_COLLISION_BODY = "ops00-b-static-api-collision"


def _write_webclient_fixture(
    fixture_dir: Path,
    *,
    include_404_html: bool = False,
    include_api_collision: bool = False,
) -> None:
    fixture_dir.mkdir(parents=True, exist_ok=True)
    fixture_dir.joinpath("index.html").write_text(_FIXTURE_INDEX_HTML, encoding="utf-8")
    if include_404_html:
        fixture_dir.joinpath("404.html").write_text(_FIXTURE_404_HTML, encoding="utf-8")
    if include_api_collision:
        collision_dir = fixture_dir / "api" / "v1"
        collision_dir.mkdir(parents=True, exist_ok=True)
        collision_dir.joinpath("not-a-route").write_text(
            _FIXTURE_API_COLLISION_BODY,
            encoding="utf-8",
        )
    assets_dir = fixture_dir / "assets"
    assets_dir.mkdir()
    assets_dir.joinpath("app.js").write_text("console.log('ops00-b-fixture');", encoding="utf-8")


def _start_https_fixture_host(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    fixture_dir: Path,
) -> tuple[ServiceHost, ssl.SSLContext, str]:
    cert_path, key_path = write_ephemeral_self_signed_pem(tmp_path)
    bind_port = _reserve_port()

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
    status = host.status()
    base_url = f"https://{status.bind_host}:{status.bind_port}"
    return host, ssl_context_trusting(cert_path), base_url


def test_same_origin_static_fixture_reachable_over_https(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture_dir = tmp_path / "webclient-fixture"
    _write_webclient_fixture(fixture_dir)
    host, ctx, base_url = _start_https_fixture_host(tmp_path, monkeypatch, fixture_dir=fixture_dir)
    try:
        health = probe_health(
            host.status().bind_host,
            host.status().bind_port,
            use_https=True,
            ssl_context=ctx,
        )
        assert health["status"] == "ok"

        status_code, body = probe_url(f"{base_url}/", ssl_context=ctx)
        assert status_code == 200
        assert body.decode("utf-8") == _FIXTURE_INDEX_HTML

        api_status_code, _ = probe_url(f"{base_url}/api/v1/auth/csrf", ssl_context=ctx)
        assert api_status_code in {200, 204}
    finally:
        host.stop(timeout=15.0)


def test_spa_html_deep_link_fallback_serves_fixture_index_with_dist_404_html(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture_dir = tmp_path / "webclient-fixture"
    _write_webclient_fixture(fixture_dir, include_404_html=True)
    host, ctx, base_url = _start_https_fixture_host(tmp_path, monkeypatch, fixture_dir=fixture_dir)
    try:
        status_code, body, _ = probe_request(
            f"{base_url}/documents/DOC-WEB01-K1-PIS/signature",
            headers={"Accept": "text/html"},
            ssl_context=ctx,
        )
        assert status_code == 200
        assert body.decode("utf-8") == _FIXTURE_INDEX_HTML

        asset_status, asset_body, _ = probe_request(
            f"{base_url}/assets/missing.js",
            headers={"Accept": "text/html"},
            ssl_context=ctx,
        )
        assert asset_status == 404
        assert _FIXTURE_INDEX_HTML.encode("utf-8") not in asset_body
        assert asset_body.decode("utf-8") == _FIXTURE_404_HTML
    finally:
        host.stop(timeout=15.0)


def test_spa_html_deep_link_fallback_serves_fixture_index(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture_dir = tmp_path / "webclient-fixture"
    _write_webclient_fixture(fixture_dir)
    host, ctx, base_url = _start_https_fixture_host(tmp_path, monkeypatch, fixture_dir=fixture_dir)
    try:
        deep_link = (
            f"{base_url}/documents/DOC-WEB01-K1-PIS"
            "?version=1&section=history"
        )
        status_code, body, _ = probe_request(
            deep_link,
            headers={"Accept": "text/html"},
            ssl_context=ctx,
        )
        assert status_code == 200
        assert body.decode("utf-8") == _FIXTURE_INDEX_HTML
    finally:
        host.stop(timeout=15.0)


def test_spa_fallback_preserves_existing_root_and_asset_serving(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture_dir = tmp_path / "webclient-fixture"
    _write_webclient_fixture(fixture_dir)
    host, ctx, base_url = _start_https_fixture_host(tmp_path, monkeypatch, fixture_dir=fixture_dir)
    try:
        root_status, root_body, _ = probe_request(f"{base_url}/", ssl_context=ctx)
        assert root_status == 200
        assert root_body.decode("utf-8") == _FIXTURE_INDEX_HTML

        asset_status, asset_body, _ = probe_request(f"{base_url}/assets/app.js", ssl_context=ctx)
        assert asset_status == 200
        assert asset_body == b"console.log('ops00-b-fixture');"
    finally:
        host.stop(timeout=15.0)


def test_spa_head_deep_link_returns_html_headers_and_empty_body(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture_dir = tmp_path / "webclient-fixture"
    _write_webclient_fixture(fixture_dir)
    host, ctx, base_url = _start_https_fixture_host(tmp_path, monkeypatch, fixture_dir=fixture_dir)
    try:
        status_code, body, headers = probe_request(
            f"{base_url}/documents/DOC-WEB01-K1-PIS/signature",
            method="HEAD",
            headers={"Accept": "text/html"},
            ssl_context=ctx,
        )
        assert status_code == 200
        assert body == b""
        assert "text/html" in headers.get("content-type", "")
    finally:
        host.stop(timeout=15.0)


def test_missing_asset_stays_404_without_spa_shell(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture_dir = tmp_path / "webclient-fixture"
    _write_webclient_fixture(fixture_dir, include_404_html=True)
    host, ctx, base_url = _start_https_fixture_host(tmp_path, monkeypatch, fixture_dir=fixture_dir)
    try:
        status_code, body, _ = probe_request(
            f"{base_url}/assets/missing.js",
            headers={"Accept": "text/html"},
            ssl_context=ctx,
        )
        assert status_code == 404
        assert _FIXTURE_INDEX_HTML.encode("utf-8") not in body
        assert body.decode("utf-8") == _FIXTURE_404_HTML
    finally:
        host.stop(timeout=15.0)


def test_unknown_api_route_stays_json_404_without_spa_shell(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture_dir = tmp_path / "webclient-fixture"
    _write_webclient_fixture(
        fixture_dir,
        include_404_html=True,
        include_api_collision=True,
    )
    host, ctx, base_url = _start_https_fixture_host(tmp_path, monkeypatch, fixture_dir=fixture_dir)
    try:
        status_code, body, headers = probe_request(
            f"{base_url}/api/v1/not-a-route",
            headers={"Accept": "text/html"},
            ssl_context=ctx,
        )
        assert status_code == 404
        assert "application/json" in headers.get("content-type", "")
        payload = json.loads(body.decode("utf-8"))
        assert "detail" in payload
        assert _FIXTURE_INDEX_HTML.encode("utf-8") not in body
        assert _FIXTURE_404_HTML.encode("utf-8") not in body
        assert _FIXTURE_API_COLLISION_BODY.encode("utf-8") not in body
    finally:
        host.stop(timeout=15.0)


def test_non_html_vue_route_stays_404(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture_dir = tmp_path / "webclient-fixture"
    _write_webclient_fixture(fixture_dir)
    host, ctx, base_url = _start_https_fixture_host(tmp_path, monkeypatch, fixture_dir=fixture_dir)
    try:
        status_code, body, _ = probe_request(
            f"{base_url}/documents/DOC-WEB01-K1-PIS/signature",
            headers={"Accept": "application/json"},
            ssl_context=ctx,
        )
        assert status_code == 404
        assert _FIXTURE_INDEX_HTML.encode("utf-8") not in body
    finally:
        host.stop(timeout=15.0)


def test_sec_fetch_dest_not_document_stays_404(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture_dir = tmp_path / "webclient-fixture"
    _write_webclient_fixture(fixture_dir)
    host, ctx, base_url = _start_https_fixture_host(tmp_path, monkeypatch, fixture_dir=fixture_dir)
    try:
        status_code, body, _ = probe_request(
            f"{base_url}/documents/DOC-WEB01-K1-PIS/signature",
            headers={"Accept": "text/html", "Sec-Fetch-Dest": "empty"},
            ssl_context=ctx,
        )
        assert status_code == 404
        assert _FIXTURE_INDEX_HTML.encode("utf-8") not in body
    finally:
        host.stop(timeout=15.0)


def test_post_on_vue_route_stays_405(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture_dir = tmp_path / "webclient-fixture"
    _write_webclient_fixture(fixture_dir)
    host, ctx, base_url = _start_https_fixture_host(tmp_path, monkeypatch, fixture_dir=fixture_dir)
    try:
        status_code, body, _ = probe_request(
            f"{base_url}/documents/DOC-WEB01-K1-PIS/signature",
            method="POST",
            headers={"Accept": "text/html"},
            ssl_context=ctx,
        )
        assert status_code == 405
        assert _FIXTURE_INDEX_HTML.encode("utf-8") not in body
    finally:
        host.stop(timeout=15.0)


def test_health_ready_and_existing_api_route_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture_dir = tmp_path / "webclient-fixture"
    _write_webclient_fixture(fixture_dir)
    host, ctx, base_url = _start_https_fixture_host(tmp_path, monkeypatch, fixture_dir=fixture_dir)
    try:
        health_status, health_body, _ = probe_request(f"{base_url}/health", ssl_context=ctx)
        assert health_status == 200
        assert json.loads(health_body.decode("utf-8")) == {
            "status": "ok",
            "service": "qmtool-backend",
        }

        ready_status, ready_body, _ = probe_request(f"{base_url}/ready", ssl_context=ctx)
        assert ready_status in {200, 503}
        ready_payload = json.loads(ready_body.decode("utf-8"))
        assert ready_payload["service"] == "qmtool-backend"
        assert "checks" in ready_payload
        assert isinstance(ready_payload.get("ready"), bool)
        assert _FIXTURE_INDEX_HTML.encode("utf-8") not in ready_body

        csrf_status, _, _ = probe_request(f"{base_url}/api/v1/auth/csrf", ssl_context=ctx)
        assert csrf_status in {200, 204}
    finally:
        host.stop(timeout=15.0)


def test_spa_deep_link_with_dotted_document_ids_serves_fixture_index(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture_dir = tmp_path / "webclient-fixture"
    _write_webclient_fixture(fixture_dir)
    host, ctx, base_url = _start_https_fixture_host(tmp_path, monkeypatch, fixture_dir=fixture_dir)
    try:
        for document_id in ("SOP.001", "SOP..001"):
            status_code, body, _ = probe_request(
                f"{base_url}/documents/{document_id}/signature",
                headers={"Accept": "text/html"},
                ssl_context=ctx,
            )
            assert status_code == 200
            assert body.decode("utf-8") == _FIXTURE_INDEX_HTML
    finally:
        host.stop(timeout=15.0)


@pytest.mark.parametrize(
    "accept_header",
    [
        "application/not-text/html",
        "text/html;q=0",
        "application/json, text/html;q=0",
        "text/html;q=2",
        "text/html;q=Infinity",
    ],
)
def test_rejected_accept_ranges_stay_404_without_spa_shell(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    accept_header: str,
) -> None:
    fixture_dir = tmp_path / "webclient-fixture"
    _write_webclient_fixture(fixture_dir)
    host, ctx, base_url = _start_https_fixture_host(tmp_path, monkeypatch, fixture_dir=fixture_dir)
    try:
        status_code, body, _ = probe_request(
            f"{base_url}/documents/DOC-WEB01-K1-PIS/signature",
            headers={"Accept": accept_header},
            ssl_context=ctx,
        )
        assert status_code == 404
        assert _FIXTURE_INDEX_HTML.encode("utf-8") not in body
    finally:
        host.stop(timeout=15.0)


def test_accept_html_with_surrounding_whitespace_serves_fixture_index(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture_dir = tmp_path / "webclient-fixture"
    _write_webclient_fixture(fixture_dir)
    host, ctx, base_url = _start_https_fixture_host(tmp_path, monkeypatch, fixture_dir=fixture_dir)
    try:
        status_code, body, _ = probe_request(
            f"{base_url}/documents/DOC-WEB01-K1-PIS/signature",
            headers={"Accept": " application/json ,  TEXT/HTML ; q=0.8 "},
            ssl_context=ctx,
        )
        assert status_code == 200
        assert body.decode("utf-8") == _FIXTURE_INDEX_HTML
    finally:
        host.stop(timeout=15.0)


@pytest.mark.parametrize("reserved_path", ["/docs", "/redoc", "/openapi.json"])
def test_reserved_openapi_paths_stay_non_spa_in_production(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    reserved_path: str,
) -> None:
    fixture_dir = tmp_path / "webclient-fixture"
    _write_webclient_fixture(fixture_dir, include_404_html=True)
    host, ctx, base_url = _start_https_fixture_host(tmp_path, monkeypatch, fixture_dir=fixture_dir)
    try:
        collision_name = reserved_path.lstrip("/")
        fixture_dir.joinpath(collision_name).write_text(
            "ops00-b-static-reserved-collision",
            encoding="utf-8",
        )
        status_code, body, _ = probe_request(
            f"{base_url}{reserved_path}",
            headers={"Accept": "text/html"},
            ssl_context=ctx,
        )
        assert status_code == 404
        assert _FIXTURE_INDEX_HTML.encode("utf-8") not in body
        assert _FIXTURE_404_HTML.encode("utf-8") not in body
        assert b"ops00-b-static-reserved-collision" not in body
    finally:
        host.stop(timeout=15.0)


def test_traversal_path_does_not_spa_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture_dir = tmp_path / "webclient-fixture"
    _write_webclient_fixture(fixture_dir)
    host, ctx, base_url = _start_https_fixture_host(tmp_path, monkeypatch, fixture_dir=fixture_dir)
    try:
        status_code, body, _ = probe_request(
            f"{base_url}/documents/../../index.html",
            headers={"Accept": "text/html"},
            ssl_context=ctx,
        )
        assert status_code == 404
        assert _FIXTURE_INDEX_HTML.encode("utf-8") not in body
    finally:
        host.stop(timeout=15.0)
