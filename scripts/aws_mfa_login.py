#!/usr/bin/env python3
"""
aws_mfa_login.py — Refresh the [mfa] AWS profile using a TOTP code.

Calls sts:GetSessionToken with the Corey02 MFA device and writes
temporary credentials to the [mfa] profile in ~/.aws/credentials.
Session lasts 24 hours (86400s).

Usage:
  python3 scripts/aws_mfa_login.py              # prompts for TOTP code
  python3 scripts/aws_mfa_login.py --code 123456
  python3 scripts/aws_mfa_login.py --check       # just check if session valid
"""

import argparse
import configparser
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.errors import fail, require_tool

CREDENTIALS_FILE = Path.home() / ".aws" / "credentials"
LONG_TERM_PROFILE = "<YOUR_EMAIL>"
MFA_PROFILE = "mfa"
MFA_SERIAL = "arn:aws:iam::496800238012:mfa/Corey02"
DURATION = 86400  # 24 hours


def check_session() -> bool:
    """Return True if the [mfa] profile has a valid session."""
    result = subprocess.run(
        ["aws", "sts", "get-caller-identity", "--profile", MFA_PROFILE],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        identity = json.loads(result.stdout)
        print(f"  ✓ Active session: {identity.get('Arn', 'unknown')}")
        return True
    return False


def refresh_session(code: str) -> bool:
    """Use TOTP code to get new STS session and write to [mfa] profile."""
    result = subprocess.run(
        [
            "aws", "sts", "get-session-token",
            "--profile", LONG_TERM_PROFILE,
            "--serial-number", MFA_SERIAL,
            "--token-code", code.strip(),
            "--duration-seconds", str(DURATION),
            "--output", "json",
        ],
        capture_output=True, text=True
    )

    if result.returncode != 0:
        msg = result.stderr.strip()
        if "invalid MFA one time pass code" in msg:
            print("  ❌ Invalid TOTP code. Two common causes:")
            print("     1. Code already used — wait for your authenticator to show a NEW code and retry")
            print("     2. Wrong authenticator entry — make sure you're reading the 'Corey02' account")
        else:
            print(f"  ❌ STS call failed: {msg}")
        return False

    creds = json.loads(result.stdout)["Credentials"]

    config = configparser.ConfigParser()
    config.read(CREDENTIALS_FILE)

    if MFA_PROFILE not in config:
        config[MFA_PROFILE] = {}

    config[MFA_PROFILE]["aws_access_key_id"] = creds["AccessKeyId"]
    config[MFA_PROFILE]["aws_secret_access_key"] = creds["SecretAccessKey"]
    config[MFA_PROFILE]["aws_session_token"] = creds["SessionToken"]

    with open(CREDENTIALS_FILE, "w") as f:
        config.write(f)

    print(f"  ✓ [mfa] profile refreshed — valid until {creds['Expiration']}")
    return True


def main():
    parser = argparse.ArgumentParser(description="Refresh AWS MFA session")
    parser.add_argument("--code", help="6-digit TOTP code")
    parser.add_argument("--check", action="store_true", help="Check session validity only")
    args = parser.parse_args()

    require_tool("aws", install="pip install awscli  OR  brew install awscli")
    if args.check:
        if check_session():
            sys.exit(0)
        else:
            fail(
                "No valid MFA session",
                causes=["Session expired or was never established"],
                try_=["Run python3 scripts/aws_mfa_login.py --code <TOTP> to refresh"],
            )

    if check_session():
        print("  ℹ  Session still valid — no refresh needed.")
        return

    code = args.code or input("  Enter Corey02 TOTP code: ").strip()
    if not code:
        fail(
            "No TOTP code provided",
            causes=["User pressed Enter without entering a code"],
            try_=["Rerun: python3 scripts/aws_mfa_login.py --code 123456",
                  "Open your Corey02 authenticator and enter the 6-digit code"],
        )

    refresh_session(code)


if __name__ == "__main__":
    main()
