"""Funciones auxiliares para conectar con OpenAI y Azure OpenAI."""

import os
import json
import openai

_DEFAULT_MODEL = None


def apply_azure_env_vars(force=False, verbose=False):
    """Map Azure-specific variables to the names expected by ``openai``."""
    found = False
    key = os.getenv("AZURE_OPENAI_KEY")
    if key:
        os.environ.setdefault("OPENAI_API_KEY", key)
        found = True
        if verbose:
            print("Usando AZURE_OPENAI_KEY")
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    if endpoint:
        os.environ.setdefault("OPENAI_API_BASE", endpoint)
        found = True
        if verbose:
            print(f"Endpoint: {endpoint}")
    version = os.getenv("AZURE_OPENAI_VERSION")
    if version:
        os.environ.setdefault("OPENAI_API_VERSION", version)
        found = True
        if verbose:
            print(f"Versión: {version}")
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT")
    if deployment:
        os.environ.setdefault("OPENAI_MODEL", deployment)
        found = True
        if verbose:
            print(f"Deployment: {deployment}")
    if force or found:
        os.environ["OPENAI_API_TYPE"] = "azure"


def load_openai_config(path=None, verbose=False):
    """Carga la configuración de OpenAI desde un archivo JSON."""
    config_path = path or os.getenv("OPENAI_CONFIG_FILE", "openai_config.json")
    if not os.path.isfile(config_path):
        if verbose:
            print(f"Archivo de configuración {config_path} no encontrado")
        return {}
    try:
        with open(config_path, encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception as exc:
        if verbose:
            print(f"No se pudo cargar {config_path}: {exc}")
        return {}
    if verbose:
        print(f"Configuración cargada desde {config_path}")
    return cfg


def configure_openai(api_key=None, api_type=None, api_base=None, api_version=None,
                     model=None, config_file=None, verbose=False):
    """Configura la librería ``openai`` para usar OpenAI o Azure OpenAI."""
    if api_type == "azure" or os.getenv("OPENAI_API_TYPE") == "azure":
        apply_azure_env_vars(force=True, verbose=verbose)
    else:
        apply_azure_env_vars(verbose=verbose)
    cfg = load_openai_config(config_file, verbose=verbose)

    key = api_key or os.getenv("OPENAI_API_KEY") or cfg.get("api_key")
    openai.api_key = key
    if verbose and not key:
        print("Advertencia: OPENAI_API_KEY no definido")

    api_type = api_type or os.getenv("OPENAI_API_TYPE") or cfg.get("api_type", "openai")
    if api_type == "azure":
        openai.api_type = "azure"
        openai.api_base = api_base or os.getenv("OPENAI_API_BASE") or cfg.get("api_base")
        openai.api_version = api_version or os.getenv("OPENAI_API_VERSION") or cfg.get("api_version")
        if verbose and (not openai.api_base or not openai.api_version):
            print("Advertencia: OPENAI_API_BASE o OPENAI_API_VERSION no definidos para Azure")
    else:
        openai.api_type = "openai"

    global _DEFAULT_MODEL
    _DEFAULT_MODEL = model or os.getenv("OPENAI_MODEL") or cfg.get("model")
    if verbose:
        print(f"API type: {openai.api_type}")
        if openai.api_type == "azure":
            print(f"Endpoint: {openai.api_base}")
            print(f"Versión: {openai.api_version}")
            print(f"Deployment/Modelo: {_DEFAULT_MODEL}")
        else:
            print(f"Modelo: {_DEFAULT_MODEL}")


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
