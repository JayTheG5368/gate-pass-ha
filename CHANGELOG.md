# Changelog

All notable changes to Gate Pass HA are documented here.

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

[0.2.1]: https://github.com/JayTheG5368/gate-pass-ha/releases/tag/v0.2.1
