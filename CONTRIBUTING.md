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
npm test
npm audit --audit-level=high
npm run build
```

Commit the rebuilt
`custom_components/gate_pass/frontend/gate-pass-card.js` when the frontend
source changes. Keep pull requests narrowly scoped and include tests for
behavioral changes.

## Required checks on main

Import `.github/main-ruleset.json` in the repository's **Settings → Rules → Rulesets →
New ruleset → Import a ruleset**, then verify that enforcement is **Active**.
The file requires pull requests and the `test`, `HACS`, and `Hassfest` checks,
blocks deletion and force pushes, and allows merging without an additional
reviewer for this single-maintainer repository. Committing the JSON alone does
not activate these protections. Creating repository rulesets requires GitHub
Administration write permission.

See [GitHub's ruleset API documentation](https://docs.github.com/en/rest/repos/rules#create-a-repository-ruleset).

The test suite uses real aiohttp HTTP routes and runs the actual integration
setup/unload functions against narrow Home Assistant API doubles. It does not
replace a smoke test on a real Home Assistant installation and physical device.
