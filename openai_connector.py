"""Funciones auxiliares para conectar con OpenAI y Azure OpenAI."""

import os
import openai


def configure_openai(api_key=None, api_type=None, api_base=None, api_version=None):
    """Configura la librería ``openai`` para usar OpenAI o Azure OpenAI."""
    openai.api_key = api_key or os.getenv("OPENAI_API_KEY")
    api_type = api_type or os.getenv("OPENAI_API_TYPE", "openai")
    if api_type == "azure":
        openai.api_type = "azure"
        openai.api_base = api_base or os.getenv("OPENAI_API_BASE")
        openai.api_version = api_version or os.getenv("OPENAI_API_VERSION")
    else:
        openai.api_type = "openai"


def fetch_completion(messages, model=None):
    """Envía las ``messages`` al servicio configurado y devuelve la respuesta."""
    model = model or os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
    response = openai.ChatCompletion.create(model=model, messages=messages)
    return response["choices"][0]["message"]["content"]
