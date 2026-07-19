import argparse
import sys

from shared_token_credentials import SERVICE_NAME, USERNAME


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Guarda el token compartido de AgroDrone en el keyring seguro del sistema"
    )
    parser.add_argument("token", nargs="?", help="Token a guardar. Si se omite, se genera uno aleatorio.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    token = args.token

    if not token:
        import secrets
        token = secrets.token_urlsafe(24)
        print(f"No se pasó un token; se generó uno nuevo: {token}")
        print("Guárdalo también en .env.local del frontend como VITE_SHARED_TOKEN "
              "(es el único lugar donde SÍ hace falta un archivo, porque el navegador "
              "no tiene acceso al keyring del sistema).")

    try:
        import keyring
    except Exception as exc:
        print(f"No se pudo importar keyring: {exc}")
        print("Instálalo primero con: python -m pip install keyring")
        return 1

    try:
        keyring.set_password(SERVICE_NAME, USERNAME, token)
    except Exception as exc:
        print(f"No se pudo guardar el token: {exc}")
        return 1

    print(f"Token guardado correctamente en el almacén de claves ({SERVICE_NAME}/{USERNAME}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())