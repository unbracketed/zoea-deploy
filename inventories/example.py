# Copy this file to production.py/staging.py and replace the hostnames.

all = [
    (
        "zoea-full-1.exe.xyz",
        {
            "zoea_components": ["server", "web"],
            "zoea_server_names": ["zoea-full-1.exe.xyz"],
        },
    ),
    (
        "zoea-api-1.exe.xyz",
        {
            "zoea_components": ["server"],
            "zoea_server_names": ["zoea-api-1.exe.xyz"],
        },
    ),
    (
        "zoea-web-1.exe.xyz",
        {
            "zoea_components": ["web"],
            "zoea_server_names": ["zoea-web-1.exe.xyz"],
            "zoea_api_upstream": "https://zoea-api-1.exe.xyz",
        },
    ),
]
