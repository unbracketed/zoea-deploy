from __future__ import annotations

import json
import shlex
from pathlib import Path, PurePosixPath

from pyinfra import host
from pyinfra.operations import files, server, systemd


DEPLOY_DIR = Path(__file__).resolve().parent
REPO_ROOT = DEPLOY_DIR.parent
SERVER_BINARY_SRC = ".build/zoea-server/zoea-server"
WEB_DIST_SRC = ".build/zoea-web-ui"
ZOEA_TOOLS_ARCHIVE_SRC = ".build/zoea-tools.tar.gz"
ZOEA_CORE_SRC = REPO_ROOT / "zoea-core"
SYNC_EXCLUDE_DIRS = [".git", ".venv", ".pytest_cache", "__pycache__"]
SYNC_EXCLUDE_FILES = ["*.pyc", ".DS_Store"]


def data(name: str, default=None):
    value = getattr(host.data, name, default)
    return default if value is None else value


def pjoin(*parts: str) -> str:
    return str(PurePosixPath(*parts))


def q(value: str | Path) -> str:
    return shlex.quote(str(value))


def as_run_user(command: str, *, run_user: str, run_home: str) -> str:
    return "sudo -Hu {user} env HOME={home} bash -lc {command}".format(
        user=q(run_user),
        home=q(run_home),
        command=q(command),
    )


def normalize_components(raw) -> set[str]:
    if isinstance(raw, str):
        raw = [raw]
    return {str(item).strip().lower() for item in (raw or []) if str(item).strip()}


def normalize_server_names(raw) -> list[str]:
    if isinstance(raw, str):
        raw = [raw]
    names = [str(item).strip() for item in (raw or []) if str(item).strip()]
    return names or [host.name]


def env_items_for_server(values: dict[str, str]) -> list[tuple[str, str]]:
    return [(key, json.dumps(str(value))) for key, value in sorted(values.items()) if value != ""]


components = normalize_components(data("zoea_components", ["server", "web"]))
server_enabled = "server" in components
web_enabled = "web" in components

if not server_enabled and not web_enabled:
    raise ValueError(f"{host.name}: zoea_components must include 'server', 'web', or both")

instance_name = data("zoea_instance_name", host.name.split(".")[0].replace("_", "-"))
run_user = data("zoea_run_user", "exedev")
run_group = data("zoea_run_group", run_user)
run_home = data("zoea_run_home", f"/home/{run_user}" if run_user != "root" else "/root")
root_dir = pjoin(data("zoea_root_dir", "/opt/zoea"), instance_name)
server_names = normalize_server_names(data("zoea_server_names", []))
public_host = next((name for name in server_names if name != "_"), host.name)

server_host = data("zoea_server_host", "127.0.0.1")
server_port = int(data("zoea_server_port", 14004))
listen_addr = f"{server_host}:{server_port}"
server_service_name = data("zoea_server_service_name", f"zoea-server-{instance_name}")
server_dir = pjoin(root_dir, "server")
server_bin_dir = pjoin(server_dir, "bin")
server_state_dir = pjoin(server_dir, "state")
server_sessions_dir = pjoin(server_dir, "sessions")
server_binary_dest = pjoin(server_bin_dir, "zoea-server")
agent_runtime_dir = data("zoea_agent_runtime_dir", pjoin(root_dir, "agent-runtime"))
zoea_tools_dir = pjoin(agent_runtime_dir, "zoea-tools")
zoea_tools_archive_dest = pjoin(agent_runtime_dir, "zoea-tools.tar.gz")
zoea_core_dir = pjoin(agent_runtime_dir, "zoea-core")
zoea_core_pythonpath = pjoin(zoea_core_dir, "src")
server_env_file = pjoin("/etc/zoea", f"{instance_name}.env")
server_unit_file = pjoin("/etc/systemd/system", f"{server_service_name}.service")
server_ZOEA_STORE_DSN = data("zoea_ZOEA_STORE_DSN", pjoin(server_state_dir, "zoea.db"))
server_working_dir = data("zoea_server_working_dir", "")
pi_bin_path = data("zoea_pi_bin_path", "pi")

web_root = data("zoea_web_root", pjoin(root_dir, "web", "current"))
nginx_listen_port = int(data("zoea_nginx_listen_port", 80))
nginx_site_name = data("zoea_nginx_site_name", f"zoea-{instance_name}")
nginx_site_available = pjoin("/etc/nginx/sites-available", f"{nginx_site_name}.conf")
nginx_site_enabled = pjoin("/etc/nginx/sites-enabled", f"{nginx_site_name}.conf")
client_max_body_size = data("zoea_client_max_body_size", "20m")
api_upstream = data("zoea_api_upstream", f"http://{server_host}:{server_port}" if server_enabled else "")

if not api_upstream:
    raise ValueError(f"{host.name}: zoea_api_upstream is required when deploying web without server")

files.directory(
    name="Ensure Zoea root exists",
    path=root_dir,
    user=run_user,
    group=run_group,
    mode="755",
)

restart_server = None
if server_enabled:
    files.directory(
        name="Ensure Zoea server directories exist",
        path=server_dir,
        user=run_user,
        group=run_group,
        mode="755",
    )
    for path in (server_bin_dir, server_state_dir, server_sessions_dir, agent_runtime_dir):
        files.directory(
            name=f"Ensure {path} exists",
            path=path,
            user=run_user,
            group=run_group,
            mode="755",
        )

    zoea_tools_archive = files.put(
        name="Upload zoea-tools Pi package archive",
        src=ZOEA_TOOLS_ARCHIVE_SRC,
        dest=zoea_tools_archive_dest,
        user=run_user,
        group=run_group,
        mode="644",
    )

    zoea_tools_unpack = server.shell(
        name="Unpack zoea-tools Pi package",
        commands=[
            "rm -rf {tools} && mkdir -p {tools} && tar -xzf {archive} -C {tools} && chown -R {user}:{group} {tools}".format(
                tools=q(zoea_tools_dir),
                archive=q(zoea_tools_archive_dest),
                user=q(run_user),
                group=q(run_group),
            )
        ],
        _if=lambda: zoea_tools_archive.did_change(),
    )

    zoea_core_sync = files.sync(
        name="Sync zoea-core Python package",
        src=str(ZOEA_CORE_SRC),
        dest=zoea_core_dir,
        user=run_user,
        group=run_group,
        delete=True,
        exclude=SYNC_EXCLUDE_FILES,
        exclude_dir=SYNC_EXCLUDE_DIRS,
        add_deploy_dir=False,
    )

    server.shell(
        name="Register zoea-tools with Pi",
        commands=[
            as_run_user(
                f"{q(pi_bin_path)} install {q(zoea_tools_dir)}",
                run_user=run_user,
                run_home=run_home,
            )
        ],
    )

    extra_env = {str(k): str(v) for k, v in dict(data("zoea_extra_env", {})).items()}
    pythonpath_parts = [zoea_core_pythonpath]
    if extra_env.get("PYTHONPATH"):
        pythonpath_parts.append(extra_env["PYTHONPATH"])
    extra_env["PYTHONPATH"] = ":".join(pythonpath_parts)

    server_binary = files.put(
        name="Upload zoea-server binary",
        src=SERVER_BINARY_SRC,
        dest=server_binary_dest,
        user=run_user,
        group=run_group,
        mode="755",
    )

    server_env = files.template(
        name="Render zoea-server environment",
        src="templates/zoea-server.env.j2",
        dest=server_env_file,
        user="root",
        group="root",
        mode="600",
        env_items=env_items_for_server(
            {
                "ZOEA_LISTEN_ADDR": listen_addr,
                "PI_BIN_PATH": pi_bin_path,
                "PI_DEFAULT_ARGS": data("zoea_pi_default_args", "--mode rpc"),
                "ZOEA_PI_SESSION_DIR": server_sessions_dir,
                "ZOEA_WORKING_DIR": server_working_dir,
                "ZOEA_BEHIND_PROXY": "1",
                "STORE_DRIVER": data("zoea_store_driver", "sqlite"),
                "ZOEA_STORE_DSN": server_ZOEA_STORE_DSN,
                "AUTH_API_KEYS": data("zoea_auth_api_keys", ""),
                "AUTH_JWKS_URL": data("zoea_auth_jwks_url", ""),
                "AUTH_JWT_ISSUER": data("zoea_auth_jwt_issuer", ""),
                "AUTH_JWT_AUDIENCE": data("zoea_auth_jwt_audience", ""),
                "HOME": run_home,
                "ZOEA_CORE_PATH": zoea_core_dir,
                **extra_env,
            }
        ),
    )

    server_unit = files.template(
        name="Render zoea-server systemd unit",
        src="templates/zoea-server.service.j2",
        dest=server_unit_file,
        user="root",
        group="root",
        mode="644",
        instance_name=instance_name,
        run_user=run_user,
        run_group=run_group,
        working_directory=root_dir,
        env_file=server_env_file,
        exec_start=server_binary_dest,
    )

    systemd.daemon_reload(
        name="Reload systemd daemon for zoea-server",
        _if=server_unit.did_change,
    )

    systemd.service(
        name="Enable and start zoea-server",
        service=server_service_name,
        running=True,
        enabled=True,
    )

    restart_server = systemd.service(
        name="Restart zoea-server when configuration changes",
        service=server_service_name,
        running=True,
        restarted=True,
        _if=lambda: (
            server_binary.did_change()
            or server_env.did_change()
            or server_unit.did_change()
            or zoea_tools_unpack.did_change()
            or zoea_core_sync.did_change()
        ),
    )

if web_enabled:
    files.directory(
        name="Ensure zoea-web-ui root exists",
        path=web_root,
        user=run_user,
        group=run_group,
        mode="755",
    )
    files.sync(
        name="Sync zoea-web-ui assets",
        src=WEB_DIST_SRC,
        dest=web_root,
        user=run_user,
        group=run_group,
        delete=True,
    )

nginx_site = files.template(
    name="Render nginx site for Zoea",
    src="templates/nginx-site.conf.j2",
    dest=nginx_site_available,
    user="root",
    group="root",
    mode="644",
    server_names=server_names,
    client_max_body_size=client_max_body_size,
    api_upstream=api_upstream,
    web_enabled=web_enabled,
    web_root=web_root,
    nginx_listen_port=nginx_listen_port,
)

nginx_site_link = files.link(
    name="Enable Zoea nginx site",
    path=nginx_site_enabled,
    target=nginx_site_available,
)

default_nginx_site = files.link(
    name="Disable default nginx site",
    path="/etc/nginx/sites-enabled/default",
    present=False,
)

server.shell(
    name="Validate nginx configuration",
    commands=["nginx -t"],
    _if=lambda: nginx_site.did_change() or nginx_site_link.did_change() or default_nginx_site.did_change(),
)

systemd.service(
    name="Ensure nginx is running",
    service="nginx",
    running=True,
    enabled=True,
)

systemd.service(
    name="Reload nginx when site changes",
    service="nginx",
    running=True,
    reloaded=True,
    _if=lambda: nginx_site.did_change() or nginx_site_link.did_change() or default_nginx_site.did_change(),
)
