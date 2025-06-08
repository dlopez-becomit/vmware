"""Sección de disponibilidad del informe detallado."""

from openai_connector import fetch_completion

INTRO = (
    "Esta sección revisa los aspectos de alta disponibilidad y resiliencia. "
    "A continuación se añadirá el análisis generado por IA."
)

PROMPT_TEMPLATE = (
    "Eres un experto en VMware. Debes redactar un informe profesional "
    "sobre la disponibilidad usando los siguientes datos:\n{data}"
)

def generate(data, model=None):
    """Genera el texto detallado para la sección de disponibilidad."""
    prompt = PROMPT_TEMPLATE.format(data=data)
    messages = [
        {"role": "system", "content": "Eres un experto en VMware. Debes redactar un informe profesional."},
        {"role": "user", "content": prompt},
    ]
    return fetch_completion(messages, model)
