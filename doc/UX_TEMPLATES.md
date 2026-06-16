# UX templates

Gamatrix uses one authenticated UX template per deployment. Set `UX_TEMPLATE`
to `default` or `modern` locally, or set `ux_template` in the private
`cdk-config.yaml` used for deployment. Invalid names fail application startup
and CDK config loading.

Public sign-in and password-recovery pages deliberately use the stable root
templates and are not affected by `UX_TEMPLATE`.

Each directory under `src/gamatrix/templates/<name>/` must contain every file
listed by `AUTHENTICATED_TEMPLATE_NAMES` in `gamatrix.templating`. Its
stylesheet lives at `src/gamatrix/static/templates/<name>/style.css` and must
support:

- `light`
- `dark`
- `high-contrast`
- `color-blind`

Users choose a mode on the Preferences page. The selection is stored with the
account and applies on the next navigation. Until a mode is chosen, templates
omit `data-mode` and CSS follows the browser's light/dark preference.
