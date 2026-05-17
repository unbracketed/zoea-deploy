# Shared defaults for exe.dev VMs.

ssh_user = "exedev"
_sudo = True

zoea_components = ["server", "web"]
zoea_instance_name = None
zoea_root_dir = "/opt/zoea"
zoea_run_user = "exedev"
zoea_run_group = "exedev"
zoea_run_home = "/home/exedev"

zoea_server_host = "127.0.0.1"
zoea_server_port = 14004
zoea_server_service_name = None
zoea_server_working_dir = ""
zoea_api_upstream = None
zoea_server_names = []
zoea_client_max_body_size = "20m"

zoea_pi_bin_path = "pi"
zoea_pi_default_args = "--mode rpc"
zoea_agent_runtime_dir = None
zoea_auth_api_keys = ""
zoea_auth_jwks_url = ""
zoea_auth_jwt_issuer = ""
zoea_auth_jwt_audience = ""
zoea_store_driver = "sqlite"
zoea_extra_env = {}
