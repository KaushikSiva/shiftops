# Live Vultr deployment

Public app: **https://shiftops.104-156-229-254.sslip.io**

Verified 2026-09-27. The app is served directly from this Vultr VM through Caddy
with a publicly trusted Let's Encrypt certificate. The hostname uses sslip.io
DNS mapped to the VM's public IP; it is not a laptop tunnel.

| Item | Deployed value |
| --- | --- |
| Provider / region | Vultr / Silicon Valley (`sjc`) |
| Instance | `d6fa84e7-0877-4ae1-926d-29fc2719435c` |
| Plan | `vhp-2c-4gb-amd` — 2 vCPUs, 4 GB RAM, 100 GB disk |
| OS | Ubuntu 24.04 LTS x64 |
| Public IP | `104.156.229.254` |
| Runtime source | `4773d610343a6a1273d07234d62c9d181918e29c` |
| Application directory | `/opt/shiftops` |
| Services | Docker Compose: `app` and `proxy` |
| Data | SQLite WAL in the `shiftops_operations` Docker volume |
| Compute price at provisioning | $0.033/hour, $24/month |

No GPU, paid backup or optional paid service was provisioned. Compute charges
continue while the instance is retained; use the Vultr account to review current
credits and billing. Deleting the VM ends its hosting and removes its local data.

## Evidence

- [Vultr API metadata, VM vendor, container configuration and certificate](validation/provider-vultr.json)
- [Public HTTP workflow smoke test](validation/smoke-vultr.txt)
- [Public browser walkthrough: 16 checks](validation/browser-vultr.json)
- [Two container restarts and proxy behavior](validation/persistence-vultr.json)

The deployment flag returned by `/api/health` is only configuration. Provider
identity was separately checked against the authenticated Vultr API and the VM's
hardware vendor. The deployed backend runs as UID 10001, with a read-only root
filesystem, dropped capabilities, and a dedicated writable data volume.

## Operation

An administrator with the provisioned SSH key can run these commands on the VM:

```sh
cd /opt/shiftops
docker compose ps
docker compose logs --tail 100 app
docker compose restart app
```

Restarting the app pauses any interrupted inspection. Use **Resume inspection**
to continue from its persisted checkpoint. Completed work orders and reservations
remain in the data volume. Do not remove that volume to deploy code updates.

Caddy publishes ports 80 and 443. The API container port and SQLite database are
internal. The Vultr firewall permits SSH only from the operator IP recorded at
provisioning; update that rule in Vultr if the operator network changes. The API
key and SSH private key remain on the operator's Mac and are not in this repository
or the VM's application files.
