# Security policy

Gate Pass HA can trigger a physical access action. Treat every generated guest
URL as a credential and deploy the integration with the same care as a remote
door opener.

## Supported versions

Security fixes are provided for the latest published release. Upgrade to the
latest version before reporting a problem.

## Reporting a vulnerability

Do not disclose security vulnerabilities in a public issue.

Use GitHub's **Security -> Report a vulnerability** option for this repository:

https://github.com/JayTheG5368/gate-pass-ha/security/advisories/new

Include the affected version, Home Assistant version, deployment topology,
reproduction steps, and expected impact. Remove all real guest URLs, secrets,
Home Assistant tokens, credentials, hostnames, and IP addresses.

## Deployment requirements

- Publish the guest server only through an HTTPS reverse proxy or tunnel.
- Do not expose the local guest port with router port forwarding.
- Apply rate limiting and abuse controls at the proxy or Cloudflare layer.
- Prefer short validity periods and one-use passes.
- Revoke links immediately when they are sent to the wrong recipient.
- Avoid analytics, link preview, and logging systems that record full URLs.
- Keep Home Assistant, Gate Pass HA, HACS, and the reverse proxy updated.
- Back up Home Assistant before upgrading the integration.

## Trust boundaries

The configured entity and Home Assistant action are stored server-side and
cannot be selected by a guest. Creating, listing, and revoking passes requires a
Home Assistant administrator. The complete link is nevertheless a bearer
credential: possession of the URL grants its remaining access.

Gate Pass HA does not provide identity verification, an internal firewall, or
network-level rate limiting. Those controls belong at the reverse proxy and
network layers.
