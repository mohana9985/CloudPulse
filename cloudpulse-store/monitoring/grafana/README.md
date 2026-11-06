# `monitoring/grafana/` — Grafana

Contains only [`provisioning/`](provisioning/README.md), mounted read-only at
`/etc/grafana/provisioning` so Grafana starts with its datasource and dashboard already configured.
Sign-up and analytics reporting are disabled in `../../compose.yaml`.
