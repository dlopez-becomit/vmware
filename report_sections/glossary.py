"""Sección de glosario del informe detallado."""

from openai_connector import fetch_completion

INTRO = (
    "Esta sección define los términos clave utilizados en el informe. "
    "A continuación se añadirá el análisis generado por IA."
)

PROMPT_TEMPLATE = (
    "Eres un experto en VMware. Debes crear un glosario breve utilizando "
    "los siguientes datos:\n{data}"
)

def generate(data, model=None):
    """Genera el texto detallado para el glosario."""
    prompt = PROMPT_TEMPLATE.format(data=data)
    messages = [
        {"role": "system", "content": "Eres un experto en VMware. Debes redactar un informe profesional."},
        {"role": "user", "content": prompt},
    ]
    return fetch_completion(messages, model)
