"""Pass lifecycle and concurrency-safe use accounting."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import secrets
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

from .const import ACTIVITY_LIMIT, TERMINAL_PASS_LIMIT


class PassStorage(Protocol):
    """Storage interface used by the pass manager."""

    async def async_load(self) -> dict[str, Any] | None:
        """Load stored pass data."""

    async def async_save(self, data: dict[str, Any]) -> None:
        """Persist pass data."""


class PassUnavailableError(Exception):
    """Raised when a pass cannot authorize an action."""

    def __init__(
        self,
        reason: str,
        *,
        valid_from: str | None = None,
        label: str | None = None,
    ) -> None:
        super().__init__(reason)
        self.reason = reason
        self.valid_from = valid_from
        self.label = label


class PassBusyError(Exception):
    """Raised when an action is already in progress for a pass."""


class PassManager:
    """Create, validate, reserve, consume, and revoke guest passes."""

    def __init__(
        self,
        storage: PassStorage,
        *,
        now: Callable[[], datetime] | None = None,
        action: tuple[str, str] | None = None,
    ) -> None:
        self._storage = storage
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._passes: dict[str, dict[str, Any]] = {}
        self._activity: list[dict[str, Any]] = []
        self._reserved: set[str] = set()
        self._lock = asyncio.Lock()
        self._action = list(action) if action is not None else None
        self._closing = False
        self._idle = asyncio.Event()
        self._idle.set()

    async def async_load(self) -> None:
        """Load persisted passes."""
        data = await self._storage.async_load() or {}
        stored = data.get("passes", [])
        if not isinstance(stored, list):
            stored = []
        self._passes = {
            item["pass_id"]: item
            for item in stored
            if isinstance(item, dict) and isinstance(item.get("pass_id"), str)
        }
        activity = data.get("activity", [])
        if not isinstance(activity, list):
            activity = []
        self._activity = [
            item
            for item in activity[-ACTIVITY_LIMIT:]
            if isinstance(item, dict)
            and isinstance(item.get("event_type"), str)
            and isinstance(item.get("occurred_at"), str)
        ]
        if self._action is not None and data.get("action") != self._action:
            # Adopt legacy records once; subsequent target changes revoke them.
            if data.get("action") is not None:
                for record in self._passes.values():
                    if record.get("active"):
                        record["active"] = False
                        self._append_activity_locked("revoked", record)
            await self._async_save_locked()
        await self.async_list_active()
        if (
            sum(not record.get("active") for record in self._passes.values())
            > TERMINAL_PASS_LIMIT
        ):
            await self._async_save_locked()

    async def async_shutdown(self) -> None:
        """Reject new work and drain reserved actions before reloading storage."""
        async with self._lock:
            self._closing = True
        await self._idle.wait()

    def _ensure_open(self) -> None:
        if self._closing:
            raise PassUnavailableError("unavailable")

    async def async_create(
        self,
        *,
        label: str,
        duration_hours: float,
        max_uses: int,
        valid_from: datetime | None = None,
        created_by_user_id: str | None = None,
    ) -> tuple[dict[str, Any], str]:
        """Create a pass and return its safe data plus one-time secret."""
        if duration_hours <= 0:
            raise ValueError("duration_hours must be positive")
        if max_uses < 0:
            raise ValueError("max_uses cannot be negative")

        now = self._as_utc(self._now())
        starts_at = self._as_utc(valid_from) if valid_from is not None else now
        starts_at = max(starts_at, now)
        pass_id = "gp_" + secrets.token_urlsafe(12)
        secret = secrets.token_urlsafe(32)
        record: dict[str, Any] = {
            "pass_id": pass_id,
            "secret_hash": self._hash_secret(secret),
            "label": label.strip() or "Gast",
            "created_at": now.isoformat(),
            "valid_from": starts_at.isoformat(),
            "expires_at": (starts_at + timedelta(hours=duration_hours)).isoformat(),
            "max_uses": max_uses,
            "use_count": 0,
            "active": True,
            "last_used_at": None,
            "created_by_user_id": created_by_user_id,
        }

        async with self._lock:
            self._ensure_open()
            self._passes[pass_id] = record
            self._append_activity_locked("created", record, occurred_at=now)
            await self._async_save_locked()

        return self._safe(record), secret

    async def async_get_valid(self, pass_id: str, secret: str) -> dict[str, Any]:
        """Return safe pass data when the credentials are currently valid."""
        async with self._lock:
            try:
                record = self._validate_locked(pass_id, secret)
            except PassUnavailableError as err:
                await self._async_deactivate_invalid_locked(pass_id, err.reason)
                raise
            return self._safe(record)

    async def async_reserve_use(self, pass_id: str, secret: str) -> dict[str, Any]:
        """Reserve one action slot so concurrent requests cannot exceed limits."""
        async with self._lock:
            try:
                record = self._validate_locked(pass_id, secret)
            except PassUnavailableError as err:
                await self._async_deactivate_invalid_locked(pass_id, err.reason)
                raise
            if pass_id in self._reserved:
                raise PassBusyError

            max_uses = int(record.get("max_uses", 0))
            use_count = int(record.get("use_count", 0))
            if max_uses > 0 and use_count >= max_uses:
                raise PassUnavailableError("exhausted")

            self._reserved.add(pass_id)
            self._idle.clear()
            return self._safe(record)

    async def async_commit_use(self, pass_id: str) -> dict[str, Any]:
        """Commit a reserved use after the configured HA action succeeds."""
        async with self._lock:
            if pass_id not in self._reserved:
                raise RuntimeError("pass use was not reserved")
            record = self._passes[pass_id]
            record["use_count"] = int(record.get("use_count", 0)) + 1
            used_at = self._as_utc(self._now())
            record["last_used_at"] = used_at.isoformat()
            max_uses = int(record.get("max_uses", 0))
            if max_uses > 0 and record["use_count"] >= max_uses:
                record["active"] = False
            self._append_activity_locked("used", record, occurred_at=used_at)
            try:
                await self._async_save_locked()
            finally:
                self._reserved.discard(pass_id)
                if not self._reserved:
                    self._idle.set()
            return self._safe(record)

    async def async_release_use(self, pass_id: str) -> None:
        """Release a reservation after a failed HA action without consuming it."""
        async with self._lock:
            self._reserved.discard(pass_id)
            if not self._reserved:
                self._idle.set()

    async def async_list_active(
        self, *, owner_user_id: str | None = None
    ) -> list[dict[str, Any]]:
        """Return active, unexpired passes without secrets or hashes."""
        changed = False
        async with self._lock:
            self._ensure_open()
            for record in self._passes.values():
                if record.get("active") and self._is_expired(record):
                    record["active"] = False
                    changed = True
            if changed:
                await self._async_save_locked()
            return [
                self._safe(record)
                for record in self._passes.values()
                if record.get("active")
                and (
                    owner_user_id is None
                    or record.get("created_by_user_id") == owner_user_id
                )
            ]

    async def async_list_activity(
        self, *, owner_user_id: str | None = None
    ) -> list[dict[str, Any]]:
        """Return the newest persistent activity records first."""
        async with self._lock:
            return [
                self._safe_activity(item)
                for item in reversed(self._activity)
                if owner_user_id is None
                or item.get("created_by_user_id") == owner_user_id
            ]

    async def async_clear_activity(self) -> int:
        """Clear all persistent activity records and return the removed count."""
        async with self._lock:
            self._ensure_open()
            count = len(self._activity)
            if count:
                self._activity.clear()
                await self._async_save_locked()
            return count

    async def async_revoke(
        self, pass_id: str, *, owner_user_id: str | None = None
    ) -> bool:
        """Revoke one pass."""
        async with self._lock:
            self._ensure_open()
            record = self._passes.get(pass_id)
            if record is None or (
                owner_user_id is not None
                and record.get("created_by_user_id") != owner_user_id
            ):
                return False
            if record.get("active"):
                record["active"] = False
                self._append_activity_locked("revoked", record)
            await self._async_save_locked()
            return True

    async def async_revoke_all(self) -> int:
        """Revoke all active passes."""
        count = 0
        async with self._lock:
            self._ensure_open()
            for record in self._passes.values():
                if record.get("active"):
                    record["active"] = False
                    self._append_activity_locked("revoked", record)
                    count += 1
            if count:
                await self._async_save_locked()
        return count

    async def _async_deactivate_invalid_locked(self, pass_id: str, reason: str) -> None:
        """Persist terminal expiry/exhaustion state discovered on validation."""
        if reason not in {"expired", "exhausted"}:
            return
        record = self._passes.get(pass_id)
        if record is not None and record.get("active"):
            record["active"] = False
            await self._async_save_locked()

    def _validate_locked(self, pass_id: str, secret: str) -> dict[str, Any]:
        self._ensure_open()
        record = self._passes.get(pass_id)
        if record is None:
            raise PassUnavailableError("invalid")
        if not hmac.compare_digest(
            str(record.get("secret_hash", "")), self._hash_secret(secret)
        ):
            raise PassUnavailableError("invalid")
        if not record.get("active", False):
            raise PassUnavailableError("revoked")
        valid_from = self._valid_from(record)
        if valid_from is not None and valid_from > self._as_utc(self._now()):
            raise PassUnavailableError(
                "not_yet_valid",
                valid_from=valid_from.isoformat(),
                label=str(record.get("label", "")),
            )
        if self._is_expired(record):
            raise PassUnavailableError("expired")

        max_uses = int(record.get("max_uses", 0))
        if max_uses > 0 and int(record.get("use_count", 0)) >= max_uses:
            raise PassUnavailableError("exhausted")
        return record

    def _is_expired(self, record: dict[str, Any]) -> bool:
        expires_at = self._record_datetime(record, "expires_at")
        if expires_at is None:
            return True
        return expires_at <= self._as_utc(self._now())

    def _valid_from(self, record: dict[str, Any]) -> datetime | None:
        """Return the scheduled start, treating legacy passes as immediately valid."""
        return self._record_datetime(record, "valid_from")

    @classmethod
    def _record_datetime(cls, record: dict[str, Any], key: str) -> datetime | None:
        try:
            value = datetime.fromisoformat(str(record[key]))
        except (KeyError, TypeError, ValueError):
            return None
        return cls._as_utc(value)

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    async def _async_save_locked(self) -> None:
        # Keep a bounded recent terminal history; never evict an in-flight use.
        terminal = [
            record
            for record in self._passes.values()
            if not record.get("active") and record["pass_id"] not in self._reserved
        ]
        terminal.sort(key=lambda record: str(record.get("created_at", "")))
        for record in terminal[:-TERMINAL_PASS_LIMIT]:
            self._passes.pop(record["pass_id"], None)
        await self._storage.async_save(
            {
                "passes": list(self._passes.values()),
                "activity": self._activity,
                "action": self._action,
            }
        )

    def _append_activity_locked(
        self,
        event_type: str,
        record: dict[str, Any],
        *,
        occurred_at: datetime | None = None,
    ) -> None:
        """Append a privacy-conscious activity record while holding the lock."""
        timestamp = self._as_utc(occurred_at or self._now()).isoformat()
        self._activity.append(
            {
                "event_id": "ga_" + secrets.token_urlsafe(8),
                "event_type": event_type,
                "occurred_at": timestamp,
                "pass_id": str(record.get("pass_id", "")),
                "label": str(record.get("label", "Gast")),
                "use_count": int(record.get("use_count", 0)),
                "max_uses": int(record.get("max_uses", 0)),
                "created_by_user_id": record.get("created_by_user_id"),
            }
        )
        if len(self._activity) > ACTIVITY_LIMIT:
            del self._activity[:-ACTIVITY_LIMIT]

    @staticmethod
    def _hash_secret(secret: str) -> str:
        return hashlib.sha256(secret.encode("utf-8")).hexdigest()

    @staticmethod
    def _safe(record: dict[str, Any]) -> dict[str, Any]:
        return {
            key: value
            for key, value in record.items()
            if key not in {"secret_hash", "created_by_user_id"}
        }

    @staticmethod
    def _safe_activity(record: dict[str, Any]) -> dict[str, Any]:
        return {
            key: value for key, value in record.items() if key != "created_by_user_id"
        }
