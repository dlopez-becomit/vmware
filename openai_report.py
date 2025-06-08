"""Helper to request a detailed report from OpenAI or Azure OpenAI."""

from openai_connector import configure_openai, fetch_completion


def generate_detailed_report(summary: str, api_key: str, model: str) -> str:
    """Generates a professional VMware report using OpenAI or Azure OpenAI.

    Parameters
    ----------
    summary : str
        Short summary with the relevant findings.
    api_key : str
        OpenAI API key.
    model : str
        Model name to use (e.g. 'gpt-3.5-turbo' or 'gpt-4').

    Returns
    -------
    str
        Full report text returned by the language model.
    """
    configure_openai(api_key=api_key, model=model)

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
