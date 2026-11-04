"""Create an owner-only Fernet key; never overwrite or print a key."""

import base64
import os
import secrets
import sys
from pathlib import Path

if len(sys.argv) != 2:
    raise SystemExit("Usage: python create_credential_key.py /secure/path/octopus_spain_credential_key")
path = Path(sys.argv[1])
fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
with os.fdopen(fd, "wb") as stream:
    stream.write(base64.urlsafe_b64encode(secrets.token_bytes(32)) + b"\n")
    stream.flush()
    os.fsync(stream.fileno())
print("Credential key created. Its contents were not printed.")
