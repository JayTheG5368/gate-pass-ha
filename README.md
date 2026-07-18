<p align="center">
  <img src="custom_components/gate_pass/brand/icon@2x.png" width="144" alt="Gate Pass HA logo">
</p>

# Gate Pass HA

[![Release](https://img.shields.io/github/v/release/JayTheG5368/gate-pass-ha?display_name=tag&sort=semver)](https://github.com/JayTheG5368/gate-pass-ha/releases)
[![CI](https://github.com/JayTheG5368/gate-pass-ha/actions/workflows/ci.yml/badge.svg)](https://github.com/JayTheG5368/gate-pass-ha/actions/workflows/ci.yml)
[![HACS](https://github.com/JayTheG5368/gate-pass-ha/actions/workflows/validate.yml/badge.svg)](https://github.com/JayTheG5368/gate-pass-ha/actions/workflows/validate.yml)
[![License](https://img.shields.io/github/license/JayTheG5368/gate-pass-ha)](LICENSE)

Gate Pass HA creates temporary public links for one preconfigured Home Assistant
action. It is designed for gates, garage doors, entry doors, and similar access
points without exposing general Home Assistant controls to guests.

> [!IMPORTANT]
> Gate Pass HA is beta software that can control physical access. Test every
> update locally before relying on it and read the [security guidance](SECURITY.md).

## Features

- One fixed server-side Home Assistant action per installation
- Temporary guest links with expiry and optional use limits
- Immediate or scheduled activation
- QR code and link generation in a Lovelace card
- Mobile-friendly validity and use selectors
- Individual and bulk revocation with confirmation
- Persistent activity history for creation, successful use, and revocation
- Optional notification after a guest successfully uses a pass
- Automatic guest-page light/dark theme with a manual toggle
- Separate guest web server for Cloudflare Tunnel and reverse proxies
- Admin-only pass creation, listing, and revocation
- Secret hashes only in Home Assistant storage
- Failed Home Assistant actions do not consume a use
- Restrictive browser security headers, origin checks, and no access log

## Installation

### HACS custom repository

Until Gate Pass HA is included in the default HACS catalog, add it as a custom
repository:

1. Open **HACS** in Home Assistant.
2. Open the three-dot menu and select **Custom repositories**.
3. Add `https://github.com/JayTheG5368/gate-pass-ha`.
4. Select **Integration** as the category.
5. Download **Gate Pass HA** and restart Home Assistant.

### Manual installation

Copy `custom_components/gate_pass` from the latest release to:

```text
/config/custom_components/gate_pass
```

Restart Home Assistant completely.

## Configuration

Open **Settings -> Devices & services -> Add integration**, search for
**Gate Pass HA**, and configure the single guest action.

| Field | Example | Description |
|---|---|---|
| Access point name | `Garage gate` | Name shown to administrators and guests |
| Guest action label | `Open gate` | Text on the public action button |
| Target entity | `button.garage_gate_open` | Entity controlled by the guest link |
| Home Assistant action | `button.press` | Fixed `domain.service` action |
| Local guest port | `8922` | Port used only by the guest web server |
| Public base URL | `https://gate.example.com` | Public HTTPS origin, without a path |
| Success notification device | `Phone (notify.mobile_app_phone)` | Optional dropdown of registered `notify.*` services |
| Default validity | `1` | Default validity in hours |
| Default use limit | `1` | `0` means unlimited until expiry |

The entity and action domains must match. For example, use `button.press` with
a `button.*` entity or `cover.open_cover` with a `cover.*` entity.

The public base URL is optional. When it is empty, Gate Pass uses an automatic
local URL. When it is configured, generated links use that URL exactly and do
not append the local guest port.

The success notification device is optional. The dropdown lists the currently
registered device-specific `notify.*` services and still accepts a manual
service name as a fallback. When configured, Gate Pass sends
a notification containing the access point and pass label after the fixed Home
Assistant action succeeds. Notification failures never undo or consume an
additional gate action.

## Reverse proxy

Expose only the dedicated guest server through Cloudflare Tunnel, Nginx,
Caddy, Traefik, or another reverse proxy. A Cloudflare Tunnel route can look
like this:

```text
https://gate.example.com -> http://homeassistant.local:8922
```

Set the integration's public base URL to:

```text
https://gate.example.com
```

A generated link then has this form:

```text
https://gate.example.com/gate-pass/guest/<pass_id>/<secret>
```

Use HTTPS externally. Do not forward the guest port directly through your
router. Configure rate limiting at the reverse proxy or Cloudflare because the
integration intentionally does not include a network-level rate limiter.

## Lovelace card

The integration serves its bundled card from the normal Home Assistant web
server. In **Settings -> Dashboards -> Resources**, add:

```text
/gate-pass/gate-pass-card.js?v=0.3.0-beta.2
```

Select **JavaScript module** as the resource type. Reload the browser or app,
edit a dashboard, and add this manual card:

```yaml
type: custom:gate-pass-card
title: Gate access
icon: mdi:garage-variant
default_name: Link by {user}
default_duration: 1
default_max_uses: 1
```

The visual card editor can change the title, icon, and default pass name. The
`{user}` placeholder is replaced with the name of the Home Assistant user who
creates the pass.

After an update, change the version in the resource URL to the installed
version and reload the frontend to avoid a cached card bundle.

## Home Assistant actions

All Gate Pass actions require a Home Assistant administrator.

| Action | Purpose |
|---|---|
| `gate_pass.create_pass` | Create a pass and return its one-time guest URL |
| `gate_pass.list_passes` | Return currently active passes without secrets |
| `gate_pass.list_activity` | Return the latest persistent activity records |
| `gate_pass.clear_activity` | Permanently clear the activity history |
| `gate_pass.revoke_pass` | Revoke one pass by ID |
| `gate_pass.revoke_all` | Revoke every active pass |

`gate_pass.create_pass` accepts `label`, `duration_hours`, `max_uses`, and an
optional `valid_from` date/time. The complete guest URL is returned only when
the pass is created.

## Security model

The public browser never sends an entity ID or action name. It can only request
the single action selected by the Home Assistant administrator. Each link is a
bearer credential containing a high-entropy secret; only its SHA-256 hash is
stored.

Anyone with the complete URL can use the pass until it expires, reaches its use
limit, or is revoked. Use HTTPS, short validity periods, one-use passes where
possible, and avoid sharing links through systems that log or preview URLs.

The activity history keeps the latest 200 records. It does not store guest URL
secrets, IP addresses, or browser identifiers. Only Home Assistant
administrators can read or clear it.

See [SECURITY.md](SECURITY.md) for deployment guidance and vulnerability
reporting.

## Troubleshooting

- **The integration does not start:** Check the Home Assistant log for a guest
  port conflict and select another local guest port.
- **The generated URL is local:** Set the public base URL in the integration
  options and reload the integration.
- **The card does not appear:** Verify the dashboard resource URL and perform a
  hard refresh after updating its version query.
- **The public page loads but the action fails:** Verify that the configured
  entity exists and that the selected Home Assistant action is available.

Open reproducible problems in the
[issue tracker](https://github.com/JayTheG5368/gate-pass-ha/issues). Do not post
guest URLs, secrets, Home Assistant tokens, tunnel credentials, or logs that
contain them.

## Current limitations

- One access point per Home Assistant installation
- No built-in Cloudflare Access identity check
- Web Share support depends on the browser or Home Assistant companion WebView
- Activity history is limited to the latest 200 records and has no export UI

## Development

```bash
python -m pip install -r requirements-dev.txt
python -m pytest tests
python -m ruff check custom_components tests scripts
npm ci
npm run lint
npm run build
```

The generated card bundle in
`custom_components/gate_pass/frontend/gate-pass-card.js` is committed and must
be rebuilt whenever `frontend/src/gate-pass-card.js` changes.

Maintainers can follow [RELEASING.md](RELEASING.md) to publish a tested GitHub
release.

## License

Gate Pass HA and its original brand assets are released under the [MIT License](LICENSE).
