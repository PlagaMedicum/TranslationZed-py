"""Tests for LanguageTool core client helpers."""

from __future__ import annotations

import io
import urllib.error

import pytest

from translationzed_py.core import languagetool as lt


def test_validate_server_url_allows_https_and_local_http() -> None:
    """Accept HTTPS URLs and localhost-only HTTP URLs."""
    assert lt.validate_server_url("https://lt.example.org") == "https://lt.example.org"
    assert lt.validate_server_url("http://localhost:8081") == "http://localhost:8081"
    assert lt.validate_server_url("http://127.0.0.1:8081/") == "http://127.0.0.1:8081"


def test_validate_server_url_rejects_non_local_http() -> None:
    """Reject plain HTTP URLs for non-local hosts."""
    try:
        lt.validate_server_url("http://example.org:8081")
    except ValueError as exc:
        assert "localhost http" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected ValueError for non-local http URL")


def test_draft_language_map_uses_defaults_and_locale_heuristics() -> None:
    """Build draft locale map with defaults plus heuristic fallbacks."""
    mapping = lt.draft_language_map(("EN", "BE", "RU", "UA", "FR", "PT-BR"))
    assert mapping["EN"] == "en-US"
    assert mapping["BE"] == "be-BY"
    assert mapping["RU"] == "ru-RU"
    assert mapping["UA"] == "uk-UA"
    assert mapping["FR"] == "fr"
    assert mapping["PT-BR"] == "pt-BR"


def test_check_text_uses_requested_level() -> None:
    """Send requested level to request layer without fallback when successful."""
    called_levels: list[str] = []

    def _fake_request(**kwargs):  # type: ignore[no-untyped-def]
        called_levels.append(str(kwargs["level"]))
        return {"matches": []}

    original = lt._perform_check_request
    lt._perform_check_request = _fake_request  # type: ignore[assignment]
    try:
        result_default = lt.check_text(
            server_url="http://127.0.0.1:8081",
            language="en-US",
            text="Text",
            level=lt.LT_LEVEL_DEFAULT,
            timeout_ms=1200,
        )
        result_picky = lt.check_text(
            server_url="http://127.0.0.1:8081",
            language="en-US",
            text="Text",
            level=lt.LT_LEVEL_PICKY,
            timeout_ms=1200,
        )
    finally:
        lt._perform_check_request = original  # type: ignore[assignment]

    assert result_default.status == lt.LT_STATUS_OK
    assert result_default.used_level == lt.LT_LEVEL_DEFAULT
    assert result_picky.status == lt.LT_STATUS_OK
    assert result_picky.used_level == lt.LT_LEVEL_PICKY
    assert called_levels == [lt.LT_LEVEL_DEFAULT, lt.LT_LEVEL_PICKY]


def test_check_text_falls_back_to_default_when_picky_is_unsupported() -> None:
    """Retry with default level and set warning when picky mode is unsupported."""
    called_levels: list[str] = []

    def _fake_request(**kwargs):  # type: ignore[no-untyped-def]
        level = str(kwargs["level"])
        called_levels.append(level)
        if level == lt.LT_LEVEL_PICKY:
            raise lt.LTRequestError(
                "LanguageTool HTTP error (400).",
                code=400,
                body="Unknown parameter: level",
            )
        return {
            "matches": [
                {
                    "offset": 1,
                    "length": 2,
                    "message": "issue",
                    "replacements": [{"value": "ok"}],
                    "rule": {"id": "R1", "category": {"id": "GRAMMAR"}},
                    "type": {"typeName": "misspelling"},
                }
            ]
        }

    original = lt._perform_check_request
    lt._perform_check_request = _fake_request  # type: ignore[assignment]
    try:
        result = lt.check_text(
            server_url="http://127.0.0.1:8081",
            language="en-US",
            text="Text",
            level=lt.LT_LEVEL_PICKY,
            timeout_ms=1200,
        )
    finally:
        lt._perform_check_request = original  # type: ignore[assignment]

    assert called_levels == [lt.LT_LEVEL_PICKY, lt.LT_LEVEL_DEFAULT]
    assert result.status == lt.LT_STATUS_OK
    assert result.used_level == lt.LT_LEVEL_DEFAULT
    assert result.fallback_used is True
    assert "Picky unsupported" in result.warning
    assert len(result.matches) == 1


def test_check_text_returns_offline_status_for_network_failures() -> None:
    """Map offline errors to offline check result status."""

    def _fake_request(**_kwargs):  # type: ignore[no-untyped-def]
        raise lt.LTOfflineError("endpoint unreachable")

    original = lt._perform_check_request
    lt._perform_check_request = _fake_request  # type: ignore[assignment]
    try:
        result = lt.check_text(
            server_url="http://127.0.0.1:8081",
            language="en-US",
            text="Text",
            level=lt.LT_LEVEL_DEFAULT,
            timeout_ms=1200,
        )
    finally:
        lt._perform_check_request = original  # type: ignore[assignment]

    assert result.status == lt.LT_STATUS_OFFLINE
    assert result.error == "endpoint unreachable"


def test_check_text_rejects_invalid_server_url() -> None:
    """Map invalid endpoint input to error status."""
    result = lt.check_text(
        server_url="ftp://localhost:8081",
        language="en-US",
        text="Text",
        level=lt.LT_LEVEL_DEFAULT,
        timeout_ms=1200,
    )
    assert result.status == lt.LT_STATUS_ERROR
    assert "http or https" in result.error


def test_normalizers_and_language_map_helpers_cover_invalid_inputs() -> None:
    """Normalize LanguageTool helper inputs and fallback mappings."""
    assert lt.normalize_timeout_ms("bad") == 1200
    assert lt.normalize_timeout_ms("50") == 100
    assert lt.normalize_timeout_ms("999999") == 30_000
    assert lt.normalize_editor_mode("bad", default="off") == "off"
    assert lt.normalize_level("bad") == lt.LT_LEVEL_DEFAULT

    loaded = lt.load_language_map('{"be":"be-BY","EN":"en-US","":"x","FR":" "}')
    assert loaded == {"BE": "be-BY", "EN": "en-US"}
    assert lt.load_language_map('["not", "an", "object"]') == {}
    assert lt.dump_language_map({" be ": "be-BY", "EN": "en-US", "FR": ""}) == (
        '{"BE":"be-BY","EN":"en-US"}'
    )
    assert lt.resolve_language_code("", {}) == "en-US"
    assert lt.resolve_language_code("fr", {}) == "fr"


def test_parse_matches_skips_invalid_entries_and_extracts_fields() -> None:
    """Parse LanguageTool matches and ignore malformed rows."""
    payload = {
        "matches": [
            "bad",
            {"offset": "x", "length": "1"},
            {"offset": "1", "length": "0"},
            {
                "offset": 3,
                "length": 2,
                "message": "Issue",
                "replacements": [{"value": "ok"}, {"value": ""}, "bad"],
                "rule": {"id": "R1", "category": {"id": "GRAMMAR"}},
                "type": {"typeName": "misspelling"},
            },
        ]
    }

    matches = lt._parse_matches(payload)
    assert len(matches) == 1
    assert matches[0].offset == 3
    assert matches[0].length == 2
    assert matches[0].message == "Issue"
    assert matches[0].replacements == ("ok",)
    assert matches[0].rule_id == "R1"
    assert matches[0].category_id == "GRAMMAR"
    assert matches[0].issue_type == "misspelling"


def test_perform_check_request_maps_transport_and_payload_errors(monkeypatch) -> None:
    """Map low-level HTTP/URL/timeout/JSON errors to typed LT errors."""
    endpoint = "http://127.0.0.1:8081/v2/check"

    http_error = urllib.error.HTTPError(
        url=endpoint,
        code=400,
        msg="Bad Request",
        hdrs=None,
        fp=io.BytesIO(b"Unknown parameter: level"),
    )
    monkeypatch.setattr(
        lt.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(http_error),
    )
    with pytest.raises(lt.LTRequestError, match="HTTP error"):
        lt._perform_check_request(
            endpoint=endpoint,
            language="en-US",
            text="text",
            level=lt.LT_LEVEL_PICKY,
            timeout_ms=1200,
        )

    url_error = urllib.error.URLError("offline")
    monkeypatch.setattr(
        lt.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(url_error),
    )
    with pytest.raises(lt.LTOfflineError, match="unreachable"):
        lt._perform_check_request(
            endpoint=endpoint,
            language="en-US",
            text="text",
            level=lt.LT_LEVEL_DEFAULT,
            timeout_ms=1200,
        )

    monkeypatch.setattr(
        lt.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(TimeoutError()),
    )
    with pytest.raises(lt.LTOfflineError, match="timed out"):
        lt._perform_check_request(
            endpoint=endpoint,
            language="en-US",
            text="text",
            level=lt.LT_LEVEL_DEFAULT,
            timeout_ms=1200,
        )

    class _Response:
        def __init__(self, payload: str) -> None:
            self._payload = payload

        def __enter__(self) -> _Response:
            return self

        def __exit__(self, *_args) -> None:  # type: ignore[no-untyped-def]
            return None

        def read(self) -> bytes:
            return self._payload.encode("utf-8")

    monkeypatch.setattr(
        lt.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: _Response("not-json"),
    )
    with pytest.raises(lt.LTRequestError, match="not valid JSON"):
        lt._perform_check_request(
            endpoint=endpoint,
            language="en-US",
            text="text",
            level=lt.LT_LEVEL_DEFAULT,
            timeout_ms=1200,
        )

    monkeypatch.setattr(
        lt.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: _Response("[]"),
    )
    with pytest.raises(lt.LTRequestError, match="must be a JSON object"):
        lt._perform_check_request(
            endpoint=endpoint,
            language="en-US",
            text="text",
            level=lt.LT_LEVEL_DEFAULT,
            timeout_ms=1200,
        )


def test_check_text_fallback_error_branches_are_reported() -> None:
    """Return typed statuses when picky fallback request also fails."""

    def _offline_fallback(**kwargs):  # type: ignore[no-untyped-def]
        if kwargs["level"] == lt.LT_LEVEL_PICKY:
            raise lt.LTRequestError(
                "LanguageTool HTTP error (400).",
                code=400,
                body="Unknown parameter: level",
            )
        raise lt.LTOfflineError("fallback offline")

    original = lt._perform_check_request
    lt._perform_check_request = _offline_fallback  # type: ignore[assignment]
    try:
        offline = lt.check_text(
            server_url="http://127.0.0.1:8081",
            language="en-US",
            text="Text",
            level=lt.LT_LEVEL_PICKY,
            timeout_ms=1200,
        )
    finally:
        lt._perform_check_request = original  # type: ignore[assignment]

    assert offline.status == lt.LT_STATUS_OFFLINE
    assert offline.fallback_used is True
    assert offline.used_level == lt.LT_LEVEL_DEFAULT

    def _request_fallback(**kwargs):  # type: ignore[no-untyped-def]
        if kwargs["level"] == lt.LT_LEVEL_PICKY:
            raise lt.LTRequestError(
                "LanguageTool HTTP error (400).",
                code=400,
                body="Unknown parameter: level",
            )
        raise lt.LTRequestError("fallback request failed", code=500, body="bad")

    lt._perform_check_request = _request_fallback  # type: ignore[assignment]
    try:
        failed = lt.check_text(
            server_url="http://127.0.0.1:8081",
            language="en-US",
            text="Text",
            level=lt.LT_LEVEL_PICKY,
            timeout_ms=1200,
        )
    finally:
        lt._perform_check_request = original  # type: ignore[assignment]

    assert failed.status == lt.LT_STATUS_ERROR
    assert failed.fallback_used is True
    assert failed.used_level == lt.LT_LEVEL_DEFAULT
    assert "fallback request failed" in failed.error

    def _direct_request_error(**_kwargs):  # type: ignore[no-untyped-def]
        raise lt.LTRequestError("direct request failed", code=500, body="bad")

    lt._perform_check_request = _direct_request_error  # type: ignore[assignment]
    try:
        direct = lt.check_text(
            server_url="http://127.0.0.1:8081",
            language="en-US",
            text="Text",
            level=lt.LT_LEVEL_DEFAULT,
            timeout_ms=1200,
        )
    finally:
        lt._perform_check_request = original  # type: ignore[assignment]

    assert direct.status == lt.LT_STATUS_ERROR
    assert direct.fallback_used is False
    assert direct.used_level == lt.LT_LEVEL_DEFAULT
    assert "direct request failed" in direct.error
