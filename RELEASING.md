# Releasing Gate Pass HA

Releases follow semantic versioning and use matching `vMAJOR.MINOR.PATCH` Git
tags. The release workflow creates the GitHub release and manual installation
archive automatically after a matching tag is pushed.

## Prepare a release

1. Update the version in:
   - `custom_components/gate_pass/manifest.json`
   - `package.json`
   - `package-lock.json` at both package version locations
   - the Lovelace resource URL in `README.md`
2. Add the release notes to `CHANGELOG.md`.
3. Rebuild and run all checks:

   ```bash
   python -m pytest tests
   python -m ruff check custom_components tests scripts
   python -m ruff format --check custom_components tests scripts
   npm ci
   npm run lint
   npm test
   npm audit --audit-level=high
   npm run build
   ```

4. Submit the release preparation in a pull request targeting `main` and merge it after validation.
5. Wait for the CI, HACS, and hassfest workflows to pass.

## Publish

For version `0.2.1`:

```bash
git tag -a v0.2.1 -m "Gate Pass HA v0.2.1"
git push origin v0.2.1
```

The tag starts `.github/workflows/release.yml`. The workflow verifies that the
tag, integration manifest, and npm package versions match, reruns the tests,
builds the frontend, creates `gate-pass-ha-0.2.1.zip`, and publishes a complete
GitHub release.

Do not move or reuse an existing release tag. Publish a new patch version for
every correction to released code.
