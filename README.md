# VMware Health Check

Este repositorio incluye una herramienta escrita en Python que recopila información básica de seguridad y rendimiento de un vCenter o host ESXi.
Genera un informe HTML y, opcionalmente, un texto detallado empleando OpenAI o Azure OpenAI.

## Requisitos

- Python 3.8+
- Dependencias indicadas en `requirements.txt` (`pyvmomi`, `matplotlib`, `jinja2`)

## Instalación

1. Instale las dependencias ejecutando el script `setup.sh` o, si lo prefiere,
   instálelas manualmente:
   ```bash
   ./setup.sh  # instala automáticamente
   # o bien
   pip install -r requirements.txt
   ```
   Para comprobar que Jinja2 se instaló correctamente puede ejecutar:
   ```bash
   python -c "import jinja2"
   ```

2. Ejecute el script proporcionando los datos de conexión. Puede especificar opcionalmente un archivo de salida HTML:
```bash
python vmware_healthcheck.py --host <vcenter o esxi> --user <usuario> --password <contraseña> --output reporte.html
```

Para generar además un informe en texto (requiere haber definido `OPENAI_API_KEY`):
```bash
python vmware_healthcheck.py --host <vcenter o esxi> --user <usuario> --password <contraseña> --detailed-report informe.txt
```

   Si desea emplear una plantilla Jinja2 personalizada para el informe, coloque
   el archivo de plantilla en el directorio deseado y utilice la opción
   `--template` para indicar su ubicación. Puede indicar un nombre de plantilla
   diferente mediante `--template-file`:
   ```bash
python vmware_healthcheck.py --host <vcenter o esxi> --user <usuario> --password <contraseña> --output reporte.html --template /ruta/a/plantilla --template-file template_a.html
```
De forma predeterminada, `generate_report` buscará un archivo llamado `template.html` en el directorio especificado (o en el del script si no se indica ninguno). Este repositorio incluye uno con un diseño minimalista y
moderno listo para usar.
Para obtener un informe de texto detallado mediante la API de OpenAI exporte `OPENAI_API_KEY` y añada la opción `--detailed-report <archivo>`.
En sistemas Linux o macOS puede definirse así:
```bash
export OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxx
```
Si utiliza Azure OpenAI establezca además las variables `OPENAI_API_TYPE=azure`, `OPENAI_API_BASE` y `OPENAI_API_VERSION` con los valores de su servicio.
```bash
export OPENAI_API_TYPE=azure
export OPENAI_API_BASE=https://<tu-recurso>.openai.azure.com/
export OPENAI_API_VERSION=2023-05-15
export OPENAI_API_KEY=<clave>
```
En lugar de variables de entorno también puede crearse un archivo
`openai_config.json` con estos mismos campos. El script lo cargará
automáticamente si está presente (o si se indica la ruta en
`OPENAI_CONFIG_FILE`). Un ejemplo de su contenido es:
```json
{
  "api_key": "sk-xxxxxxxx",
  "api_type": "openai",
  "api_base": "",
  "api_version": "",
  "model": "gpt-3.5-turbo"
}
```
Para Azure también puede almacenarse la configuración en este archivo. Un
ejemplo sería:
```json
{
  "api_key": "<clave>",
  "api_type": "azure",
  "api_base": "https://<tu-recurso>.openai.azure.com/",
  "api_version": "2023-05-15",
  "model": "<deployment>"
}
```
Este repositorio incluye `openai_config_azure.json` como referencia.
Si se desea escoger explícitamente el tipo de servicio al ejecutar
`vmware_healthcheck.py`, puede indicarse mediante la opción
`--api-type`, que acepta los valores `openai` o `azure`. También es
posible especificar un archivo de configuración distinto con
`--openai-config <archivo>`.
Para verificar la configuración de OpenAI se incluye `check_openai_connection.py`.
Ejecútelo para confirmar que la clave y el endpoint son correctos:
```bash
python check_openai_connection.py
```
Si la conexión es válida se mostrará la respuesta generada por el servicio.
Para Azure OpenAI existe `check_azure_openai_connection.py`, que acepta las
variables `AZURE_OPENAI_KEY`, `AZURE_OPENAI_ENDPOINT`,
`AZURE_OPENAI_VERSION` y `AZURE_OPENAI_DEPLOYMENT` como alias de las variables
reconocidas por la librería `openai`.
```bash
python check_azure_openai_connection.py
```
Si no se indica un archivo de configuración concreto, el script buscará
automáticamente `openai_config_azure.json` en el directorio actual.
Si también se indica `--output`, el texto se incluirá al final del HTML.
Adicionalmente, se incluye `template_a.html`, una plantilla avanzada con un formato extendido y botones para exportar o imprimir el informe. Para utilizarla basta con indicar el directorio donde se encuentra mediante `--template` y pasar `--template-file template_a.html`.

También se ha añadido `template_a_detailed.html`, una versión ampliada que incorpora una sección **Análisis Detallado** con cuatro bloques de texto (Rendimiento, Almacenamiento, Seguridad y Disponibilidad). Dichos textos se generan con IA si se indica la opción `--detailed-report`.

De forma simplificada puede utilizarse `--extended-html`, que aplica automáticamente esta plantilla y habilita el informe detallado cuando se indica `--output`.

Para obtener un informe extendido en HTML utilice el nombre de esta plantilla y especifique dónde guardar el texto generado:

```bash
python vmware_healthcheck.py --host <vcenter o esxi> --user <usuario> --password <contraseña> \
  --output informe.html --template . --template-file template_a_detailed.html \
  --detailed-report report.txt
```
O bien utilizando la nueva opción:
```bash
python vmware_healthcheck.py --host <vcenter o esxi> --user <usuario> --password <contraseña> \
  --output informe.html --template . --extended-html
```

Asimismo se incluye `template_full.html`, una versión pensada para un informe completo con portada e índice.
Incluye 12 secciones: portada, resumen ejecutivo, introducción, resumen del entorno, análisis por categorías, indicadores de componentes, listados Top&nbsp;10, recomendaciones, conclusiones, glosario y anexos.
Puede emplearse fácilmente con:
```bash
python vmware_healthcheck.py --host <vcenter o esxi> --user <usuario> --password <contraseña> \
  --output informe.html --template . --full-html
```
Para obtener el mismo informe completamente en español puede utilizar `template_full_es.html` y la opción `--full-html-es`:
```bash
python vmware_healthcheck.py --host <vcenter o esxi> --user <usuario> --password <contraseña> \
  --output informe.html --template . --full-html-es
```
Las áreas de recomendaciones, conclusiones y glosario se generan con IA, por lo que debe configurarse OpenAI (variables de entorno o `openai_config.json`).

El archivo `template_a_detailed.html` incluye ahora un pequeño índice clicable
para navegar por las secciones principales del informe. Una vez generado el
HTML puede convertirse en PDF con vínculos internos utilizando el script
`html_to_pdf.py`:

```bash
python html_to_pdf.py informe.html reporte.pdf
```

Recuerde exportar `OPENAI_API_KEY` y, en el caso de Azure OpenAI, `OPENAI_API_TYPE`, `OPENAI_API_BASE` y `OPENAI_API_VERSION` para que se puedan crear estos textos automáticamente.

Las comprobaciones se han ampliado para registrar el tiempo de actividad de cada host, detectar si el clúster tiene activados HA y DRS, y para cada VM revisar la presencia de instantáneas y el estado de VMware Tools.

Adicionalmente, la versión actual realiza comprobaciones básicas de:

- Configuración de servidores NTP en los hosts.
- Asignación de licencias en vCenter/ESXi.
- Existencia de resource pools en los clústeres.
- Inconsistencias de carpetas o VMs duplicadas.
- Búsqueda de VMDK "zombies" no asociados a una VM.
- Presencia de snapshots como indicativo de copias de seguridad.
- Verificación de CPU Ready y memoria "balloon" en las VMs.
- Comprobación básica de cumplimiento de actualizaciones en los hosts.
- Alerta por datastores con más del 90% de uso.
- Detección de IPv6 habilitado.
- Cálculo de la relación vCPU/pCPU y políticas Round Robin en iSCSI.
- Consistencia del nombre DNS configurado en cada host.

El informe generado con `template_a.html` muestra nuevas secciones: un **Health Score** con métricas globales, un resumen por categorías (rendimiento, almacenamiento, seguridad y disponibilidad), indicadores de componentes clave y varias tablas con los 10 elementos más relevantes (CPU Ready, uso de RAM, capacidad de datastores, espacio libre de discos por VM, IOPS y tráfico de red).
Además se incluyen indicadores extra como estado de actualizaciones, presencia de ballooning o discrepancias de DNS entre otros.


El script mostrará por pantalla un resumen de la información recopilada para cada host y para cada máquina virtual encontrada.
El informe HTML incluye ahora un ranking con las 10 máquinas virtuales con mayor **CPU Ready** y tablas con métricas detalladas de CPU, memoria, disco y red por VM. Además, se recopila información de datastores, interfaces de red y firmware de cada host.

Si se desean añadir contadores de rendimiento adicionales por VM basta con proporcionar un diccionario `metric_names` al método `vm_performance_check`.

**Nota**: este script es un punto de partida y no sustituye a una auditoría completa. Puede ampliarse para cubrir todas las comprobaciones de seguridad, rendimiento y mejores prácticas descritas en la solicitud original.

### Unidades de las métricas

- `cpu_ready_ms`: tiempo medio de CPU Ready expresado en milisegundos.
- `cpu_usage_pct` y `mem_usage_pct`: porcentajes reales (1.0 corresponde al 100 %).
- `disk_reads` y `disk_writes`: número medio de operaciones por intervalo.
- `net_rx_kbps` y `net_tx_kbps`: velocidad media de recepción y envío en KB/s.
- `disk_free_pct`: porcentaje de espacio libre en los discos virtuales de cada VM.

### Prompt base

La función `generate_detailed_report` utiliza un prompt muy sencillo para crear el informe:
```python
[
    {"role": "system", "content": "Eres un experto en VMware. Debes redactar un informe profesional."},
    {"role": "user", "content": "A partir del siguiente resumen genera un informe completo:\n<resumen>"}
]
```

Los módulos en `report_sections/` generan el texto de cada área. Cada uno arranca con una breve introducción y solicita a la IA que elabore un análisis adicional:

- **Rendimiento** analiza hosts y VMs usando datos de CPU y RAM.
- **Almacenamiento** revisa el uso de datastores y espacio libre.
- **Seguridad** evalúa puntos como snapshots, backups o licencias.
- **Disponibilidad** cubre HA, DRS y otros elementos de resiliencia.

