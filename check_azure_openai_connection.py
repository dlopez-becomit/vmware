#!/usr/bin/env python3
"""Prueba de conexión específica para Azure OpenAI."""

from openai_connector import configure_openai, fetch_completion
import os


def _apply_azure_env_vars() -> None:
    """Mapea variables de entorno específicas de Azure al formato esperado."""
    key = os.getenv("AZURE_OPENAI_KEY")
    if key:
        os.environ.setdefault("OPENAI_API_KEY", key)
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    if endpoint:
        os.environ.setdefault("OPENAI_API_BASE", endpoint)
    version = os.getenv("AZURE_OPENAI_VERSION")
    if version:
        os.environ.setdefault("OPENAI_API_VERSION", version)
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT")
    if deployment:
        os.environ.setdefault("OPENAI_MODEL", deployment)
    os.environ["OPENAI_API_TYPE"] = "azure"


def main() -> None:
    """Muestra si es posible obtener una respuesta desde Azure OpenAI."""
    _apply_azure_env_vars()
    configure_openai()
    try:
        text = fetch_completion([
            {"role": "user", "content": "Decir hola"}
        ])
    except Exception as exc:  # pragma: no cover - external call
        print("ERROR:", exc)
    else:
        print("Conexión Azure OpenAI OK. Respuesta truncada:")
        print(text[:200])


if __name__ == "__main__":
    main()
