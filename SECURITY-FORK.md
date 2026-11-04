# Octopus Spain: separately keyed credential encryption

Based on upstream v1.4.0. This fork retains the `octopus_spain` domain and entity IDs. It replaces the upstream integration; do not install both. No account credentials or encryption key are included in this repository.

## Protection and limits

Email and password are stored together as an authenticated Fernet ciphertext in HA config entries. The key is read only from `/run/secrets/octopus_spain_credential_key`. No key is generated automatically; missing, invalid, shared-permission or symlink keys cause a failure, never a plaintext fallback. Both initial configuration and options save ciphertext; options do not return decrypted defaults to the browser.

This protects configuration files and HA backups copied **without the key**. It does not protect against a compromised HA process, another malicious custom integration, a NAS administrator, memory inspection or a backup containing both config and key. HA must decrypt in memory to authenticate with Octopus. Browser-to-HA transport is unchanged: use HTTPS or a trusted encrypted connection for the input form. Network calls to Octopus are unchanged.

Existing plaintext credentials migrate through the HA config-entry API at version 1 → 2. Migration preserves the old entry on failure and removes plaintext fields from both data and options on success. It cannot erase older backups, filesystem snapshots, disk history or previously exported files. Do not delete recovery copies casually; treat them as secrets. Version downgrade requires restoring the appropriate previous configuration or reconfiguring the upstream integration.

## Deployment on HA Container

1. Back up the existing integration code and HA configuration before replacing it.
2. Create a dedicated key directory on the host, **outside the volume mapped to `/config`**, with restrictive permissions. Run `python tools/create_credential_key.py /path/to/key` as the user running HA. For this NAS, HA currently runs as root: the key must be root-owned and mode 0400 or 0600.
3. Keep a separate protected recovery copy of the key (for example, a password manager). A configuration backup without this key cannot recover the Octopus credentials; re-entering credentials with a new key is the alternative. Exclude the live key directory from ordinary config backups; whole-NAS backups may still contain it.
4. Add this read-only bind mount to the **existing** HA container definition, preserving its other settings:

   ```yaml
   volumes:
     - /your/separate/key/path:/run/secrets/octopus_spain_credential_key:ro
   ```

5. Replace `custom_components/octopus_spain` with this fork, retain the same domain, recreate HA with the additional mount, and verify the key is available before configuration. Do not run the upstream and this fork simultaneously or let HACS replace this fork with upstream updates.
6. Configure Octopus in HA. On migration, inspect **field names only** to confirm `email` and `password` are absent from data/options; never print their values. Verify the entry loads and sensors update. Verify encrypted HA backups omit the external key mount.

An existing account is not necessary to run the local crypto tests:

```sh
python -m venv .venv
.venv/bin/pip install cryptography pytest
.venv/bin/pytest -q -c /dev/null tests/test_secure_credentials_standalone.py
```

## Validation status

17 tests cover randomized encryption, round-trip, wrong key, ciphertext tampering, insecure key modes, missing/invalid/symlink/FIFO keys, wrong key owner, invalid decrypted payload, legacy migration, option precedence and fail-closed behavior. Python compilation and targeted lint checks pass. End-to-end HA deployment and real Octopus authentication remain to be validated; local tests are not a security certification.

The encryption module uses `cryptography`, already supplied by Home Assistant Core. The fork introduces no telemetry, additional network destination or external credential service. Existing account data in sensor attributes and HA history is outside this credential-encryption change.
