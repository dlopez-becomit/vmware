"""Funciones auxiliares para conectar con OpenAI y Azure OpenAI."""

import os
import json
import openai

_DEFAULT_MODEL = None


def load_openai_config(path=None):
    """Carga la configuración de OpenAI desde un archivo JSON."""
    config_path = path or os.getenv("OPENAI_CONFIG_FILE", "openai_config.json")
    if not os.path.isfile(config_path):
        return {}
    try:
        with open(config_path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def configure_openai(api_key=None, api_type=None, api_base=None, api_version=None, model=None, config_file=None):
    """Configura la librería ``openai`` para usar OpenAI o Azure OpenAI."""
    cfg = load_openai_config(config_file)

    key = api_key or os.getenv("OPENAI_API_KEY") or cfg.get("api_key")
    openai.api_key = key

    api_type = api_type or os.getenv("OPENAI_API_TYPE") or cfg.get("api_type", "openai")
    if api_type == "azure":
        openai.api_type = "azure"
        openai.api_base = api_base or os.getenv("OPENAI_API_BASE") or cfg.get("api_base")
        openai.api_version = api_version or os.getenv("OPENAI_API_VERSION") or cfg.get("api_version")
    else:
        openai.api_type = "openai"

    global _DEFAULT_MODEL
    _DEFAULT_MODEL = model or os.getenv("OPENAI_MODEL") or cfg.get("model")


def fetch_completion(messages, model=None):
    """Envía las ``messages`` al servicio configurado y devuelve la respuesta."""
    if model is None:
        model = _DEFAULT_MODEL or os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
    params = {"messages": messages}
    # Azure OpenAI uses the ``engine`` or ``deployment_id`` parameter instead of
    # ``model``. Detect the configured API type to build the correct call.
    if getattr(openai, "api_type", "openai") == "azure":
        params["engine"] = model
    else:
        params["model"] = model
    response = openai.ChatCompletion.create(**params)
    return response["choices"][0]["message"]["content"]
