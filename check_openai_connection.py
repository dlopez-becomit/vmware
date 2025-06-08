#!/usr/bin/env python3
"""Prueba sencilla de conexión con OpenAI o Azure OpenAI."""

from openai_connector import configure_openai, fetch_completion


def main() -> None:
    """Muestra si es posible obtener una respuesta."""
    configure_openai(verbose=True)
    try:
        text = fetch_completion([
            {"role": "user", "content": "Decir hola"}
        ])
    except Exception as exc:  # pragma: no cover - external call
        print("ERROR:", exc)
    else:
        print("Conexión OK. Respuesta truncada:")
        print(text[:200])


if __name__ == "__main__":
    main()
