# Changelog

All notable changes to Gate Pass HA are documented here.

## [0.4.0] - 2026-07-19

### Added

- Multiple independently configured access points
- Shared guest-server ports with access-point-scoped public links
- Dynamic access-point selection or fixed access-point cards
- Optional mobile-friendly quick presets in the visual card editor
- Active-pass and last-successful-use Home Assistant sensors per access point
- Configurable notifications for pass creation, use, and revocation
- Optional selection of multiple notification devices per access point
- Administrator-only CSV activity export

### Changed

- Pass storage is separated by config entry and the previous single-instance
  store is copied automatically during upgrade
- Management actions accept an optional `config_entry_id` and require it only
  when multiple access points are loaded

### Security

- Reject malformed and cross-origin browser action requests
- Pin GitHub Actions dependencies to reviewed commits
- Keep action targets and notification services fixed in administrator settings

### Compatibility

- Existing single-access configurations and pre-0.4 guest links remain valid
- Existing single-device notification settings are adopted automatically
- A failed or unavailable notification device does not block other devices
- The new capabilities are optional; a single access point behaves as before

## [0.3.0] - 2026-07-18

### Added

- Persistent administrator-only activity history for pass creation, successful
  use, and revocation
- Activity tab and confirmed history clearing in the Lovelace card
- Optional classic `notify.*` service after a successful guest action
- Device-friendly dropdown populated from registered `notify.*` services, with
  a manual-entry fallback

### Security

- Activity records exclude guest secrets, IP addresses, and browser identifiers
- Notification targets and contents remain fixed in administrator configuration
- Failed notifications do not retry or repeat the configured access action

## [0.2.1] - 2026-07-18

### Added

- Scheduled pass activation with mobile-friendly presets and custom date/time
- Configurable Lovelace card title, icon, and default pass name
- Automatic guest-page light/dark theme and manual theme toggle
- Confirmation before individual pass revocation
- Local Home Assistant brand images for HACS and the integration UI

### Changed

- Improved mobile form controls and card layout
- Improved native browser sharing with clipboard fallback
- Restricted pass management actions to Home Assistant administrators
- Added stricter browser security headers to the public guest server

### Security

- Guest entity and action remain fixed on the server
- Pass secrets are stored only as SHA-256 hashes
- Failed Home Assistant actions no longer consume a pass use

[0.4.0]: https://github.com/JayTheG5368/gate-pass-ha/releases/tag/v0.4.0
[0.3.0]: https://github.com/JayTheG5368/gate-pass-ha/releases/tag/v0.3.0
[0.2.1]: https://github.com/JayTheG5368/gate-pass-ha/releases/tag/v0.2.1
