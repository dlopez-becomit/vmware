"""Sección de seguridad del informe detallado."""

from openai_connector import fetch_completion

INTRO = (
    "Esta sección evalúa los aspectos de seguridad de la infraestructura VMware. "
    "A continuación se añadirá el análisis generado por IA."
)

PROMPT_TEMPLATE = (
    "Eres un experto en VMware. Debes redactar un informe profesional "
    "sobre la seguridad usando los siguientes datos:\n{data}"
)

def generate(data, model=None):
    """Genera el texto detallado para la sección de seguridad."""
    prompt = PROMPT_TEMPLATE.format(data=data)
    messages = [
        {"role": "system", "content": "Eres un experto en VMware. Debes redactar un informe profesional."},
        {"role": "user", "content": prompt},
    ]
    return fetch_completion(messages, model)
