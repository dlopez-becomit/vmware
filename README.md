# VMware Health Check

Este repositorio incluye una herramienta sencilla escrita en Python que se conecta a un vCenter o host ESXi para obtener información básica de seguridad, rendimiento y buenas prácticas.

## Requisitos

- Python 3.8+
- Dependencias indicadas en `requirements.txt` (`pyvmomi`, `matplotlib`)

## Instalación

1. Instale las dependencias:
   ```bash
   pip install -r requirements.txt
   ```

2. Ejecute el script proporcionando los datos de conexión. Puede especificar opcionalmente un archivo de salida HTML:
   ```bash
   python vmware_healthcheck.py --host <vcenter o esxi> --user <usuario> --password <contraseña> --output reporte.html
   ```

El script mostrará por pantalla un resumen de la información recopilada para cada host detectado.

**Nota**: este script es un punto de partida y no sustituye a una auditoría completa. Puede ampliarse para cubrir todas las comprobaciones de seguridad, rendimiento y mejores prácticas descritas en la solicitud original.
