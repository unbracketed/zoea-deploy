# zoea-deploy

`pyinfra` deploys for Zoea on exe.dev VMs.

Supports per-VM combinations of:
- `server` + `web`
- `server` only
- `web` only

Assumptions:
- target VMs are normal SSH hosts
- exe.dev VMs already have `nginx`, `pi`, and `python3`
- local deploy machine has `go`, `node`/`npm`, and `rsync`
- nginx is the public entrypoint on port `80`

## Layout

- `deploy.py` — main pyinfra deploy
- `config.py` — builds local artifacts once before deploy
- `group_data/all.py` — shared defaults
- `inventories/example.py` — sample inventory
- `templates/` — systemd + nginx templates

## Install

```bash
cd zoea-deploy
uv sync
```

Or run without creating a venv:

```bash
cd zoea-deploy
uv run pyinfra inventories/example.py deploy.py
```

## Inventory

Copy `inventories/example.py` to something like `inventories/production.py`.

Each host sets `zoea_components`:

```py
("full.exe.xyz", {"zoea_components": ["server", "web"]})
("api.exe.xyz", {"zoea_components": ["server"]})
("web.exe.xyz", {
    "zoea_components": ["web"],
    "zoea_api_upstream": "https://api.exe.xyz",
})
```

## Deploy

Deploy all hosts:

```bash
uv run pyinfra inventories/production.py deploy.py
```

Deploy one host:

```bash
uv run pyinfra inventories/production.py deploy.py --limit api.exe.xyz
```

## Build behavior

`config.py` builds/prepares artifacts locally before pyinfra connects:
- `zoea-server` via `go build`
- `zoea-web-ui` via `npm ci && npm run build`
- `zoea-tools` by copying the package to `.build/zoea-tools`, running `npm ci --omit=dev --legacy-peer-deps` there, and packing `.build/zoea-tools.tar.gz`

Server deploys upload/unpack prepared `.build/zoea-tools.tar.gz` and sync local `zoea-core/` to the VM.

Skip builds when needed:

```bash
ZOEA_DEPLOY_BUILD_SERVER=0 uv run pyinfra inventories/production.py deploy.py
ZOEA_DEPLOY_BUILD_WEB=0 uv run pyinfra inventories/production.py deploy.py
ZOEA_DEPLOY_BUILD_TOOLS=0 uv run pyinfra inventories/production.py deploy.py
```

Override local npm install commands:

```bash
ZOEA_DEPLOY_NPM_INSTALL="npm install" uv run pyinfra inventories/production.py deploy.py
ZOEA_DEPLOY_TOOLS_NPM_INSTALL="npm install --omit=dev --legacy-peer-deps" uv run pyinfra inventories/production.py deploy.py
```

## What gets managed

### Server hosts
- uploads `zoea-server` binary to `/opt/zoea/<instance>/server/bin/zoea-server`
- uploads/unpacks agent runtime packages under `/opt/zoea/<instance>/agent-runtime/`:
  - `zoea-tools/` — Pi package for manifest-discovered tools
  - `zoea-core/` — Python package source exposed to tools through `PYTHONPATH`
- registers the synced `zoea-tools/` package with Pi for the runtime user via `pi install`
- writes env file to `/etc/zoea/<instance>.env`, including `HOME`, `ZOEA_CORE_PATH`, and `PYTHONPATH` for `zoea-core`
- writes a systemd unit at `/etc/systemd/system/<service>.service`
- persists SQLite + session state under `/opt/zoea/<instance>/server/`

### Web hosts
- syncs built `zoea-web-ui` assets to `/opt/zoea/<instance>/web/current`
- writes an nginx site in `/etc/nginx/sites-available/`
- enables that site and disables nginx's default site

### Combined hosts
- nginx serves the web UI and proxies `/v1`, `/healthz`, and `/readyz` to the local server

### Web-only hosts
- nginx serves the web UI and proxies API traffic to `zoea_api_upstream`

## Important note about zoea-web-ui standalone

This UI is deployed as a same-origin app behind nginx.

So `web`-only hosts still need nginx to proxy `/v1` to a Zoea backend. Set:

```py
"zoea_api_upstream": "https://your-api-host"
```

## Useful host data

Defaults live in `group_data/all.py`.

Common overrides:
- `zoea_instance_name`
- `zoea_server_port`
- `zoea_server_working_dir`
- `zoea_server_names`
- `zoea_auth_api_keys`
- `zoea_run_home`
- `zoea_agent_runtime_dir`
- `zoea_extra_env`

Example:

```py
("api.exe.xyz", {
    "zoea_components": ["server"],
    "zoea_instance_name": "prod-api",
    "zoea_server_working_dir": "/home/exedev/app",
    "zoea_auth_api_keys": "myapp:sk_secret:admin",
    "zoea_extra_env": {
        "OPENAI_API_KEY": "...",
    },
})
```

## exe.dev note

After deploy, point exe.dev sharing at port 80 if needed:

```bash
ssh exe.dev share port <vm-name> 80
```
