"""Store the Microsoft OAuth client secret in macOS Keychain without printing it."""

from __future__ import annotations

import getpass
import json
import subprocess

CLIENT_ID = "dbde8708-816a-46d7-a161-ad1a1a6be55d"
SERVICE = "axiom.ai-delivery-platform.microsoft.oauth-client"


def main() -> None:
    secret = getpass.getpass("Microsoft client secret VALUE (hidden): ").strip()
    if len(secret) < 8:
        raise SystemExit("Secret was empty or unexpectedly short; nothing changed.")
    payload = json.dumps({"client_id": CLIENT_ID, "client_secret": secret})
    subprocess.run(
        [
            "security",
            "add-generic-password",
            "-U",
            "-a",
            CLIENT_ID,
            "-s",
            SERVICE,
            "-w",
            payload,
        ],
        check=True,
        capture_output=True,
        timeout=10,
    )
    secret = payload = ""
    print("Microsoft OAuth client configuration stored in macOS Keychain.")


if __name__ == "__main__":
    main()
