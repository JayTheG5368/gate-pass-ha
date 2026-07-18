# Contributing

Bug reports and focused pull requests are welcome.

## Before opening an issue

- Confirm the problem still occurs on the latest release.
- Check existing issues for the same behavior.
- Remove guest URLs, secrets, Home Assistant tokens, credentials, public
  hostnames, and local IP addresses from screenshots and logs.
- Use the private security reporting process in `SECURITY.md` for vulnerabilities.

## Development setup

Install the Python and frontend dependencies:

```bash
python -m pip install -r requirements-dev.txt
npm ci
```

Run the required checks before opening a pull request:

```bash
python -m pytest tests
python -m ruff check custom_components tests scripts
npm run lint
npm run build
```

Commit the rebuilt
`custom_components/gate_pass/frontend/gate-pass-card.js` when the frontend
source changes. Keep pull requests narrowly scoped and include tests for
behavioral changes.
