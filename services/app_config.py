from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from ipaddress import ip_network
from os import environ
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Sequence, Tuple

import tomlkit

from packaging.version import Version
from packaging.version import parse

DEFAULT_BATCH_SIZE = 20
DEFAULT_MAX_RANK = 1000
DEFAULT_TEMP_LINK_ENABLED = True
DEFAULT_TEMP_LINK_TTL_HOURS = 24
DEFAULT_TEMP_LINK_MAX_CUSTOM_HOURS = 24 * 30
DEFAULT_TEMP_LINK_PURGE_INTERVAL_SECONDS = 600
DEFAULT_TRUSTED_PROXY_CIDRS = ("127.0.0.1/32", "::1/128")

CONFIG_ENV_VAR = "STARTPAGE_CONFIG_PATH"
ENV_BATCH = "STARTPAGE_BATCH_SIZE"
ENV_MAX_RANK = "STARTPAGE_MAX_RANK"
ENV_TEMP_ENABLED = "STARTPAGE_TEMP_LINKS_ENABLED"
ENV_TEMP_DEFAULT = "STARTPAGE_TEMP_LINK_DEFAULT_TTL_HOURS"
ENV_TEMP_MAX = "STARTPAGE_TEMP_LINK_MAX_CUSTOM_HOURS"
ENV_TEMP_PURGE = "STARTPAGE_TEMP_LINK_PURGE_INTERVAL_SECONDS"
ENV_TRUSTED_PROXY_CIDRS = "STARTPAGE_TRUSTED_PROXY_CIDRS"

_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.toml"
_CONFIG_PATH = Path(environ.get(CONFIG_ENV_VAR, _DEFAULT_CONFIG_PATH))
_RUNTIME_CONFIG: Optional["RuntimeConfig"] = None


class AppConfig:
    """
    Class for keeping track of the application configuration.
    """

    def __init__(self, app_version: str, db_version: Version):
        """
        Initialize the configuration.
        """
        self.app_version = parse(app_version)
        self.db_version = db_version


@dataclass(frozen=True)
class FrecencyConfig:
    batch_size: int = DEFAULT_BATCH_SIZE
    max_rank: int = DEFAULT_MAX_RANK


@dataclass(frozen=True)
class TempLinkConfig:
    enabled: bool = DEFAULT_TEMP_LINK_ENABLED
    default_ttl_hours: int = DEFAULT_TEMP_LINK_TTL_HOURS
    max_custom_hours: int = DEFAULT_TEMP_LINK_MAX_CUSTOM_HOURS
    purge_interval_seconds: int = DEFAULT_TEMP_LINK_PURGE_INTERVAL_SECONDS


@dataclass(frozen=True)
class MetricsConfig:
    trusted_proxy_cidrs: Tuple[str, ...] = DEFAULT_TRUSTED_PROXY_CIDRS


@dataclass(frozen=True)
class RuntimeConfig:
    frecency: FrecencyConfig = field(default_factory=FrecencyConfig)
    temp_links: TempLinkConfig = field(default_factory=TempLinkConfig)
    metrics: MetricsConfig = field(default_factory=MetricsConfig)

    def as_dict(self) -> Dict[str, Any]:
        """Return a dict representation used by template/context builders."""
        return asdict(self)


def get_config_path() -> Path:
    return _CONFIG_PATH


def ensure_config_file() -> Path:
    """Write the current config to disk if no file exists yet."""
    path = get_config_path()
    if not path.exists():
        persist_runtime_config(get_runtime_config())
    return path


def get_runtime_config() -> RuntimeConfig:
    global _RUNTIME_CONFIG
    if _RUNTIME_CONFIG is None:
        _RUNTIME_CONFIG = _load_runtime_config(get_config_path())
    return _RUNTIME_CONFIG


def reload_runtime_config() -> RuntimeConfig:
    """Force a reload from disk and environment variables."""
    global _RUNTIME_CONFIG
    _RUNTIME_CONFIG = _load_runtime_config(get_config_path())
    return _RUNTIME_CONFIG


def persist_runtime_config(config: RuntimeConfig, *, path: Optional[Path] = None) -> RuntimeConfig:
    """Write the provided config to disk and update the cached runtime copy."""
    output_path = path or get_config_path()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = tomlkit.document()
    doc["frecency"] = {
        "batch_size": config.frecency.batch_size,
        "max_rank": config.frecency.max_rank,
    }
    doc["temp_links"] = {
        "enabled": config.temp_links.enabled,
        "default_ttl_hours": config.temp_links.default_ttl_hours,
        "max_custom_hours": config.temp_links.max_custom_hours,
        "purge_interval_seconds": config.temp_links.purge_interval_seconds,
    }
    doc["metrics"] = {
        "trusted_proxy_cidrs": list(config.metrics.trusted_proxy_cidrs),
    }
    with output_path.open("w", encoding="utf-8") as handle:
        handle.write(tomlkit.dumps(doc))
    global _RUNTIME_CONFIG
    _RUNTIME_CONFIG = config
    return config


def update_frecency_settings(batch_size: int, max_rank: int) -> RuntimeConfig:
    """Replace frecency settings and persist them."""
    safe_batch = max(1, batch_size)
    safe_rank = max(1, max_rank)
    config = get_runtime_config()
    updated = replace(
        config,
        frecency=FrecencyConfig(batch_size=safe_batch, max_rank=safe_rank),
    )
    return persist_runtime_config(updated)


def update_temp_link_settings(
    enabled: bool,
    default_ttl_hours: int,
    max_custom_hours: int,
    purge_interval_seconds: int,
) -> RuntimeConfig:
    """Replace temp-link settings and persist them."""
    safe_default = max(1, default_ttl_hours)
    safe_max = max(safe_default, max_custom_hours)
    safe_max = min(DEFAULT_TEMP_LINK_MAX_CUSTOM_HOURS, safe_max)
    safe_default = min(safe_max, safe_default)
    safe_purge = max(60, purge_interval_seconds)
    config = get_runtime_config()
    updated = replace(
        config,
        temp_links=TempLinkConfig(
            enabled=enabled,
            default_ttl_hours=safe_default,
            max_custom_hours=safe_max,
            purge_interval_seconds=safe_purge,
        ),
    )
    return persist_runtime_config(updated)


def normalize_trusted_proxy_cidrs(entries: Sequence[str]) -> Tuple[str, ...]:
    return _normalize_trusted_proxy_cidrs(entries)


def update_metrics_settings(trusted_proxy_cidrs: Sequence[str]) -> RuntimeConfig:
    """Replace metrics settings and persist them."""
    config = get_runtime_config()
    updated = replace(
        config,
        metrics=MetricsConfig(trusted_proxy_cidrs=normalize_trusted_proxy_cidrs(trusted_proxy_cidrs)),
    )
    return persist_runtime_config(updated)


def _load_runtime_config(path: Path) -> RuntimeConfig:
    if path.exists():
        with path.open("r", encoding="utf-8") as handle:
            raw = tomlkit.parse(handle.read())
    else:
        raw = {}

    frecency = _load_frecency_config(raw.get("frecency", {}))
    temp_links = _load_temp_link_config(raw.get("temp_links", {}))
    metrics = _load_metrics_config(raw.get("metrics", {}))
    return RuntimeConfig(frecency=frecency, temp_links=temp_links, metrics=metrics)


def _load_frecency_config(data: Dict[str, Any]) -> FrecencyConfig:
    batch = _coerce_int(data.get("batch_size"), DEFAULT_BATCH_SIZE, minimum=1)
    max_rank = _coerce_int(data.get("max_rank"), DEFAULT_MAX_RANK, minimum=1)
    env_batch = _env_int(ENV_BATCH)
    env_rank = _env_int(ENV_MAX_RANK)
    if env_batch is not None:
        batch = _coerce_int(env_batch, batch, minimum=1)
    if env_rank is not None:
        max_rank = _coerce_int(env_rank, max_rank, minimum=1)
    return FrecencyConfig(batch_size=batch, max_rank=max_rank)


def _load_temp_link_config(data: Dict[str, Any]) -> TempLinkConfig:
    enabled = _coerce_bool(data.get("enabled"), DEFAULT_TEMP_LINK_ENABLED)
    default_hours = _coerce_int(
        data.get("default_ttl_hours"), DEFAULT_TEMP_LINK_TTL_HOURS, minimum=1
    )
    max_custom = _coerce_int(
        data.get("max_custom_hours"),
        DEFAULT_TEMP_LINK_MAX_CUSTOM_HOURS,
        minimum=default_hours,
        maximum=DEFAULT_TEMP_LINK_MAX_CUSTOM_HOURS,
    )
    purge_seconds = _coerce_int(
        data.get("purge_interval_seconds"),
        DEFAULT_TEMP_LINK_PURGE_INTERVAL_SECONDS,
        minimum=60,
    )
    env_enabled = _env_bool(ENV_TEMP_ENABLED)
    env_default = _env_int(ENV_TEMP_DEFAULT)
    env_max = _env_int(ENV_TEMP_MAX)
    env_purge = _env_int(ENV_TEMP_PURGE)

    if env_enabled is not None:
        enabled = env_enabled
    if env_default is not None:
        default_hours = _coerce_int(env_default, default_hours, minimum=1)
    if env_max is not None:
        max_custom = _coerce_int(
            env_max,
            max_custom,
            minimum=default_hours,
            maximum=DEFAULT_TEMP_LINK_MAX_CUSTOM_HOURS,
        )
    if env_purge is not None:
        purge_seconds = _coerce_int(env_purge, purge_seconds, minimum=60)

    max_custom = max(default_hours, min(DEFAULT_TEMP_LINK_MAX_CUSTOM_HOURS, max_custom))
    default_hours = min(max_custom, default_hours)
    return TempLinkConfig(
        enabled=enabled,
        default_ttl_hours=default_hours,
        max_custom_hours=max_custom,
        purge_interval_seconds=purge_seconds,
    )


def _load_metrics_config(data: Dict[str, Any]) -> MetricsConfig:
    configured = _coerce_str_sequence(data.get("trusted_proxy_cidrs"))
    if configured is None:
        trusted = DEFAULT_TRUSTED_PROXY_CIDRS
    else:
        trusted = normalize_trusted_proxy_cidrs(configured)

    env_value = environ.get(ENV_TRUSTED_PROXY_CIDRS)
    if env_value is not None:
        env_tokens = [token.strip() for token in env_value.split(",") if token.strip()]
        if env_tokens:
            trusted = normalize_trusted_proxy_cidrs(env_tokens)
        else:
            trusted = DEFAULT_TRUSTED_PROXY_CIDRS

    return MetricsConfig(trusted_proxy_cidrs=trusted)


def _coerce_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _coerce_int(
    value: Any,
    default: int,
    *,
    minimum: Optional[int] = None,
    maximum: Optional[int] = None,
) -> int:
    if value is None:
        result = default
    else:
        try:
            result = int(value)
        except (TypeError, ValueError):
            result = default
    if minimum is not None:
        result = max(minimum, result)
    if maximum is not None:
        result = min(maximum, result)
    return result


def _env_int(name: str) -> Optional[int]:
    raw = environ.get(name)
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _env_bool(name: str) -> Optional[bool]:
    raw = environ.get(name)
    if raw is None:
        return None
    normalized = str(raw).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return None


def _coerce_str_sequence(value: Any) -> Optional[Sequence[str]]:
    if value is None:
        return None
    if isinstance(value, str):
        tokens = [token.strip() for token in value.replace("\n", ",").split(",")]
        return [token for token in tokens if token]
    if isinstance(value, Iterable):
        result = []
        for item in value:
            token = str(item).strip()
            if token:
                result.append(token)
        return result
    return None


def _normalize_trusted_proxy_cidrs(entries: Sequence[str]) -> Tuple[str, ...]:
    normalized: list[str] = []
    seen = set()
    for entry in entries:
        token = str(entry).strip()
        if not token:
            continue
        try:
            value = str(ip_network(token, strict=False))
        except ValueError as exc:
            raise ValueError(f"Invalid trusted proxy CIDR/IP: {token}") from exc
        if value not in seen:
            seen.add(value)
            normalized.append(value)
    return tuple(normalized)
