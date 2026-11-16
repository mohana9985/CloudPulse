# `cloudpulse-store/docs/` — Store documentation

| Document | Contents |
|---|---|
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Container layout, why this design, backend layers, frontend structure, database schema, monitoring surface, scope boundaries |
| [`API_DOCUMENTATION.md`](API_DOCUMENTATION.md) | Every endpoint with request/response examples and the error format |
| [`LOCAL_SETUP.md`](LOCAL_SETUP.md) | macOS (Apple Silicon) setup: Docker/Colima, Docker workflow, development mode without Docker, tests |
| [`TESTING_GUIDE.md`](TESTING_GUIDE.md) | Backend tests, frontend build, Docker system verification, load tests, verification log template |
| [`AWS_TWO_EC2.md`](AWS_TWO_EC2.md) | **Current deployment plan**: two new EC2 instances (store + dashboard/scheduler), cloned from GitHub, all settings in `.env`, security groups that reference each other |
| [`AWS_DEPLOYMENT.md`](AWS_DEPLOYMENT.md) | Single-instance EC2 basics: SSH, Docker install, security group, HTTPS, updates, shutdown, cost considerations, troubleshooting |
| [`SCHEDULING.md`](SCHEDULING.md) | Scheduling algorithms applied to the website: gateway design, local measurements ([`results/`](results/README.md) holds the raw tables) |

Start with the [store README](../README.md); the project overview is in the
[repository README](../../README.md).
