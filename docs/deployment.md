# Deployment readiness

`mansour-vision` is the production architecture, but Milestone 2 remains a
service foundation: it does not yet ingest cameras or run inference. These steps
harden and validate the stack; they do not claim Milestone 3 features exist.

## Single-host stack

```powershell
make secrets
Copy-Item .env.example .env
.\scripts\deployment-readiness.ps1
docker compose -f infra/compose/docker-compose.yml up -d --build
docker compose -f infra/compose/docker-compose.yml ps
```

PostgreSQL and Redis require independent, randomly generated, file-mounted
passwords. Neither data service is published to the host.

## Public deployment requirements

Before exposing the stack outside a trusted network:

- terminate TLS at NGINX or a managed load balancer;
- set the real `MEDIA_PUBLIC_HOST`;
- mount certificates from a secret store;
- restrict RTSP, WebRTC, and HLS ports at the firewall;
- implement Milestone 3 authentication/RBAC and camera configuration;
- configure PostgreSQL and Redis backups and test restoration;
- benchmark the intended camera count on the deployment hardware;
- complete a privacy/legal review for every enabled analytic.

Set `ENVIRONMENT=production`, `TLS_CERTIFICATE_PATH`, and
`TLS_PRIVATE_KEY_PATH` before running `scripts/deployment-readiness.ps1`. The
script refuses a public-production configuration missing those inputs.
