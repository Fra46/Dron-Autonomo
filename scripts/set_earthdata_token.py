import argparse
import os
import sys


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Store your Earthdata token securely in the system keyring")
    parser.add_argument("token", help="Earthdata token to store")
    parser.add_argument("--service", default="earthdata", help="Keyring service name (default: earthdata)")
    parser.add_argument("--username", default="token", help="Keyring username (default: token)")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    token = args.token

    if not token:
        print("No se encontró un token. Pásalo como argumento.")
        print("Ejemplo: python scripts/set_earthdata_token.py \"TU_TOKEN\"")
        return 1

    try:
        import keyring
    except Exception as exc:
        print(f"No se pudo importar keyring: {exc}")
        print("Instálalo primero con: python -m pip install keyring")
        return 1

    try:
        keyring.set_password(args.service, args.username, token)
    except Exception as exc:
        print(f"No se pudo guardar el token: {exc}")
        return 1

    print(f"Token guardado correctamente en el almacén de claves ({args.service}/{args.username}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
