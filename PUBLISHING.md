# Publishing checklist

Maintainer checklist for publishing Progressive Automations for Home Assistant.

The public repository is:

`https://github.com/roweboat123/progressive-automations-home-assistant`

## 1. Validate

The included `.github/workflows/validate.yml` runs both:

- HACS validation (`category: integration`).
- Home Assistant Hassfest validation.

Resolve validation failures before creating a release. The integration contains local brand assets under `custom_components/progressive_automations/brand/`, which Home Assistant 2026.3+ supports for custom integrations.

## 2. Create GitHub release

For v1.0.1, create a full GitHub **Release**, not only a tag.

Tag:

`v1.0.1`

Suggested title:

`Progressive Automations v1.0.1`

Use the `1.0.1` section of `CHANGELOG.md` for release notes and mention that v1.0.1 is a frontend-only maintenance update over the hardware-validated v1.0.0 backend.

For later releases, update `manifest.json`, `CHANGELOG.md`, and any dashboard cache-buster/version references before tagging.

## 3. HACS distribution

The repository structure follows HACS integration requirements:

`custom_components/progressive_automations/...`

Users can add the public repository to HACS as a **Custom repository** of type **Integration**.

Submitting it to the HACS default repository list is a separate step. Current HACS publisher requirements include a public GitHub repository, passing HACS and Hassfest actions, a GitHub release, issues enabled, repository metadata, and valid integration metadata.

## 4. Optional dashboard card

HACS integration installation only installs the custom component. The optional card remains in `dashboard/progressive-automations-card.js` and is installed manually into `/config/www` as documented in `DASHBOARD.md`.

If the dashboard develops independently or gains broader use, consider publishing it later as its own HACS Dashboard/Plugin repository rather than coupling frontend installation to the integration package.
