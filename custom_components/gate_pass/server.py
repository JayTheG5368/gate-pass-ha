"""Standalone public guest server for Gate Pass HA."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from aiohttp import web

from homeassistant.core import HomeAssistant

from .const import (
    CONF_ACCESS_NAME,
    CONF_ACTION_LABEL,
    CONF_ENTITY_ID,
    CONF_PUBLIC_BASE_URL,
    CONF_SERVICE,
    EVENT_PASS_USED,
)
from .notifications import async_send_notification
from .pass_manager import PassBusyError, PassManager, PassUnavailableError

_LOGGER = logging.getLogger(__name__)

BRAND_ICON_PATH = Path(__file__).parent / "brand" / "icon.png"

PAGE_HEADERS = {
    "Cache-Control": "no-store",
    "Content-Security-Policy": (
        "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
        "connect-src 'self'; img-src 'self' data:; base-uri 'none'; "
        "frame-ancestors 'none'; form-action 'none'"
    ),
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Permissions-Policy": (
        "camera=(), microphone=(), geolocation=(), payment=(), usb=()"
    ),
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-Robots-Tag": "noindex, nofollow, noarchive",
}
API_HEADERS = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}
ASSET_HEADERS = {
    "Cache-Control": "public, max-age=86400",
    "Cross-Origin-Resource-Policy": "same-origin",
    "X-Content-Type-Options": "nosniff",
}

GUEST_PAGE_HTML = """<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <meta name="color-scheme" content="light dark">
  <title>Gate Pass</title>
  <style>
    :root { color-scheme: light dark; --bg:#f4f6f7; --surface:#fff; --text:#15201c;
      --muted:#5f6b66; --line:#d7ddda; --action:#176b4d; --action-text:#fff;
      --warn:#a43b2e; --success:#18744f; }
    @media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { --bg:#101513; --surface:#19201d;
      --text:#edf3f0; --muted:#a9b5b0; --line:#34413b; --action:#45a77f;
      --action-text:#07130e; --warn:#ff8a78; --success:#68d5a7; } }
    :root[data-theme="dark"] { --bg:#101513; --surface:#19201d;
      --text:#edf3f0; --muted:#a9b5b0; --line:#34413b; --action:#45a77f;
      --action-text:#07130e; --warn:#ff8a78; --success:#68d5a7; }
    * { box-sizing:border-box; letter-spacing:0; }
    body { margin:0; min-height:100dvh; background:var(--bg); color:var(--text);
      font:16px/1.45 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }
    main { width:min(100%,520px); min-height:100dvh; margin:0 auto; padding:max(24px,env(safe-area-inset-top))
      20px max(24px,env(safe-area-inset-bottom)); display:flex; flex-direction:column; }
    header { display:flex; align-items:center; gap:12px; padding-bottom:24px; border-bottom:1px solid var(--line); }
    .mark { width:44px; height:44px; flex:0 0 auto; }
    .mark img { display:block; width:100%; height:100%; object-fit:contain; }
    h1 { margin:0; font-size:1.2rem; font-weight:650; }
    .eyebrow { margin:2px 0 0; color:var(--muted); font-size:.82rem; }
    #content { flex:1; display:flex; flex-direction:column; justify-content:center; padding:32px 0; }
    .pass-label { margin:0 0 8px; color:var(--muted); font-size:.9rem; }
    h2 { margin:0 0 10px; font-size:clamp(1.8rem,8vw,2.5rem); line-height:1.08; }
    .meta { display:flex; gap:8px 16px; flex-wrap:wrap; margin:0 0 28px; color:var(--muted); font-size:.9rem; }
    button { width:100%; min-height:64px; border:0; border-radius:8px; padding:14px 18px;
      background:var(--action); color:var(--action-text); font:650 1.05rem/1.2 inherit; cursor:pointer; }
    button:disabled { opacity:.55; cursor:wait; }
    .status { min-height:28px; margin-top:18px; font-weight:600; }
    .status.error { color:var(--warn); } .status.success { color:var(--success); }
    footer { color:var(--muted); font-size:.78rem; padding-top:18px; border-top:1px solid var(--line); }
    dialog { width:min(calc(100% - 32px),440px); border:1px solid var(--line); border-radius:8px;
      padding:22px; background:var(--surface); color:var(--text); }
    dialog::backdrop { background:rgba(0,0,0,.55); }
    dialog h3 { margin:0 0 8px; font-size:1.25rem; }
    dialog p { margin:0 0 20px; color:var(--muted); }
    .dialog-actions { display:grid; grid-template-columns:1fr 1fr; gap:10px; }
    .secondary { background:transparent; color:var(--text); border:1px solid var(--line); }
    .theme-toggle { position:fixed; z-index:10; right:max(16px,env(safe-area-inset-right));
      bottom:max(16px,env(safe-area-inset-bottom)); width:48px; min-height:48px; padding:0;
      display:grid; place-items:center; border:1px solid var(--line); border-radius:50%;
      background:var(--surface); color:var(--text); font-size:1.35rem; line-height:1;
      box-shadow:0 4px 16px rgba(0,0,0,.18); }
    .theme-toggle:focus-visible { outline:3px solid var(--action); outline-offset:3px; }
    @media (max-width:380px) { .dialog-actions { grid-template-columns:1fr; } }
  </style>
</head>
<body>
<main>
  <header><div class="mark" aria-hidden="true"><img src="/gate-pass/assets/icon.png" alt="" width="44" height="44"></div><div><h1>Gate Pass</h1><p class="eyebrow" id="accessName">Zugang wird geladen</p></div></header>
  <section id="content" aria-live="polite">
    <p class="pass-label" id="passLabel"></p>
    <h2 id="actionLabel">Zugang</h2>
    <div class="meta"><span id="expires"></span><span id="uses"></span></div>
    <button id="openButton" type="button" disabled>Bitte warten</button>
    <div id="status" class="status" role="status"></div>
  </section>
  <footer>Zeitlich begrenzter Zugang</footer>
</main>
<button class="theme-toggle" id="themeToggle" type="button" role="switch" aria-checked="false" aria-label="Dunklen Modus aktivieren" title="Dunklen Modus aktivieren">&#x263E;</button>
<dialog id="confirmDialog">
  <h3 id="confirmTitle">Aktion bestätigen</h3>
  <p>Diese Aktion wird sofort ausgeführt.</p>
  <div class="dialog-actions"><button class="secondary" id="cancelButton" type="button">Abbrechen</button><button id="confirmButton" type="button">Jetzt ausführen</button></div>
</dialog>
<script>
(() => {
  const themeMedia = window.matchMedia('(prefers-color-scheme: dark)');
  const themeToggle = document.getElementById('themeToggle');
  let manualTheme = null;

  function applyTheme(theme) {
    const dark = theme === 'dark';
    document.documentElement.dataset.theme = theme;
    themeToggle.textContent = dark ? '\u2600' : '\u263e';
    themeToggle.setAttribute('aria-checked', String(dark));
    const label = dark ? 'Hellen Modus aktivieren' : 'Dunklen Modus aktivieren';
    themeToggle.setAttribute('aria-label', label);
    themeToggle.title = label;
  }

  function applySystemTheme() {
    applyTheme(themeMedia.matches ? 'dark' : 'light');
  }

  themeToggle.addEventListener('click', () => {
    const dark = document.documentElement.dataset.theme === 'dark';
    manualTheme = dark ? 'light' : 'dark';
    applyTheme(manualTheme);
  });
  themeMedia.addEventListener('change', () => {
    if (manualTheme === null) applySystemTheme();
  });
  applySystemTheme();

  const parts = location.pathname.split('/').filter(Boolean);
  const scoped = parts.length >= 5;
  const entryId = scoped ? parts[2] : null;
  const passId = scoped ? parts[3] : parts[2];
  const secret = scoped ? parts[4] : parts[3];
  const api = '/gate-pass/api/' + (entryId ? encodeURIComponent(entryId) + '/' : '')
    + encodeURIComponent(passId) + '/' + encodeURIComponent(secret);
  const button = document.getElementById('openButton');
  const dialog = document.getElementById('confirmDialog');
  const status = document.getElementById('status');
  let actionLabel = 'Zugang ausführen';

  function setStatus(message, kind) {
    status.textContent = message;
    status.className = 'status' + (kind ? ' ' + kind : '');
  }

  async function load() {
    try {
      const response = await fetch(api + '/status', { cache: 'no-store' });
      const data = await response.json();
      if (response.status === 425 && data.valid_from) {
        actionLabel = data.action_label;
        document.getElementById('accessName').textContent = data.access_name;
        document.getElementById('passLabel').textContent = data.label;
        document.getElementById('actionLabel').textContent = data.action_label;
        button.textContent = 'Noch nicht aktiv';
        setStatus('Gültig ab ' + new Date(data.valid_from).toLocaleString(), '');
        return;
      }
      if (!response.ok) throw new Error('invalid');
      actionLabel = data.action_label;
      document.getElementById('accessName').textContent = data.access_name;
      document.getElementById('passLabel').textContent = data.label;
      document.getElementById('actionLabel').textContent = data.action_label;
      document.getElementById('confirmTitle').textContent = data.action_label + '?';
      document.getElementById('confirmButton').textContent = data.action_label;
      document.getElementById('expires').textContent = 'Gültig bis ' + new Date(data.expires_at).toLocaleString();
      document.getElementById('uses').textContent = data.remaining_uses === null ? 'Unbegrenzt nutzbar' : data.remaining_uses + ' Nutzung(en)';
      button.textContent = data.action_label;
      button.disabled = false;
    } catch (_) {
      button.textContent = 'Zugang nicht verfuegbar';
      setStatus('Der Link ist ungültig, abgelaufen oder bereits verwendet.', 'error');
    }
  }

  button.addEventListener('click', () => dialog.showModal());
  document.getElementById('cancelButton').addEventListener('click', () => dialog.close());
  document.getElementById('confirmButton').addEventListener('click', async () => {
    dialog.close();
    button.disabled = true;
    button.textContent = 'Wird ausgeführt ...';
    setStatus('', '');
    try {
      const response = await fetch(api + '/open', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}'
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Aktion fehlgeschlagen');
      button.textContent = 'Erfolgreich';
      setStatus(actionLabel + ' wurde ausgeführt.', 'success');
    } catch (error) {
      button.disabled = false;
      button.textContent = actionLabel;
      setStatus(error.message || 'Aktion fehlgeschlagen.', 'error');
    }
  });
  load();
})();
</script>
</body>
</html>"""

INVALID_PAGE_HTML = """<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Gate Pass</title></head><body><main><h1>Zugang nicht verfügbar</h1><p>Der Link ist ungültig, abgelaufen oder bereits verwendet.</p></main></body></html>"""


@dataclass
class GuestAccessPoint:
    """One action and pass store exposed by a shared guest server."""

    entry_id: str
    manager: PassManager
    config: dict[str, Any]


class GuestServer:
    """Serve one or more access points on a shared local port."""

    def __init__(self, hass: HomeAssistant, port: int) -> None:
        self.hass = hass
        self.port = port
        self._access_points: dict[str, GuestAccessPoint] = {}
        self._legacy_entry_id: str | None = None
        self._runner: web.AppRunner | None = None

    def register(
        self,
        entry_id: str,
        manager: PassManager,
        config: dict[str, Any],
        *,
        legacy: bool = False,
    ) -> None:
        """Register an access point before or after the server starts."""
        self._access_points[entry_id] = GuestAccessPoint(entry_id, manager, config)
        if legacy:
            self._legacy_entry_id = entry_id

    def unregister(self, entry_id: str) -> None:
        """Remove an access point from this server."""
        self._access_points.pop(entry_id, None)
        if self._legacy_entry_id == entry_id:
            self._legacy_entry_id = None

    @property
    def empty(self) -> bool:
        """Return whether no access points remain."""
        return not self._access_points

    async def async_start(self) -> None:
        """Start the standalone aiohttp server."""
        app = web.Application(client_max_size=16 * 1024)
        app.router.add_get("/gate-pass/assets/icon.png", self._handle_brand_icon)
        app.router.add_get(
            "/gate-pass/guest/{entry_id}/{pass_id}/{secret}", self._handle_page
        )
        app.router.add_get(
            "/gate-pass/api/{entry_id}/{pass_id}/{secret}/status",
            self._handle_status,
        )
        app.router.add_post(
            "/gate-pass/api/{entry_id}/{pass_id}/{secret}/open",
            self._handle_open,
        )
        # Preserve links created by the pre-0.4 single-access-point version.
        app.router.add_get("/gate-pass/guest/{pass_id}/{secret}", self._handle_page)
        app.router.add_get(
            "/gate-pass/api/{pass_id}/{secret}/status", self._handle_status
        )
        app.router.add_post("/gate-pass/api/{pass_id}/{secret}/open", self._handle_open)
        self._runner = web.AppRunner(app, access_log=None)
        await self._runner.setup()
        # Reverse proxies must be able to reach this dedicated guest port.
        site = web.TCPSite(self._runner, "0.0.0.0", self.port)  # nosec B104
        await site.start()
        _LOGGER.info("Gate Pass guest server listening on port %d", self.port)

    async def _handle_brand_icon(self, _request: web.Request) -> web.FileResponse:
        """Serve the bundled brand icon without exposing filesystem paths."""
        return web.FileResponse(BRAND_ICON_PATH, headers=ASSET_HEADERS)

    async def async_stop(self) -> None:
        """Stop the guest server."""
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None

    def build_guest_url(self, entry_id: str, pass_id: str, secret: str) -> str:
        """Build a public guest URL from one-time credentials."""
        target = self._access_points[entry_id]
        external_url = self._build_external_url(target.config)
        return f"{external_url}/gate-pass/guest/{entry_id}/{pass_id}/{secret}"

    def _build_external_url(self, config: dict[str, Any]) -> str:
        public = str(config.get(CONF_PUBLIC_BASE_URL, "")).strip().rstrip("/")
        if public:
            return public
        host = self._derive_host()
        return f"http://{host}:{self.port}"

    def _derive_host(self) -> str:
        for candidate in (self.hass.config.internal_url, self.hass.config.external_url):
            if not candidate:
                continue
            try:
                if hostname := urlsplit(candidate).hostname:
                    return hostname
            except ValueError:
                continue
        return "homeassistant.local"

    def _resolve_access_point(self, request: web.Request) -> GuestAccessPoint | None:
        entry_id = request.match_info.get("entry_id") or self._legacy_entry_id
        if entry_id is None and len(self._access_points) == 1:
            entry_id = next(iter(self._access_points))
        return self._access_points.get(entry_id) if entry_id else None

    async def _handle_page(self, request: web.Request) -> web.Response:
        target = self._resolve_access_point(request)
        if target is None:
            return web.Response(
                text=INVALID_PAGE_HTML,
                content_type="text/html",
                status=404,
                headers=PAGE_HEADERS,
            )
        try:
            await target.manager.async_get_valid(
                request.match_info["pass_id"], request.match_info["secret"]
            )
        except PassUnavailableError as err:
            if err.reason == "not_yet_valid":
                return web.Response(
                    text=GUEST_PAGE_HTML,
                    content_type="text/html",
                    headers=PAGE_HEADERS,
                )
            return web.Response(
                text=INVALID_PAGE_HTML,
                content_type="text/html",
                status=401,
                headers=PAGE_HEADERS,
            )
        return web.Response(
            text=GUEST_PAGE_HTML, content_type="text/html", headers=PAGE_HEADERS
        )

    async def _handle_status(self, request: web.Request) -> web.Response:
        target = self._resolve_access_point(request)
        if target is None:
            return web.json_response(
                {"error": "Access point not found"}, status=404, headers=API_HEADERS
            )
        try:
            guest_pass = await target.manager.async_get_valid(
                request.match_info["pass_id"], request.match_info["secret"]
            )
        except PassUnavailableError as err:
            if err.reason == "not_yet_valid":
                return web.json_response(
                    {
                        "error": err.reason,
                        "valid_from": err.valid_from,
                        "access_name": target.config[CONF_ACCESS_NAME],
                        "action_label": target.config[CONF_ACTION_LABEL],
                        "label": err.label,
                    },
                    status=425,
                    headers=API_HEADERS,
                )
            return web.json_response(
                {"error": "Pass is invalid or expired"},
                status=401,
                headers=API_HEADERS,
            )
        max_uses = int(guest_pass["max_uses"])
        remaining = (
            None if max_uses == 0 else max(0, max_uses - int(guest_pass["use_count"]))
        )
        return web.json_response(
            {
                "access_name": target.config[CONF_ACCESS_NAME],
                "action_label": target.config[CONF_ACTION_LABEL],
                "label": guest_pass["label"],
                "valid_from": guest_pass.get("valid_from"),
                "expires_at": guest_pass["expires_at"],
                "remaining_uses": remaining,
            },
            headers=API_HEADERS,
        )

    async def _handle_open(self, request: web.Request) -> web.Response:
        target = self._resolve_access_point(request)
        if target is None:
            return web.json_response(
                {"error": "Access point not found"}, status=404, headers=API_HEADERS
            )
        if not self._check_browser_origin(request):
            return web.json_response(
                {"error": "Cross-site request rejected"},
                status=403,
                headers=API_HEADERS,
            )
        content_type = request.headers.get("Content-Type", "").split(";")[0].strip()
        if content_type.lower() != "application/json":
            return web.json_response(
                {"error": "Content-Type must be application/json"},
                status=415,
                headers=API_HEADERS,
            )

        pass_id = request.match_info["pass_id"]
        secret = request.match_info["secret"]
        try:
            body = await request.json()
        except ValueError:
            return web.json_response(
                {"error": "Invalid JSON"}, status=400, headers=API_HEADERS
            )
        if not isinstance(body, dict):
            return web.json_response(
                {"error": "JSON body must be an object"},
                status=400,
                headers=API_HEADERS,
            )

        try:
            guest_pass = await target.manager.async_reserve_use(pass_id, secret)
        except PassBusyError:
            return web.json_response(
                {"error": "Action already in progress"},
                status=409,
                headers=API_HEADERS,
            )
        except PassUnavailableError as err:
            if err.reason == "not_yet_valid":
                return web.json_response(
                    {"error": "Pass is not active yet", "valid_from": err.valid_from},
                    status=425,
                    headers=API_HEADERS,
                )
            return web.json_response(
                {"error": "Pass is invalid, expired, or exhausted"},
                status=401,
                headers=API_HEADERS,
            )

        domain, _, service = str(target.config[CONF_SERVICE]).partition(".")
        try:
            if not self.hass.services.has_service(domain, service):
                raise RuntimeError(
                    f"Home Assistant service {domain}.{service} is unavailable"
                )
            await self.hass.services.async_call(
                domain,
                service,
                {"entity_id": target.config[CONF_ENTITY_ID]},
                blocking=True,
            )
        except Exception:
            await target.manager.async_release_use(pass_id)
            _LOGGER.exception("Gate Pass action failed")
            return web.json_response(
                {"error": "Home Assistant action failed"},
                status=502,
                headers=API_HEADERS,
            )

        committed = await target.manager.async_commit_use(pass_id)
        self.hass.bus.async_fire(
            EVENT_PASS_USED,
            {
                "pass_id": pass_id,
                "label": guest_pass["label"],
                "use_count": committed["use_count"],
                "config_entry_id": target.entry_id,
                "access_name": target.config[CONF_ACCESS_NAME],
            },
        )
        await async_send_notification(
            self.hass, target.config, "used", label=guest_pass["label"]
        )
        return web.json_response({"success": True}, headers=API_HEADERS)

    @staticmethod
    def _check_browser_origin(request: web.Request) -> bool:
        site = request.headers.get("Sec-Fetch-Site", "").lower()
        if site and site not in {"same-origin", "same-site", "none"}:
            return False
        origin = request.headers.get("Origin")
        if not origin:
            return True
        try:
            parsed_origin = urlsplit(origin)
            parsed_host = urlsplit(f"//{request.headers.get('Host', '').strip()}")
        except ValueError:
            return False
        origin_host = parsed_origin.hostname
        host = parsed_host.hostname
        if (
            parsed_origin.scheme.lower() not in {"http", "https"}
            or not origin_host
            or parsed_origin.username is not None
            or parsed_origin.password is not None
            or parsed_origin.path not in {"", "/"}
            or parsed_origin.query
            or parsed_origin.fragment
            or not host
        ):
            return False
        return origin_host.lower() == host.lower()
