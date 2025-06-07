import argparse
import ssl
import io
import base64
import logging
from pyVim.connect import SmartConnect, Disconnect
from pyVmomi import vim
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

class VMwareHealthCheck:
    """Recopila información básica de seguridad y rendimiento en VMware."""

    def __init__(self, host, user, password, port=443):
        """Inicializa la conexión.

        Parameters
        ----------
        host : str
            Nombre o IP del vCenter/ESXi.
        user : str
            Usuario con permisos de acceso.
        password : str
            Contraseña del usuario.
        port : int, optional
            Puerto del servicio, por defecto ``443``.

        Returns
        -------
        None
        """
        self.host = host
        self.user = user
        self.password = password
        self.port = port
        self.si = None

    def connect(self):
        """Establece la conexión con el servidor VMware.

        Returns
        -------
        ServiceInstance
            Objeto de conexión a vSphere.
        """
        logger.info("Connecting to %s", self.host)
        context = ssl._create_unverified_context()
        try:
            self.si = SmartConnect(
                host=self.host,
                user=self.user,
                pwd=self.password,
                port=self.port,
                sslContext=context,
            )
            logger.info("Connection established")
        except vim.fault.InvalidLogin:
            logger.error("Invalid credentials for %s", self.host)
            raise
        except Exception:
            logger.exception("Error connecting to %s", self.host)
            raise
        return self.si

    def disconnect(self):
        """Cierra la conexión actual si existe."""
        if self.si:
            logger.info("Disconnecting from %s", self.host)
            Disconnect(self.si)

    def get_hosts(self):
        """Devuelve la lista de hosts gestionados."""
        logger.info("Retrieving hosts")
        content = self.si.RetrieveContent()
        container = content.viewManager.CreateContainerView(
            content.rootFolder, [vim.HostSystem], True
        )
        hosts = list(container.view)
        container.Destroy()
        logger.info("Found %d host(s)", len(hosts))
        return hosts

    def security_check(self, host):
        """Realiza comprobaciones básicas de seguridad en un host."""
        logger.info("Running security checks on %s", host.name)
        summary = host.summary
        config = host.config
        security = {}
        security['name'] = summary.config.name
        security['version'] = summary.config.product.fullName
        # "lockdownMode" reflects whether the host restricts direct remote
        # management access (normal, lockdown or strict modes)
        security['lockdown_mode'] = config.lockdownMode
        security['services'] = {
            'ssh': any(s.key == 'TSM-SSH' and s.running for s in host.configManager.serviceSystem.serviceInfo.service),
            'esxi_shell': any(s.key == 'TSM' and s.running for s in host.configManager.serviceSystem.serviceInfo.service)
        }
        ntp_cfg = getattr(getattr(config.dateTimeInfo, 'ntpConfig', None), 'server', None)
        if isinstance(ntp_cfg, (list, tuple)):
            security['ntp_servers'] = list(ntp_cfg)
        elif ntp_cfg:
            security['ntp_servers'] = [ntp_cfg]
        else:
            security['ntp_servers'] = []
        firewall_info = host.configManager.firewallSystem.firewallInfo
        # `vim.host.FirewallInfo` exposes its rules via the `ruleset` attribute
        # in pyVmomi. Each ruleset represents a named group of firewall rules
        # that can be enabled or disabled. Collect the identifiers for all
        # configured rulesets so they can be reported.
        security['firewall_exceptions'] = [rs.key for rs in getattr(firewall_info, 'ruleset', [])]
        return security

    def performance_check(self, host):
        """Obtiene métricas de rendimiento del host."""
        logger.info("Gathering performance metrics from %s", host.name)
        summary = host.summary
        stats = summary.quickStats
        perf = {
            'cpu_usage': stats.overallCpuUsage,
            'memory_usage': stats.overallMemoryUsage,
            'num_vms': len(getattr(host, 'vm', [])),
            'network_usage_kbps': getattr(stats, 'overallNetworkUsage', 0)
        }

        # Datastore usage aggregated across all datastores assigned to the host
        datastore_stats = []
        for ds in getattr(host, 'datastore', []):
            try:
                summary = ds.summary
                datastore_stats.append({
                    'name': summary.name,
                    'capacity_gb': summary.capacity / (1024 ** 3),
                    'free_gb': summary.freeSpace / (1024 ** 3)
                })
            except Exception:
                continue
        perf['datastores'] = datastore_stats

        # Basic information about physical NICs
        nic_stats = []
        for pnic in getattr(host.config.network, 'pnic', []):
            nic_stats.append({
                'device': pnic.device,
                'speed_mb': getattr(getattr(pnic, 'linkSpeed', None), 'speedMb', 'n/a')
            })
        perf['network'] = nic_stats

        # Firmware information can also be interesting from a performance point of view
        hw = host.hardware
        perf['firmware'] = {
            'bios_version': getattr(hw.biosInfo, 'biosVersion', 'n/a'),
            'vendor': getattr(hw.systemInfo, 'vendor', 'n/a'),
            'model': getattr(hw.systemInfo, 'model', 'n/a'),
        }

        # Additional metrics can be gathered from host.configManager or perfManager
        return perf

    def _build_perf_counter_map(self):
        """Create a mapping of performance counter name to counter id."""
        pm = self.si.content.perfManager
        counters = {}
        for c in pm.perfCounter:
            full = f"{c.groupInfo.key}.{c.nameInfo.key}.{c.rollupType}"
            counters[full] = c.key
        return counters

    def vm_performance_check(self, vm, counters=None, metric_names=None):
        """Gather VM level performance metrics."""
        pm = self.si.content.perfManager
        if counters is None:
            counters = self._build_perf_counter_map()

        if metric_names is None:
            metric_names = {
                'cpu.ready.summation': 'cpu_ready_ms',
                'cpu.usage.average': 'cpu_usage_pct',
                'mem.usage.average': 'mem_usage_pct',
                'disk.numberRead.summation': 'disk_reads',
                'disk.numberWrite.summation': 'disk_writes',
                'net.received.average': 'net_rx_kbps',
                'net.transmitted.average': 'net_tx_kbps',
            }

        metric_ids = []
        for key in metric_names:
            cid = counters.get(key)
            if cid:
                metric_ids.append(vim.PerformanceManager.MetricId(counterId=cid, instance="*"))

        spec = vim.PerformanceManager.QuerySpec(
            entity=vm,
            maxSample=1,
            metricId=metric_ids,
            intervalId=20,
        )

        stats = pm.QueryStats(querySpec=[spec])
        metrics = {v: 0 for v in metric_names.values()}
        if stats:
            vals = stats[0].value
            for val in vals:
                for name, field in metric_names.items():
                    if counters.get(name) == val.id.counterId:
                        if val.value:
                            metrics[field] = sum(val.value) / len(val.value)
        return metrics

    def best_practice_check(self, host):
        """Comprueba parámetros recomendados en un host."""
        logger.info("Checking best practices on %s", host.name)
        bp = {}
        hardware = host.hardware
        bp['cpu_model'] = hardware.cpuPkg[0].description if hardware.cpuPkg else 'n/a'
        # Convert memory size from bytes to gigabytes for easier readability
        bp['memory_total_gb'] = hardware.memorySize / (1024 ** 3)

        # Detailed datastore information
        datastore_info = []
        for ds in host.datastore:
            try:
                summary = ds.summary
                datastore_info.append({
                    'name': summary.name,
                    'capacity_gb': summary.capacity / (1024 ** 3),
                    'free_gb': summary.freeSpace / (1024 ** 3)
                })
            except Exception:
                continue
        bp['datastores'] = datastore_info

        # Basic network interface details
        nic_info = []
        for pnic in getattr(host.config.network, 'pnic', []):
            nic_info.append({
                'device': pnic.device,
                'speed_mb': getattr(getattr(pnic, 'linkSpeed', None), 'speedMb', 'n/a')
            })
        bp['network'] = nic_info

        # Firmware information
        bp['firmware'] = {
            'bios_version': getattr(hardware.biosInfo, 'biosVersion', 'n/a'),
            'vendor': getattr(hardware.systemInfo, 'vendor', 'n/a'),
            'model': getattr(hardware.systemInfo, 'model', 'n/a'),
        }
        return bp

    def _create_chart(self, hosts_data):
        """Genera un gráfico de uso de CPU y memoria.

        Parameters
        ----------
        hosts_data : list of dict
            Datos recopilados de cada host.

        Returns
        -------
        str
            Imagen en base64 del gráfico.
        """
        names = [h['name'] for h in hosts_data]
        cpu = [h['performance']['cpu_usage'] for h in hosts_data]
        mem = [h['performance']['memory_usage'] for h in hosts_data]

        x = range(len(names))
        fig, ax = plt.subplots()
        ax.bar([i - 0.2 for i in x], cpu, width=0.4, label='CPU (MHz)')
        ax.bar([i + 0.2 for i in x], mem, width=0.4, label='Memory (MB)')
        ax.set_xticks(list(x))
        ax.set_xticklabels(names, rotation=45, ha='right')
        ax.legend()
        plt.tight_layout()

        buffer = io.BytesIO()
        plt.savefig(buffer, format='png')
        plt.close(fig)
        encoded = base64.b64encode(buffer.getvalue()).decode()
        return encoded

    def generate_report(self, hosts_data, vm_data, output_file):
        """Crea un informe HTML con los datos obtenidos.

        Parameters
        ----------
        hosts_data : list of dict
            Información de los hosts analizados.
        output_file : str
            Ruta del archivo HTML de salida.
        """
        logger.info("Generating HTML report: %s", output_file)
        chart = self._create_chart(hosts_data)

        html = [
            "<html><head><meta charset='utf-8'><title>VMware Health Check</title>",
            "<style>body{font-family:Arial;}table{border-collapse:collapse;}",
            "th,td{border:1px solid #ccc;padding:4px;}h1,h2{color:#2c3e50;}",
            "</style></head><body>"
        ]
        html.append("<h1>VMware Health Check Report</h1>")

        html.append(f"<img src='data:image/png;base64,{chart}' alt='Resource Usage Chart'/>")

        top_vms = sorted(vm_data, key=lambda x: x['metrics'].get('cpu_ready_ms', 0), reverse=True)[:10]
        html.append("<h2>Top 10 VMs by CPU Ready</h2><table>")
        html.append("<tr><th>VM</th><th>CPU Ready (ms)</th></tr>")
        for v in top_vms:
            html.append(f"<tr><td>{v['name']}</td><td>{v['metrics'].get('cpu_ready_ms', 0)}</td></tr>")
        html.append("</table>")

        for h in hosts_data:
            html.append(f"<h2>Host: {h['name']}</h2>")
            html.append("<h3>Security</h3><table>")
            for k, v in h['security'].items():
                html.append(f"<tr><th>{k}</th><td>{v}</td></tr>")
            html.append("</table>")

            html.append("<h3>Performance</h3><table>")
            perf_basic = ['cpu_usage', 'memory_usage', 'num_vms', 'network_usage_kbps']
            for k in perf_basic:
                if k in h['performance']:
                    html.append(f"<tr><th>{k}</th><td>{h['performance'][k]}</td></tr>")
            html.append("</table>")

            if h['performance'].get('datastores'):
                html.append("<h4>Datastores</h4>")
                html.append("<table><tr><th>Name</th><th>Capacity (GB)</th><th>Free (GB)</th></tr>")
                for ds in h['performance']['datastores']:
                    html.append(f"<tr><td>{ds['name']}</td><td>{ds['capacity_gb']:.1f}</td><td>{ds['free_gb']:.1f}</td></tr>")
                html.append("</table>")

            if h['performance'].get('network'):
                html.append("<h4>Network Interfaces</h4>")
                html.append("<table><tr><th>Device</th><th>Speed (Mb)</th></tr>")
                for nic in h['performance']['network']:
                    html.append(f"<tr><td>{nic['device']}</td><td>{nic['speed_mb']}</td></tr>")
                html.append("</table>")

            html.append("<h3>Best Practices</h3><table>")
            html.append(f"<tr><th>cpu_model</th><td>{h['best_practice'].get('cpu_model')}</td></tr>")
            html.append(f"<tr><th>memory_total_gb</th><td>{h['best_practice'].get('memory_total_gb')}</td></tr>")
            html.append("</table>")

            if h['best_practice'].get('datastores'):
                html.append("<h4>Datastores</h4><table><tr><th>Name</th><th>Capacity (GB)</th><th>Free (GB)</th></tr>")
                for ds in h['best_practice']['datastores']:
                    html.append(f"<tr><td>{ds['name']}</td><td>{ds['capacity_gb']:.1f}</td><td>{ds['free_gb']:.1f}</td></tr>")
                html.append("</table>")

            if h['best_practice'].get('network'):
                html.append("<h4>Network Interfaces</h4><table><tr><th>Device</th><th>Speed (Mb)</th></tr>")
                for nic in h['best_practice']['network']:
                    html.append(f"<tr><td>{nic['device']}</td><td>{nic['speed_mb']}</td></tr>")
                html.append("</table>")

            if h['best_practice'].get('firmware'):
                fw = h['best_practice']['firmware']
                html.append("<h4>Firmware</h4><table>")
                html.append(f"<tr><th>Vendor</th><td>{fw.get('vendor')}</td></tr>")
                html.append(f"<tr><th>Model</th><td>{fw.get('model')}</td></tr>")
                html.append(f"<tr><th>BIOS Version</th><td>{fw.get('bios_version')}</td></tr>")
                html.append("</table>")

            if h.get('vms'):
                html.append("<h3>VM Metrics</h3>")
                html.append("<table>")
                html.append("<tr><th>Name</th><th>CPU Ready (ms)</th><th>CPU Usage (%)</th><th>Memory Usage (%)</th><th>Disk Reads</th><th>Disk Writes</th><th>Net RX</th><th>Net TX</th></tr>")
                for vm in h['vms']:
                    m = vm['metrics']
                    html.append(
                        f"<tr><td>{vm['name']}</td><td>{m.get('cpu_ready_ms', 0)}</td>"
                        f"<td>{m.get('cpu_usage_pct', 0)}</td>"
                        f"<td>{m.get('mem_usage_pct', 0)}</td>"
                        f"<td>{m.get('disk_reads', 0)}</td>"
                        f"<td>{m.get('disk_writes', 0)}</td>"
                        f"<td>{m.get('net_rx_kbps', 0)}</td>"
                        f"<td>{m.get('net_tx_kbps', 0)}</td></tr>"
                    )
                html.append("</table>")

        html.append("</body></html>")

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(html))


def main():
    """Punto de entrada del script."""
    parser = argparse.ArgumentParser(description='VMware ESXi/vCenter Health Check')
    parser.add_argument('--host', required=True, help='vCenter or ESXi hostname/IP')
    parser.add_argument('--user', required=True, help='username')
    parser.add_argument('--password', required=True, help='password')
    parser.add_argument('--output', help='HTML report file')
    args = parser.parse_args()

    checker = VMwareHealthCheck(args.host, args.user, args.password)
    try:
        checker.connect()

        hosts = checker.get_hosts()
        hosts_data = []
        all_vms = []
        for host in hosts:
            logger.info("Processing host %s", host.name)
            security = checker.security_check(host)
            performance = checker.performance_check(host)
            best_practice = checker.best_practice_check(host)
            vm_info = []
            counters = checker._build_perf_counter_map()
            for vm in getattr(host, 'vm', []):
                metrics = checker.vm_performance_check(vm, counters)
                vm_info.append({'name': vm.name, 'metrics': metrics})
                all_vms.append({'name': vm.name, 'metrics': metrics})

            print('--- Host: {} ---'.format(host.name))
            print('Security:')
            for k, v in security.items():
                print('  {}: {}'.format(k, v))
            print('Performance:')
            for k, v in performance.items():
                print('  {}: {}'.format(k, v))
            print('Best Practices:')
            for k, v in best_practice.items():
                print('  {}: {}'.format(k, v))
            print('VM Metrics:')
            for vm in vm_info:
                print('  VM: {}'.format(vm['name']))
                for mk, mv in vm['metrics'].items():
                    print('    {}: {}'.format(mk, mv))
            print()

            hosts_data.append({
                'name': host.name,
                'security': security,
                'performance': performance,
                'best_practice': best_practice,
                'vms': vm_info,
            })

        if args.output:
            checker.generate_report(hosts_data, all_vms, args.output)
            logger.info("HTML report written to %s", args.output)
    finally:
        checker.disconnect()

if __name__ == '__main__':
    main()
