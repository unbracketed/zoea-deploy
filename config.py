from __future__ import annotations

import os
import shlex
from pathlib import Path

from pyinfra import local, logger

DEPLOY_DIR = Path(__file__).resolve().parent
REPO_ROOT = DEPLOY_DIR.parent
SERVER_DIR = REPO_ROOT / "zoea-server"
WEB_DIR = REPO_ROOT / "zoea-web-ui"
TOOLS_DIR = REPO_ROOT / "zoea-tools"
BUILD_DIR = DEPLOY_DIR / ".build"
SERVER_BUILD_DIR = BUILD_DIR / "zoea-server"
WEB_BUILD_DIR = BUILD_DIR / "zoea-web-ui"
TOOLS_BUILD_DIR = BUILD_DIR / "zoea-tools"
TOOLS_ARCHIVE = BUILD_DIR / "zoea-tools.tar.gz"
SERVER_BINARY = SERVER_BUILD_DIR / "zoea-server"

BUILD_SERVER = os.getenv("ZOEA_DEPLOY_BUILD_SERVER", "1") != "0"
BUILD_WEB = os.getenv("ZOEA_DEPLOY_BUILD_WEB", "1") != "0"
BUILD_TOOLS = os.getenv("ZOEA_DEPLOY_BUILD_TOOLS", "1") != "0"
NPM_INSTALL_CMD = os.getenv("ZOEA_DEPLOY_NPM_INSTALL", "npm ci")
TOOLS_NPM_INSTALL_CMD = os.getenv("ZOEA_DEPLOY_TOOLS_NPM_INSTALL", "npm ci --omit=dev --legacy-peer-deps")


def q(value: Path | str) -> str:
    return shlex.quote(str(value))


BUILD_DIR.mkdir(exist_ok=True)

if BUILD_SERVER:
    goos = os.getenv("ZOEA_DEPLOY_GOOS", "linux")
    goarch = os.getenv("ZOEA_DEPLOY_GOARCH", "amd64")
    logger.info(f"Building zoea-server locally (GOOS={goos} GOARCH={goarch})")
    SERVER_BUILD_DIR.mkdir(parents=True, exist_ok=True)
    local.shell(
        "cd {src} && env GOOS={goos} GOARCH={goarch} CGO_ENABLED=0 go build -o {out} ./cmd/server".format(
            src=q(SERVER_DIR),
            goos=q(goos),
            goarch=q(goarch),
            out=q(SERVER_BINARY),
        )
    )

if BUILD_WEB:
    logger.info("Building zoea-web-ui locally")
    WEB_BUILD_DIR.mkdir(parents=True, exist_ok=True)
    local.shell(
        "cd {src} && {install} && npm run build".format(
            src=q(WEB_DIR),
            install=NPM_INSTALL_CMD,
        )
    )
    local.shell(
        "rsync -a --delete {src} {dst}".format(
            src=q(f"{WEB_DIR / 'dist'}/"),
            dst=q(f"{WEB_BUILD_DIR}/"),
        )
    )

if BUILD_TOOLS:
    logger.info("Preparing zoea-tools package locally")
    TOOLS_BUILD_DIR.mkdir(parents=True, exist_ok=True)
    local.shell(
        "rsync -a --delete --exclude .git --exclude node_modules {src} {dst}".format(
            src=q(f"{TOOLS_DIR}/"),
            dst=q(f"{TOOLS_BUILD_DIR}/"),
        )
    )
    local.shell(
        "cd {src} && {install}".format(
            src=q(TOOLS_BUILD_DIR),
            install=TOOLS_NPM_INSTALL_CMD,
        )
    )
    local.shell(
        "tar -czf {archive} -C {src} .".format(
            archive=q(TOOLS_ARCHIVE),
            src=q(TOOLS_BUILD_DIR),
        )
    )
