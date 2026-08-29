# rknightion public repo settings audit

Generated 2026-08-29 across the 25 non-archived, non-fork public repos.

Raw data: `repo-settings-audit.json`. Regenerate with:

```bash
./fleet/collect-repo-settings.py --out fleet/repo-settings-audit.json
./fleet/collect-repo-settings.py --check   # exit 1 on any divergence
```

**The standard is derived, not declared.** Whatever most repos already do is treated as the norm, so a deliberate fleet-wide change needs no edit here — move thirteen repos and the standard follows. The trade is that a majority which drifts *together* is invisible, which is why this reports for a human rather than enforcing.

## The standard, derived from the majority

Every line below is what most repos already do. Nothing here is invented.

| Setting | Standard | Conforming |
|---|---|---|
| Branch ruleset on `main` | deletion + non_fast_forward + pull_request + required_status_checks, enforcement `active`, gating `ci-success` | 21/25 |
| `delete_branch_on_merge` | `true` | 21/25 |
| `allow_auto_merge` | `true` — Renovate platform-automerge needs it | 21/25 |
| `allow_update_branch` | `false` | 20/25 |
| `web_commit_signoff_required` | `false` | 21/25 |
| `has_wiki` | `false` | 15/25 |
| `has_projects` | `true` | 23/25 |
| `has_discussions` | `false` | 23/25 |
| Secret scanning | `enabled` | 22/25 |
| Secret scanning push protection | `enabled` | 22/25 |
| Dependabot **security updates** | `disabled` — Renovate raises these | 23/25 |
| Dependabot **alerts** | `true` — alerts on, PRs off | 24/25 |
| Automated security fixes | `false` — same reason | 23/25 |
| Default workflow permissions | `read` | 25/25 |
| Actions can approve PRs | `false` | 25/25 |
| `renovate.json` present | `true` | 24/25 |

## Divergence

- **Branch ruleset on `main`** — 4 outlier(s): `codexlb2otel`, `grafana-cloud-vending-machine`, `polylens2otel`, `rfc6035-2otel`
- **`delete_branch_on_merge`** — 4 outlier(s): `codexlb2otel`, `grafana-cloud-vending-machine`, `polylens2otel`, `rfc6035-2otel`
- **`allow_auto_merge`** — 4 outlier(s): `codexlb2otel`, `grafana-cloud-vending-machine`, `polylens2otel`, `rfc6035-2otel`
- **`allow_update_branch`** — 5 outlier(s): `bumblebee-intune`, `meraki-dashboard-ha`, `openbao-plugin-secrets-github`, `opnsense2otel`, `transceiver-exporter`
- **`web_commit_signoff_required`** — 4 outlier(s): `bumblebee-intune`, `openbao-plugin-secrets-github`, `opnsense2otel`, `transceiver-exporter`
- **`has_wiki`** — 10 outlier(s): `.github`, `autopi-ha`, `bumblebee-catalog`, `bumblebee-intune`, `meraki-dashboard-exporter`, `openbao-plugin-secrets-github`, `opnsense2otel`, `paperless-ngx-dedupe`, `rfc6035-2otel`, `transceiver-exporter`
- **`has_projects`** — 2 outlier(s): `meraki-dashboard-ha`, `sagemcom-f3896-py`
- **`has_discussions`** — 2 outlier(s): `opnsense2otel`, `paperless-ngx-dedupe`
- **Secret scanning** — 3 outlier(s): `codexlb2otel`, `grafana-cloud-vending-machine`, `sf2loki`
- **Secret scanning push protection** — 3 outlier(s): `codexlb2otel`, `grafana-cloud-vending-machine`, `sf2loki`
- **Dependabot **security updates**** — 2 outlier(s): `grafana-cloud-org-insights`, `polylens2otel`
- **Dependabot **alerts**** — 1 outlier(s): `codexlb2otel`
- **Automated security fixes** — 2 outlier(s): `grafana-cloud-org-insights`, `polylens2otel`
- **`renovate.json` present** — 1 outlier(s): `codexlb2otel`

## Worst offenders

- `codexlb2otel` — 7 settings off standard
- `grafana-cloud-vending-machine` — 5 settings off standard
- `polylens2otel` — 5 settings off standard
- `rfc6035-2otel` — 4 settings off standard
- `opnsense2otel` — 4 settings off standard
- `bumblebee-intune` — 3 settings off standard
- `openbao-plugin-secrets-github` — 3 settings off standard
- `transceiver-exporter` — 3 settings off standard

## Deliberate exceptions, not drift

- `meraki-dashboard-ha` also gates `validate-success`, and `tailscale2otel` also gates `helm-success`. Both have a genuine second workflow. Keep.
- Licences vary by project and are not a fleet setting.
