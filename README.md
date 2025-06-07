# VMware Health Check

Este repositorio incluye una herramienta sencilla escrita en Python que se conecta a un vCenter o host ESXi para obtener información básica de seguridad, rendimiento y buenas prácticas.

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

   Si desea emplear una plantilla Jinja2 personalizada para el informe, coloque
   el archivo de plantilla en el directorio deseado y utilice la opción
   `--template` para indicar su ubicación. Puede indicar un nombre de plantilla
   diferente mediante `--template-file`:
   ```bash
   python vmware_healthcheck.py --host <vcenter o esxi> --user <usuario> --password <contraseña> --output reporte.html --template /ruta/a/plantilla --template-file template_a.html
   ```
   De forma predeterminada, `generate_report` buscará un archivo llamado `template.html` en el directorio especificado (o en el del script si no se indica ninguno). Este repositorio incluye uno con un diseño minimalista y
   moderno listo para usar.
Adicionalmente, se incluye `template_a.html`, una plantilla avanzada con un formato extendido y botones para exportar o imprimir el informe. Para utilizarla basta con indicar el directorio donde se encuentra mediante `--template` y pasar `--template-file template_a.html`.

Las comprobaciones se han ampliado para registrar el tiempo de actividad de cada host, detectar si el clúster tiene activados HA y DRS, y para cada VM revisar la presencia de instantáneas y el estado de VMware Tools.

El informe generado con `template_a.html` muestra nuevas secciones: un **Health Score** con métricas globales, un resumen por categorías (rendimiento, almacenamiento, seguridad y disponibilidad), indicadores de componentes clave y varias tablas con los 10 elementos más relevantes (CPU Ready, uso de RAM, capacidad de datastores, IOPS y tráfico de red).


El script mostrará por pantalla un resumen de la información recopilada para cada host y para cada máquina virtual encontrada.
El informe HTML incluye ahora un ranking con las 10 máquinas virtuales con mayor **CPU Ready** y tablas con métricas detalladas de CPU, memoria, disco y red por VM. Además, se recopila información de datastores, interfaces de red y firmware de cada host.

Si se desean añadir contadores de rendimiento adicionales por VM basta con proporcionar un diccionario `metric_names` al método `vm_performance_check`.

**Nota**: este script es un punto de partida y no sustituye a una auditoría completa. Puede ampliarse para cubrir todas las comprobaciones de seguridad, rendimiento y mejores prácticas descritas en la solicitud original.

### Unidades de las métricas

- `cpu_ready_ms`: tiempo medio de CPU Ready expresado en milisegundos.
- `cpu_usage_pct` y `mem_usage_pct`: porcentajes reales (1.0 corresponde al 100 %).
- `disk_reads` y `disk_writes`: número medio de operaciones por intervalo.
- `net_rx_kbps` y `net_tx_kbps`: velocidad media de recepción y envío en KB/s.

