"""Secrets held in the operating system keyring and referenced from config.

A config value of the form ``keyring:<service>/<name>`` (or ``keyring:<name>``
for the default service) names a secret in the platform credential store:
Windows Credential Manager, macOS Keychain or the Secret Service on Linux.
The config file carries only the reference; the secret is read into memory
when runtime settings load.

Command line::

    python -m jarvis.secret_store set ha_token
    python -m jarvis.secret_store delete ha_token
"""
from __future__ import annotations

import argparse
import getpass
from typing import Any, Optional, Sequence

SECRET_PREFIX = "keyring:"
DEFAULT_SERVICE = "jarvis"


def _log(message: str) -> None:
    try:
        from .debug import debug_log

        debug_log(message, "secrets")
    except Exception:
        pass


def _keyring():
    import keyring

    return keyring


def is_secret_reference(value: Any) -> bool:
    """True when the value names a keyring secret rather than holding one."""
    return isinstance(value, str) and value.strip().startswith(SECRET_PREFIX)


def reference_for(name: str, service: str = DEFAULT_SERVICE) -> str:
    """The config value that refers to a stored secret."""
    return f"{SECRET_PREFIX}{service}/{name}"


def _parse_reference(reference: str) -> tuple[str, str]:
    target = reference.strip()[len(SECRET_PREFIX):].strip()
    service, separator, name = target.partition("/")
    if not separator:
        return DEFAULT_SERVICE, service
    return service or DEFAULT_SERVICE, name


def resolve_secret(value: Any) -> Any:
    """Return the secret a reference names; other values pass through.

    A reference that cannot be resolved yields an empty string, so the
    reference text is never sent anywhere as if it were a credential.
    """
    if not is_secret_reference(value):
        return value
    service, name = _parse_reference(value)
    if not name:
        _log("⚠️ secret reference has no name")
        return ""
    try:
        secret: Optional[str] = _keyring().get_password(service, name)
    except Exception as exc:
        _log(f"⚠️ keyring unavailable for {service}/{name}: {type(exc).__name__}")
        return ""
    if not secret:
        _log(f"⚠️ no secret stored for {service}/{name}")
        return ""
    return secret


def resolve_secrets(value: Any) -> Any:
    """Resolve every reference inside nested dicts and lists, without mutating the input."""
    if isinstance(value, dict):
        return {key: resolve_secrets(item) for key, item in value.items()}
    if isinstance(value, list):
        return [resolve_secrets(item) for item in value]
    return resolve_secret(value)


def set_secret(name: str, secret: str, service: str = DEFAULT_SERVICE) -> None:
    """Store a secret in the keyring."""
    _keyring().set_password(service, name, secret)


def delete_secret(name: str, service: str = DEFAULT_SERVICE) -> bool:
    """Remove a secret from the keyring. Returns False when nothing was removed."""
    try:
        _keyring().delete_password(service, name)
        return True
    except Exception:
        return False


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m jarvis.secret_store",
        description="Manage secrets Jarvis reads from the operating system keyring.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    for command, text in (("set", "Store a secret"), ("delete", "Remove a secret")):
        p = sub.add_parser(command, help=text)
        p.add_argument("name", help="Name of the secret, e.g. ha_token")
        p.add_argument("--service", default=DEFAULT_SERVICE, help="Keyring service name")
    args = parser.parse_args(argv)

    if args.command == "set":
        secret = getpass.getpass(f"🔑 Value for {args.name} (input hidden): ")
        if not secret.strip():
            print("❌ Nothing stored: the value was empty")
            return 1
        try:
            set_secret(args.name, secret.strip(), args.service)
        except Exception as exc:
            print(f"❌ Could not store the secret: {type(exc).__name__}")
            return 1
        print(f"✅ Stored {args.name} in the system keyring")
        print(f"   📝 Use this value in config.json: {reference_for(args.name, args.service)}")
        return 0

    if delete_secret(args.name, args.service):
        print(f"🗑️ Removed {args.name} from the system keyring")
        return 0
    print(f"❌ No secret named {args.name} was removed")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
