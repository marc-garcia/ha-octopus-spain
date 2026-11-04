"""Authenticated encryption with a separately mounted, owner-only key.

The key is deliberately never generated or stored inside HA's /config.
This protects offline configuration copies, not a compromised HA process.
"""

import json
import os
from pathlib import Path
import stat

from cryptography.fernet import Fernet, InvalidToken

KEY_PATH = Path("/run/secrets/octopus_spain_credential_key")
ENCRYPTED = "encrypted_credentials"
FORMAT = "credential_format"


class CredentialError(Exception):
    """Safe error message that never contains credential values."""


def _cipher(path: Path = KEY_PATH) -> Fernet:
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as key_file:
            meta = os.fstat(key_file.fileno())
            if not stat.S_ISREG(meta.st_mode) or meta.st_mode & 0o077:
                raise CredentialError("Credential key must be an owner-only regular file (0400 or 0600).")
            if meta.st_uid != os.geteuid():
                raise CredentialError("Credential key must belong to the Home Assistant process user.")
            key = key_file.read(65).strip()
        return Fernet(key)
    except (OSError, ValueError):
        raise CredentialError("External credential key is missing, unreadable or invalid.") from None


def encrypt_credentials(email: str, password: str, path: Path = KEY_PATH) -> dict:
    if not isinstance(email, str) or not email or not isinstance(password, str) or not password:
        raise CredentialError("Both credentials are required.")
    raw = json.dumps({"email": email, "password": password}).encode()
    return {FORMAT: 1, ENCRYPTED: _cipher(path).encrypt(raw).decode("ascii")}


def decrypt_credentials(data: dict, path: Path = KEY_PATH) -> tuple[str, str]:
    try:
        if data.get(FORMAT) != 1:
            raise CredentialError("Unsupported credential format.")
        raw = _cipher(path).decrypt(data[ENCRYPTED].encode("ascii"))
        creds = json.loads(raw)
        email, password = creds["email"], creds["password"]
        if not isinstance(email, str) or not email or not isinstance(password, str) or not password:
            raise ValueError
        return email, password
    except (InvalidToken, KeyError, ValueError, TypeError, AttributeError):
        raise CredentialError("Credentials cannot be decrypted with the external key.") from None


def migrate_credentials(data: dict, options: dict, path: Path = KEY_PATH) -> tuple[dict, dict]:
    """Return new mappings; do not mutate or persist anything on failure."""
    merged = {**data, **options}
    if "email" in merged and "password" in merged:
        encrypted = encrypt_credentials(merged["email"], merged["password"], path)
    else:
        decrypt_credentials(merged, path)  # Prove the key works before removing anything.
        encrypted = {FORMAT: merged[FORMAT], ENCRYPTED: merged[ENCRYPTED]}
    secret_keys = {"email", "password", FORMAT, ENCRYPTED}
    return (
        {**{k: v for k, v in data.items() if k not in secret_keys}, **encrypted},
        {k: v for k, v in options.items() if k not in secret_keys},
    )
