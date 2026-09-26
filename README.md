<p align="center">
  <img src="custom_components/gate_pass/brand/icon@2x.png" width="144" alt="Gate Pass HA logo">
</p>

# Gate Pass HA

[![Release](https://img.shields.io/github/v/release/JayTheG5368/gate-pass-ha?display_name=tag&sort=semver)](https://github.com/JayTheG5368/gate-pass-ha/releases)
[![CI](https://github.com/JayTheG5368/gate-pass-ha/actions/workflows/ci.yml/badge.svg)](https://github.com/JayTheG5368/gate-pass-ha/actions/workflows/ci.yml)
[![HACS](https://github.com/JayTheG5368/gate-pass-ha/actions/workflows/validate.yml/badge.svg)](https://github.com/JayTheG5368/gate-pass-ha/actions/workflows/validate.yml)
[![License](https://img.shields.io/github/license/JayTheG5368/gate-pass-ha)](LICENSE)

Gate Pass HA creates temporary public links for preconfigured Home Assistant
actions. It is designed for gates, garage doors, entry doors, and similar access
points without exposing general Home Assistant controls to guests.

> [!IMPORTANT]
> Gate Pass HA is beta software that can control physical access. Test every
> update locally before relying on it and read the [security guidance](SECURITY.md).

## Features

- One fixed server-side Home Assistant action per access point
- Automatic action detection from the selected entity domain
- Optional multiple access points with a shared or separate public URL and port
- Temporary guest links with expiry and optional use limits
- Immediate or scheduled activation
- QR code and link generation in a Lovelace card
- Mobile-friendly validity and use selectors
- Individual and bulk revocation with confirmation
- Persistent activity history for creation, successful use, and revocation
- Optional notifications for pass creation, successful use, and revocation
- Home Assistant sensors for active passes and the last successful use
- Privacy-conscious CSV activity export
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
**Gate Pass HA**, and configure the first guest action. Add the integration again
for every additional access point.

| Field | Example | Description |
|---|---|---|
| Access point name | `Garage gate` | Name shown to administrators and guests |
| Guest action label | `Open gate` | Text on the public action button |
| Target entity | `button.garage_gate_open` | Entity controlled by the guest link |
| Guest action | `button.press` | Detected automatically; shown as a choice only when several safe actions match |
| Local guest port | `8922` | Port used only by the guest web server |
| Public base URL | `https://gate.example.com` | Public HTTPS origin, without a path |
| Allowed link creators | `Family member` | Optional non-admin users who may manage their own links |
| Creator maximum validity | `24` | Optional maximum hours for non-admin link creators |
| Creator maximum use limit | `5` | Optional maximum finite uses for non-admin link creators |
| Allow creator unlimited use | `Off` | Whether non-admin creators may select unlimited uses |
| Expose last-used link name | `Off` | Optional sensor attribute visible to users with sensor access |
| Notification devices | `Phone, Tablet` | Optional multi-select of registered `notify.*` services |
| Notification events | `Pass used` | Optional selection of creation, use, and revocation events |
| Default validity | `1` | Default validity in hours |
| Default use limit | `1` | `0` means unlimited until expiry |

Gate Pass detects the entity domain and only offers actions that can be called
with that entity alone. A `button.*` entity automatically uses `button.press`.
Domains with several useful actions, such as `switch.*`, `cover.*`, or `lock.*`,
show a second selection step. Existing advanced manual actions remain available
when editing an access point.

The public base URL is optional. When it is empty, Gate Pass uses an automatic
local URL. When it is configured, generated links use that URL exactly and do
not append the local guest port.

Allowed link creators are configured separately for every access point. The
field is empty by default, preserving administrator-only access. A selected
non-admin user can create, list, and revoke only links created by that same Home
Assistant user. Administrators can still manage every link and the complete
activity history. Existing links without owner information remain
administrator-only.

The creator limits apply only to selected non-administrator link creators.
Administrators and trusted internal Home Assistant automations retain the full
service limits. Existing installations remain compatible because the initial
creator limits match the previous maximums until an administrator tightens
them.

Notification devices are optional. The multi-select lists the currently
registered device-specific `notify.*` services and still accepts a manual
service name as a fallback. The same message is sent independently to every
selected device. You can independently select notifications for
creation, successful use, and revocation. Notification failures never undo or
consume an additional access action, and one unavailable device does not block
the remaining devices.

### Link lifecycle and configuration changes

Existing links are bound to the access point's configured entity and action.
Changing either revokes its outstanding links; changing a name, notification
setting, or public URL preserves them. On the first upgrade from a version
without action binding, existing links are adopted for the currently configured
action. Upgrade before changing the action if existing links must be preserved.

Reloading an access point waits for in-flight actions and use accounting to finish.
New guest actions are rejected during that short shutdown window. An action
cancelled during shutdown is conservatively counted because the device may
already have acted. Normal service errors continue to release the reservation.

Each access point retains at most 200 recent terminal (revoked, expired, or
exhausted) pass records, plus any terminal records still involved in an in-flight
action. Active and scheduled passes are never purged by this retention limit.
The separate activity history remains limited to 200 events.

Unknown entity domains no longer offer every registered service automatically.
An explicitly configured existing custom action remains available when editing
its access point.

### Multiple access points

Each integration entry has its own action, pass storage, defaults, notification
settings, and public base URL. Access points may share the same local guest port;
Gate Pass then runs one server and routes each scoped link to the correct fixed
action. Existing single-access installations and links created before version
0.4 are migrated and remain compatible.

For one public hostname, configure the same port and public base URL on every
entry. For separate hostnames, set a different public base URL per entry. Those
hostnames may still route to the same local guest port, or each entry can use a
separate port.

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
https://gate.example.com/gate-pass/guest/<access_point_id>/<pass_id>/<secret>
```

Use HTTPS externally. Do not forward the guest port directly through your
router. Configure rate limiting at the reverse proxy or Cloudflare because the
integration intentionally does not include a network-level rate limiter.

## Lovelace card

The integration serves its bundled card from the normal Home Assistant web
server. In **Settings -> Dashboards -> Resources**, add:

```text
/gate-pass/gate-pass-card.js?v=0.5.2
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
presets:
  - name: Parcel delivery
    label: Parcel delivery
    duration_hours: 2
    max_uses: 1
    start_option: now
```

The visual card editor can change the title, icon, default pass name, defaults,
and optional quick presets. The `{user}` placeholder is replaced with the name
of the Home Assistant user who creates the pass.

With multiple access points, leave **Access point** set to **Choose in card** to
show a selector. To create one dedicated card per gate or door, select a fixed
access point in each card's visual editor. In YAML, the equivalent optional
setting is `access_point: <config_entry_id>`.

After an update, change the version in the resource URL to the installed
version and reload the frontend to avoid a cached card bundle.

## Home Assistant actions

Gate Pass actions enforce the permissions configured for the selected access
point. Administrators and trusted internal Home Assistant calls retain full
access. Allowed non-admin link creators can call `list_access_points`,
`create_pass`, `list_passes`, `list_activity`, and `revoke_pass`, with results
restricted to their own links. Exporting or clearing activity and revoking all
links remain administrator-only.

| Action | Purpose |
|---|---|
| `gate_pass.list_access_points` | Return all loaded access points for cards and automations |
| `gate_pass.create_pass` | Create a pass and return its one-time guest URL |
| `gate_pass.list_passes` | Return currently active passes without secrets |
| `gate_pass.list_activity` | Return the latest persistent activity records |
| `gate_pass.export_activity` | Return the selected activity history as CSV |
| `gate_pass.clear_activity` | Permanently clear the activity history |
| `gate_pass.revoke_pass` | Revoke one pass by ID |
| `gate_pass.revoke_all` | Revoke every active pass |

All access-point-specific actions accept an optional `config_entry_id`. It may
be omitted when exactly one access point is loaded and is required when several
are loaded. `gate_pass.create_pass` also accepts `label`, `duration_hours`,
`max_uses`, and an optional `valid_from` date/time. The complete guest URL is
returned only when the pass is created.

Each access point also creates an active-pass count sensor and a timestamp sensor
for the last successful use. These can be used in dashboards and automations.
The last-used sensor always exposes the use count. Its pass-name attribute is
disabled by default because every Home Assistant user with access to that entity
could read it; administrators can explicitly enable it in the integration
options.

## Security model

The public browser never sends an entity ID or action name. It can only request
the single action selected by the Home Assistant administrator. Each link is a
bearer credential containing a high-entropy secret; only its SHA-256 hash is
stored.

Anyone with the complete URL can use the pass until it expires, reaches its use
limit, or is revoked. Use HTTPS, short validity periods, one-use passes where
possible, and avoid sharing links through systems that log or preview URLs.

The activity history keeps the latest 200 records. It does not store guest URL
secrets, IP addresses, or browser identifiers. Allowed link creators can read
only activity associated with their own links. Only Home Assistant
administrators can read the complete history, export it, or clear it.

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

- No built-in Cloudflare Access identity check
- Web Share support depends on the browser or Home Assistant companion WebView
- Activity history is limited to the latest 200 records per access point

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
