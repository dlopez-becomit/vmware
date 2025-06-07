# VMware Health Check

Este repositorio incluye una herramienta sencilla escrita en Python que se conecta a un vCenter o host ESXi para obtener información básica de seguridad, rendimiento y buenas prácticas.

## Requisitos

- Python 3.8+
- Dependencias indicadas en `requirements.txt` (`pyvmomi`, `matplotlib`, `jinja2`)

## Instalación

1. Instale las dependencias:
   ```bash
   pip install -r requirements.txt
   ```

2. Ejecute el script proporcionando los datos de conexión. Puede especificar opcionalmente un archivo de salida HTML:
   ```bash
   python vmware_healthcheck.py --host <vcenter o esxi> --user <usuario> --password <contraseña> --output reporte.html
   ```

3. El informe se genera a partir de la plantilla `template.html`. Puede personalizarla para cambiar la apariencia del reporte.

El script mostrará por pantalla un resumen de la información recopilada para cada host y para cada máquina virtual encontrada.
El informe HTML incluye ahora un ranking con las 10 máquinas virtuales con mayor **CPU Ready** y tablas con métricas detalladas de CPU, memoria, disco y red por VM. Además, se recopila información de datastores, interfaces de red y firmware de cada host.

**Nota**: este script es un punto de partida y no sustituye a una auditoría completa. Puede ampliarse para cubrir todas las comprobaciones de seguridad, rendimiento y mejores prácticas descritas en la solicitud original.

### Unidades de las métricas

- `cpu_ready_ms`: tiempo medio de CPU Ready expresado en milisegundos.
- `cpu_usage_pct` y `mem_usage_pct`: porcentajes reales (1.0 corresponde al 100 %).
- `disk_reads` y `disk_writes`: número medio de operaciones por intervalo.
- `net_rx_kbps` y `net_tx_kbps`: velocidad media de recepción y envío en KB/s.

## Pruebas

Para ejecutar las pruebas unitarias incluidas, utilice el módulo `unittest` de Python:

```bash
python -m unittest
```
