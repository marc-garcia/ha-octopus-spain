import importlib.util
from pathlib import Path
import pytest
from cryptography.fernet import Fernet

spec = importlib.util.spec_from_file_location("credentials", Path(__file__).parents[1] / "custom_components/octopus_spain/credentials.py")
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)


@pytest.fixture
def key(tmp_path):
    p = tmp_path / "key"
    p.write_bytes(Fernet.generate_key())
    p.chmod(0o600)
    return p


def test_random_roundtrip(key):
    a = c.encrypt_credentials("person", "secret-demo", key)
    b = c.encrypt_credentials("person", "secret-demo", key)
    assert a != b and "secret-demo" not in str(a)
    assert c.decrypt_credentials(a, key) == ("person", "secret-demo")


def test_wrong_key(key):
    a = c.encrypt_credentials("person", "secret-demo", key)
    key.write_bytes(Fernet.generate_key())
    with pytest.raises(c.CredentialError) as e:
        c.decrypt_credentials(a, key)
    assert "secret-demo" not in str(e.value)


def test_tampering(key):
    a = c.encrypt_credentials("person", "secret-demo", key)
    s = a[c.ENCRYPTED]
    a[c.ENCRYPTED] = s[:20] + ("A" if s[20] != "A" else "B") + s[21:]
    with pytest.raises(c.CredentialError):
        c.decrypt_credentials(a, key)


@pytest.mark.parametrize("mode", [0o644, 0o640, 0o604, 0o666])
def test_key_permissions(key, mode):
    key.chmod(mode)
    with pytest.raises(c.CredentialError):
        c.encrypt_credentials("a", "b", key)


def test_missing_key(key):
    key.unlink()
    with pytest.raises(c.CredentialError):
        c.encrypt_credentials("a", "b", key)
    assert not key.exists()


def test_symlink(key, tmp_path):
    p = tmp_path / "link"
    p.symlink_to(key)
    with pytest.raises(c.CredentialError):
        c.encrypt_credentials("a", "b", p)


def test_invalid_key(key):
    key.write_bytes(b"bad")
    with pytest.raises(c.CredentialError):
        c.encrypt_credentials("a", "b", key)


def test_migration(key):
    original = {"email": "old", "password": "old-secret", "keep": 4}
    options = {"email": "new", "password": "new-secret", "option": 7}
    d, o = c.migrate_credentials(original, options, key)
    assert c.decrypt_credentials(d, key) == ("new", "new-secret") and d["keep"] == 4 and o == {"option": 7}
    assert "email" not in d and "password" not in d
    assert original["password"] == "old-secret" and options["password"] == "new-secret"


def test_failed_migration(key):
    d = {"email": "a", "password": "b"}
    key.unlink()
    with pytest.raises(c.CredentialError):
        c.migrate_credentials(d, {}, key)
    assert d == {"email": "a", "password": "b"}


def test_new_ciphertext_options(key):
    a = c.encrypt_credentials("old", "a", key)
    b = c.encrypt_credentials("new", "b", key)
    d, o = c.migrate_credentials(a, b, key)
    assert c.decrypt_credentials(d, key) == ("new", "b") and o == {}


def test_no_plaintext_fallback(key):
    with pytest.raises(c.CredentialError):
        c.decrypt_credentials({"email": "a", "password": "b"}, key)


def test_invalid_payload(key):
    token = c._cipher(key).encrypt(b'{"email":"a","password":null}').decode()
    with pytest.raises(c.CredentialError):
        c.decrypt_credentials({c.FORMAT: 1, c.ENCRYPTED: token}, key)


def test_wrong_owner(key, monkeypatch):
    monkeypatch.setattr(c.os, "geteuid", lambda: key.stat().st_uid + 1)
    with pytest.raises(c.CredentialError):
        c.encrypt_credentials("a", "b", key)


def test_fifo(tmp_path):
    p = tmp_path / "fifo"
    c.os.mkfifo(p, 0o600)
    with pytest.raises(c.CredentialError):
        c.encrypt_credentials("a", "b", p)


def test_encrypted_options_override_stale_plaintext(key):
    legacy = {"email": "old", "password": "old-secret"}
    options = c.encrypt_credentials("new", "new-secret", key)
    data, clean_options = c.migrate_credentials(legacy, options, key)
    assert c.decrypt_credentials(data, key) == ("new", "new-secret")
    assert "password" not in data and clean_options == {}


def test_bad_encrypted_options_never_fall_back_to_plaintext(key):
    legacy = {"email": "old", "password": "old-secret"}
    options = {c.FORMAT: 1, c.ENCRYPTED: "broken"}
    with pytest.raises(c.CredentialError):
        c.migrate_credentials(legacy, options, key)


@pytest.mark.parametrize("mode", [0o100, 0o700, 0o1600])
def test_executable_or_special_key_modes_rejected(key, mode):
    key.chmod(mode)
    with pytest.raises(c.CredentialError):
        c.encrypt_credentials("a", "b", key)
