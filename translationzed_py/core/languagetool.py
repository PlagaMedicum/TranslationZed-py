"""LanguageTool client helpers and response normalization."""

from __future__ import annotations

import contextlib
import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

LT_LEVEL_DEFAULT = "default"
LT_LEVEL_PICKY = "picky"
LT_LEVELS = {LT_LEVEL_DEFAULT, LT_LEVEL_PICKY}
LT_STATUS_OK = "ok"
LT_STATUS_OFFLINE = "offline"
LT_STATUS_ERROR = "error"
_DEFAULT_TIMEOUT_MS = 1200
_MAX_TIMEOUT_MS = 30_000
_DEFAULT_LOCAL_SERVER_URL = "http://127.0.0.1:8081"
_API_PATH = "/v2/check"

_DEFAULT_LANGUAGE_MAP: dict[str, str] = {
    "EN": "en-US",
    "BE": "be-BY",
    "RU": "ru-RU",
    "UA": "uk-UA",
}


@dataclass(frozen=True, slots=True)
class LanguageToolMatch:
    """Represent one normalized LanguageTool match span."""

    offset: int
    length: int
    message: str
    replacements: tuple[str, ...]
    rule_id: str
    category_id: str
    issue_type: str


@dataclass(frozen=True, slots=True)
class LanguageToolCheckResult:
    """Represent LanguageTool check outcome."""

    status: str
    matches: tuple[LanguageToolMatch, ...]
    used_level: str
    fallback_used: bool
    warning: str
    error: str


class LTOfflineError(RuntimeError):
    """Represent endpoint/network-level offline failures."""


class LTRequestError(RuntimeError):
    """Represent HTTP/request failures with optional response metadata."""

    def __init__(
        self,
        message: str,
        *,
        code: int | None = None,
        body: str = "",
    ) -> None:
        """Initialize request error with optional HTTP status and response body."""
        super().__init__(message)
        self.code = code
        self.body = body


def default_server_url() -> str:
    """Return default localhost LanguageTool server URL."""
    return _DEFAULT_LOCAL_SERVER_URL


def normalize_timeout_ms(value: object, *, default: int = _DEFAULT_TIMEOUT_MS) -> int:
    """Normalize timeout value to allowed integer milliseconds range."""
    try:
        normalized = int(str(value).strip())
    except (TypeError, ValueError):
        normalized = int(default)
    return max(100, min(_MAX_TIMEOUT_MS, normalized))


def normalize_editor_mode(value: object, *, default: str = "auto") -> str:
    """Normalize editor mode to one of: auto, on, off."""
    raw = str(value).strip().lower()
    if raw in {"auto", "on", "off"}:
        return raw
    return default


def normalize_level(value: object, *, default: str = LT_LEVEL_DEFAULT) -> str:
    """Normalize LanguageTool API level string."""
    raw = str(value).strip().lower()
    if raw in LT_LEVELS:
        return raw
    return default


def validate_server_url(value: object) -> str:
    """Validate and normalize LanguageTool server base URL."""
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("LanguageTool server URL is empty.")
    parsed = urllib.parse.urlsplit(raw)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("LanguageTool server URL must use http or https.")
    if not parsed.netloc:
        raise ValueError("LanguageTool server URL host is missing.")
    hostname = (parsed.hostname or "").strip().lower()
    if parsed.scheme == "http" and hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("Only localhost http:// LanguageTool endpoints are allowed.")
    normalized = urllib.parse.urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path.rstrip("/"),
            "",
            "",
        )
    )
    return normalized


def endpoint_for_server(server_url: str) -> str:
    """Build `/v2/check` endpoint URL for a normalized server URL."""
    base = validate_server_url(server_url)
    return f"{base}{_API_PATH}"


def load_language_map(raw: object) -> dict[str, str]:
    """Load locale->LanguageTool language-code map from JSON/object payload."""
    if isinstance(raw, dict):
        parsed = raw
    else:
        text = str(raw or "").strip()
        if not text:
            return {}
        try:
            candidate = json.loads(text)
        except Exception:
            return {}
        if not isinstance(candidate, dict):
            return {}
        parsed = candidate
    result: dict[str, str] = {}
    for key, value in parsed.items():
        locale = str(key).strip().upper().replace("_", "-")
        lang = str(value).strip()
        if not locale or not lang:
            continue
        result[locale] = lang
    return result


def dump_language_map(value: Mapping[str, str]) -> str:
    """Serialize locale->LanguageTool language map as compact deterministic JSON."""
    normalized: dict[str, str] = {}
    for key in sorted(value):
        locale = str(key).strip().upper().replace("_", "-")
        lang = str(value.get(key) or "").strip()
        if not locale or not lang:
            continue
        normalized[locale] = lang
    return json.dumps(normalized, ensure_ascii=True, separators=(",", ":"))


def draft_language_map(locales: Iterable[str]) -> dict[str, str]:
    """Draft locale->LanguageTool language-code mapping defaults."""
    result: dict[str, str] = dict(_DEFAULT_LANGUAGE_MAP)
    for raw in locales:
        locale = str(raw).strip().upper().replace("_", "-")
        if not locale or locale in result:
            continue
        if "-" in locale:
            base, region = locale.split("-", 1)
            if base and region:
                result[locale] = f"{base.lower()}-{region.upper()}"
                continue
        if len(locale) == 2:
            result[locale] = locale.lower()
            continue
        result[locale] = locale.lower().replace("_", "-")
    return result


def resolve_language_code(locale: object, mapping: Mapping[str, str]) -> str:
    """Resolve LanguageTool language code for project locale."""
    normalized = str(locale or "").strip().upper().replace("_", "-")
    if not normalized:
        return "en-US"
    if normalized in mapping:
        return str(mapping[normalized]).strip() or "en-US"
    drafted = draft_language_map((normalized,))
    return drafted.get(normalized, "en-US")


def _encode_request_payload(*, text: str, language: str, level: str) -> bytes:
    """Encode request payload for LT API form endpoint."""
    payload = urllib.parse.urlencode(
        {
            "language": language,
            "text": text,
            "level": normalize_level(level),
        }
    )
    return payload.encode("utf-8")


def _decode_http_error_body(exc: urllib.error.HTTPError) -> str:
    """Decode HTTP error body for diagnostics/fallback classification."""
    try:
        return exc.read().decode("utf-8", errors="replace")
    except Exception:
        return ""
    finally:
        with contextlib.suppress(Exception):
            exc.close()


def _is_picky_unsupported_error(exc: LTRequestError) -> bool:
    """Return whether HTTP error indicates unsupported picky/level parameter."""
    if exc.code not in {400, 404, 422}:
        return False
    body = (exc.body or "").lower()
    if not body:
        return False
    tokens = (
        "picky",
        "level",
        "unknown parameter",
        "unsupported",
        "invalid value",
    )
    return any(token in body for token in tokens)


def _perform_check_request(
    *,
    endpoint: str,
    language: str,
    text: str,
    level: str,
    timeout_ms: int,
) -> dict[str, Any]:
    """Perform one LanguageTool API check request and parse JSON payload."""
    request = urllib.request.Request(
        url=endpoint,
        data=_encode_request_payload(
            text=text,
            language=language,
            level=level,
        ),
        headers={
            "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
            "Accept": "application/json",
            "User-Agent": "translationzed-py-languagetool-client",
        },
        method="POST",
    )
    timeout_sec = max(0.1, float(timeout_ms) / 1000.0)
    try:
        with urllib.request.urlopen(
            request, timeout=timeout_sec
        ) as response:  # nosec B310
            raw = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        body = _decode_http_error_body(exc)
        raise LTRequestError(
            f"LanguageTool HTTP error ({exc.code}).",
            code=int(exc.code),
            body=body,
        ) from exc
    except urllib.error.URLError as exc:
        raise LTOfflineError(f"LanguageTool endpoint unreachable: {exc}") from exc
    except TimeoutError as exc:
        raise LTOfflineError("LanguageTool request timed out.") from exc

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LTRequestError("LanguageTool response is not valid JSON.") from exc
    if not isinstance(payload, dict):
        raise LTRequestError("LanguageTool response payload must be a JSON object.")
    return payload


def _parse_matches(payload: dict[str, Any]) -> tuple[LanguageToolMatch, ...]:
    """Normalize LanguageTool response matches array."""
    matches_raw = payload.get("matches")
    if not isinstance(matches_raw, list):
        return ()
    out: list[LanguageToolMatch] = []
    for item in matches_raw:
        if not isinstance(item, dict):
            continue
        try:
            offset = int(str(item.get("offset")).strip())
            length = int(str(item.get("length")).strip())
        except (TypeError, ValueError):
            continue
        if offset < 0 or length <= 0:
            continue
        message = str(item.get("message") or "").strip()
        replacements_raw = item.get("replacements")
        replacements: list[str] = []
        if isinstance(replacements_raw, list):
            for replacement in replacements_raw:
                if not isinstance(replacement, dict):
                    continue
                value = str(replacement.get("value") or "").strip()
                if value:
                    replacements.append(value)
        rule_raw = item.get("rule")
        rule_id = ""
        category_id = ""
        issue_type = ""
        if isinstance(rule_raw, dict):
            rule_id = str(rule_raw.get("id") or "").strip()
            category_raw = rule_raw.get("category")
            if isinstance(category_raw, dict):
                category_id = str(category_raw.get("id") or "").strip()
        issue_type_raw = item.get("type")
        if isinstance(issue_type_raw, dict):
            issue_type = str(issue_type_raw.get("typeName") or "").strip().lower()
        out.append(
            LanguageToolMatch(
                offset=offset,
                length=length,
                message=message,
                replacements=tuple(replacements),
                rule_id=rule_id,
                category_id=category_id,
                issue_type=issue_type,
            )
        )
    return tuple(out)


def check_text(
    *,
    server_url: str,
    language: str,
    text: str,
    level: str,
    timeout_ms: int,
) -> LanguageToolCheckResult:
    """Run LanguageTool check with picky fallback behavior."""
    normalized_level = normalize_level(level)
    normalized_timeout = normalize_timeout_ms(timeout_ms)
    try:
        endpoint = endpoint_for_server(server_url)
    except ValueError as exc:
        return LanguageToolCheckResult(
            status=LT_STATUS_ERROR,
            matches=(),
            used_level=normalized_level,
            fallback_used=False,
            warning="",
            error=str(exc),
        )

    def _ok_result(
        *,
        payload: dict[str, Any],
        used_level: str,
        fallback_used: bool,
        warning: str,
    ) -> LanguageToolCheckResult:
        return LanguageToolCheckResult(
            status=LT_STATUS_OK,
            matches=_parse_matches(payload),
            used_level=used_level,
            fallback_used=fallback_used,
            warning=warning,
            error="",
        )

    try:
        payload = _perform_check_request(
            endpoint=endpoint,
            language=language,
            text=text,
            level=normalized_level,
            timeout_ms=normalized_timeout,
        )
        return _ok_result(
            payload=payload,
            used_level=normalized_level,
            fallback_used=False,
            warning="",
        )
    except LTRequestError as exc:
        if normalized_level == LT_LEVEL_PICKY and _is_picky_unsupported_error(exc):
            try:
                payload = _perform_check_request(
                    endpoint=endpoint,
                    language=language,
                    text=text,
                    level=LT_LEVEL_DEFAULT,
                    timeout_ms=normalized_timeout,
                )
            except LTOfflineError as offline_exc:
                return LanguageToolCheckResult(
                    status=LT_STATUS_OFFLINE,
                    matches=(),
                    used_level=LT_LEVEL_DEFAULT,
                    fallback_used=True,
                    warning="",
                    error=str(offline_exc),
                )
            except LTRequestError as fallback_exc:
                return LanguageToolCheckResult(
                    status=LT_STATUS_ERROR,
                    matches=(),
                    used_level=LT_LEVEL_DEFAULT,
                    fallback_used=True,
                    warning="",
                    error=str(fallback_exc),
                )
            return _ok_result(
                payload=payload,
                used_level=LT_LEVEL_DEFAULT,
                fallback_used=True,
                warning="Picky unsupported by server; using default level.",
            )
        return LanguageToolCheckResult(
            status=LT_STATUS_ERROR,
            matches=(),
            used_level=normalized_level,
            fallback_used=False,
            warning="",
            error=str(exc),
        )
    except LTOfflineError as exc:
        return LanguageToolCheckResult(
            status=LT_STATUS_OFFLINE,
            matches=(),
            used_level=normalized_level,
            fallback_used=False,
            warning="",
            error=str(exc),
        )
