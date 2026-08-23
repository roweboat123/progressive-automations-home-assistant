# Publishing checklist

This repository tree is prepared for a public GitHub + HACS release. Two metadata fields intentionally use `__GITHUB_OWNER__` because the maintainer's GitHub username was not available when the package was assembled.

## 1. Finalize GitHub metadata

Run from the repository root:

```bash
python3 scripts/set_github_owner.py YOUR_GITHUB_USERNAME
```

This updates:

- `custom_components/progressive_automations/manifest.json`
- `README.md`

The intended repository name is:

`progressive-automations-home-assistant`

## 2. Create the GitHub repository

Recommended settings:

- Public repository.
- Issues enabled.
- Description: `Local Bluetooth Home Assistant integration for Progressive Automations RT-BT1 actuator controllers.`
- Suggested topics: `home-assistant`, `hacs`, `bluetooth`, `ble`, `progressive-automations`, `rt-bt1`, `actuator`, `home-automation`.

Push this repository tree to the default branch.

## 3. Validate

The included `.github/workflows/validate.yml` runs both:

- HACS validation (`category: integration`).
- Home Assistant Hassfest validation.

Resolve validation failures before creating the first public release. The integration already contains local brand assets under `custom_components/progressive_automations/brand/`, which Home Assistant 2026.3+ supports for custom integrations.

## 4. Create GitHub release v1.0.1

Create a full GitHub **Release**, not only a tag. Tag it:

`v1.0.1`

Suggested title:

`Progressive Automations v1.0.1`

Use the `1.0.1` section of `CHANGELOG.md` for release notes and mention that v1.0.1 is a frontend-only maintenance update over the hardware-validated v1.0.0 backend.

## 5. HACS distribution

The repository structure follows HACS integration requirements:

`custom_components/progressive_automations/...`

Users can immediately add the public repository to HACS as a **Custom repository** of type **Integration**.

Submitting it to the HACS default repository list is a separate step. Current HACS publisher requirements include a public GitHub repository, passing HACS and Hassfest actions, a GitHub release, issues enabled, repository description/topics, and valid integration metadata.

## 6. Optional dashboard card

HACS integration installation only installs the custom component. The optional card remains in `dashboard/progressive-automations-card.js` and is installed manually into `/config/www` as documented in `DASHBOARD.md`.

If the dashboard develops independently or gains broader use, consider publishing it later as its own HACS Dashboard/Plugin repository rather than coupling frontend installation to the integration package.
