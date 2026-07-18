# Changelog

All notable changes to Gate Pass HA are documented here.

## [0.3.0-beta.2] - Unreleased local test

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

[0.2.1]: https://github.com/JayTheG5368/gate-pass-ha/releases/tag/v0.2.1
