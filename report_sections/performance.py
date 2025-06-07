"""Sección de rendimiento del informe detallado."""

from openai_connector import configure_openai, fetch_completion

INTRO = (
    "Esta sección analiza el rendimiento de los hosts y máquinas virtuales. "
    "A continuación se añadirá el análisis generado por IA."
)

PROMPT_TEMPLATE = (
    "Eres un experto en VMware. Debes redactar un informe profesional "
    "sobre el rendimiento usando los siguientes datos:\n{data}"
)

def generate(data, model=None):
    """Genera el texto detallado para la sección de rendimiento."""
    configure_openai()
    prompt = PROMPT_TEMPLATE.format(data=data)
    messages = [
        {"role": "system", "content": "Eres un experto en VMware. Debes redactar un informe profesional."},
        {"role": "user", "content": prompt},
    ]
    return fetch_completion(messages, model)
