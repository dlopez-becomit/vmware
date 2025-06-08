"""Helper to request a detailed report from OpenAI or Azure OpenAI."""

from typing import Optional

from openai_connector import configure_openai, fetch_completion


def generate_detailed_report(summary: str, api_key: str, model: str,
                             api_type: Optional[str] = None,
                             api_base: Optional[str] = None,
                             api_version: Optional[str] = None,
                             config_file: Optional[str] = None) -> str:
    """Generates a professional VMware report using OpenAI or Azure OpenAI.

    Parameters
    ----------
    summary : str
        Short summary with the relevant findings.
    api_key : str
        OpenAI API key.
    model : str
        Model name or deployment to use.
    api_type : str, optional
        ``"openai"`` or ``"azure"``. If ``None`` the value is taken from the
        environment or configuration file.
    api_base : str, optional
        Azure OpenAI endpoint URL. Ignored for the ``openai`` type.
    api_version : str, optional
        Azure OpenAI API version.
    config_file : str, optional
        Path to a JSON file with the configuration parameters.

    Returns
    -------
    str
        Full report text returned by the language model.
    """
    configure_openai(
        api_key=api_key,
        api_type=api_type,
        api_base=api_base,
        api_version=api_version,
        model=model,
        config_file=config_file,
    )

    messages = [
        {
            "role": "system",
            "content": "Eres un experto en VMware. Debes redactar un informe profesional."
        },
        {
            "role": "user",
            "content": f"A partir del siguiente resumen genera un informe completo:\n{summary}"
        }
    ]

    return fetch_completion(messages, model)
