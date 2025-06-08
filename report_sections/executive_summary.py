"""Sección de resumen ejecutivo del informe detallado."""

from openai_connector import fetch_completion

INTRO = (
    "Esta sección ofrece un resumen ejecutivo del informe. "
    "A continuación se añadirá el análisis generado por IA."
)

PROMPT_TEMPLATE = (
    "Eres un experto en VMware. Debes redactar un resumen ejecutivo "
    "utilizando los siguientes datos:\n{data}"
)

def generate(data, model=None):
    """Genera el texto detallado para el resumen ejecutivo."""
    prompt = PROMPT_TEMPLATE.format(data=data)
    messages = [
        {"role": "system", "content": "Eres un experto en VMware. Debes redactar un informe profesional."},
        {"role": "user", "content": prompt},
    ]
    return fetch_completion(messages, model)
