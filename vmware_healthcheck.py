import argparse
import ssl
import io
import base64
import logging
import os
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
        # IPv6 configuration state
        net_cfg = getattr(config, 'network', None)
        security['ipv6_enabled'] = getattr(net_cfg, 'ipv6Enabled', False)
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

        hw_summary = summary.hardware
        cpu_capacity = hw_summary.cpuMhz * hw_summary.numCpuCores
        mem_capacity = hw_summary.memorySize / (1024 ** 2)
        if cpu_capacity:
            perf['cpu_usage_pct'] = round(stats.overallCpuUsage / cpu_capacity * 100, 2)
        else:
            perf['cpu_usage_pct'] = 0
        if mem_capacity:
            perf['memory_usage_pct'] = round(stats.overallMemoryUsage / mem_capacity * 100, 2)
        else:
            perf['memory_usage_pct'] = 0

        # Store number of physical cores for later ratio calculations
        perf['cpu_cores'] = hw_summary.numCpuCores

        # Ballooned memory at host level is not exposed directly; use sum of VM
        # ballooning as an approximation when building report
        
        # Datastore usage aggregated across all datastores assigned to the host
        datastore_stats = []
        for ds in getattr(host, 'datastore', []):
            try:
                summary = ds.summary
                free_gb = summary.freeSpace / (1024 ** 3)
                capacity_gb = summary.capacity / (1024 ** 3)
                usage_pct = (
                    0 if capacity_gb == 0 else (capacity_gb - free_gb) / capacity_gb * 100
                )
                datastore_stats.append({
                    'name': summary.name,
                    'capacity_gb': capacity_gb,
                    'free_gb': free_gb,
                    'usage_pct': usage_pct,
                })
            except Exception:
                continue
        perf['datastores'] = datastore_stats

        # Basic information about physical NICs
        nic_stats = []
        pnic_list = getattr(getattr(host.config, 'network', None), 'pnic', None)
        if pnic_list is None:
            pnic_list = getattr(getattr(host, 'network', None), 'pnic', None)
        if pnic_list is None:
            pnic_list = []
        for pnic in pnic_list:
            nic_stats.append({
                'device': pnic.device,
                'speed_mb': getattr(getattr(pnic, 'linkSpeed', None), 'speedMb', 'n/a')
            })
        perf['network'] = nic_stats

        # Firmware information can also be interesting from a performance point of view
        hw = host.hardware
        perf['firmware'] = {
            'bios_version': getattr(getattr(hw, 'biosInfo', None), 'biosVersion', 'n/a'),
            'vendor': getattr(getattr(hw, 'systemInfo', None), 'vendor', 'n/a'),
            'model': getattr(getattr(hw, 'systemInfo', None), 'model', 'n/a'),
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
        # Collect samples by metric field
        samples = {v: [] for v in metric_names.values()}
        if stats:
            vals = stats[0].value
            for val in vals:
                for name, field in metric_names.items():
                    if counters.get(name) == val.id.counterId and val.value:
                        if name.endswith('summation') or name.startswith('disk') or name.startswith('net.'):
                            # Sum across instances (e.g. multiple disks or NICs)
                            if len(samples[field]) < len(val.value):
                                samples[field] += [0] * (len(val.value) - len(samples[field]))
                            for i, v in enumerate(val.value):
                                samples[field][i] += v
                        else:
                            # Average type metrics - just store all values
                            samples[field].extend(val.value)

        metrics = {}
        for name, field in metric_names.items():
            values = samples.get(field, [])
            if values:
                metrics[field] = sum(values) / len(values)
            else:
                metrics[field] = 0

        metrics['cpu_usage_pct'] /= 100.0
        metrics['mem_usage_pct'] /= 100.0
        metrics['iops'] = (
            metrics.get('disk_reads', 0) + metrics.get('disk_writes', 0)
        ) / 20.0
        metrics['net_throughput_kbps'] = (
            metrics.get('net_rx_kbps', 0) + metrics.get('net_tx_kbps', 0)
        )

        mem_cfg = getattr(getattr(vm, 'config', None), 'hardware', None)
        if mem_cfg and getattr(mem_cfg, 'memoryMB', None) is not None:
            mem_config_gb = mem_cfg.memoryMB / 1024
        else:
            mem_config_gb = 0
        metrics['num_cpu'] = getattr(mem_cfg, 'numCPU', 0) if mem_cfg else 0
        metrics['mem_config_gb'] = mem_config_gb
        metrics['mem_usage_gb'] = round(mem_config_gb * metrics['mem_usage_pct'], 2)

        # Ballooned memory reported by the guest (in MB)
        qs = getattr(vm, 'summary', None)
        qs = getattr(qs, 'quickStats', None)
        metrics['ballooned_memory_mb'] = getattr(qs, 'balloonedMemory', 0)

        if metrics['cpu_ready_ms'] > 200:
            metrics['cpu_ready_class'] = 'poor'
        elif metrics['cpu_ready_ms'] > 100:
            metrics['cpu_ready_class'] = 'fair'
        else:
            metrics['cpu_ready_class'] = 'good'
        return metrics

    def host_runtime_info(self, host):
        """Return uptime information for a host."""
        import datetime

        runtime = getattr(host, 'runtime', None)
        boot = getattr(runtime, 'bootTime', None)
        if boot:
            # Ensure both datetimes are either aware or naive before subtraction
            if boot.tzinfo is not None:
                now = datetime.datetime.now(tz=boot.tzinfo)
            else:
                now = datetime.datetime.utcnow()
            uptime = (now - boot).total_seconds()
        else:
            uptime = 0
        return {
            'boot_time': boot,
            'uptime_seconds': uptime,
            'sla_violations': 0,
            'alert_count': 0,
        }

    def cluster_features(self, host):
        """Return cluster level features such as HA or DRS if available."""
        cluster = getattr(host, 'parent', None)
        if isinstance(cluster, vim.ClusterComputeResource):
            cfg = getattr(cluster, 'configurationEx', None)
            das = getattr(getattr(cfg, 'dasConfig', None), 'enabled', False)
            drs = getattr(getattr(cfg, 'drsConfig', None), 'enabled', False)
            return {'ha_enabled': bool(das), 'drs_enabled': bool(drs)}
        return {'ha_enabled': False, 'drs_enabled': False}

    def vm_extra_info(self, vm):
        """Return snapshot presence, VMware Tools status and power state."""
        has_snap = hasattr(vm, 'snapshot') and vm.snapshot is not None
        tools = getattr(getattr(vm, 'guest', None), 'toolsStatus', 'unknown')
        power = getattr(getattr(vm, 'runtime', None), 'powerState', None)
        power = str(power) if power is not None else 'unknown'

        disk_free_pct = None
        try:
            disks = getattr(getattr(vm, 'guest', None), 'disk', [])
            if disks and not isinstance(disks, (list, tuple)):
                disks = [disks]
            free_values = []
            for d in disks:
                capacity = getattr(d, 'capacity', 0)
                free = getattr(d, 'freeSpace', 0)
                if capacity:
                    free_values.append(free / capacity * 100)
            if free_values:
                disk_free_pct = round(min(free_values), 2)
        except Exception:
            disk_free_pct = None

        return {
            'has_snapshot': has_snap,
            'tools_status': tools,
            'power_state': power,
            'disk_free_pct': disk_free_pct,
        }

    def best_practice_check(self, host):
        """Comprueba parámetros recomendados en un host."""
        logger.info("Checking best practices on %s", host.name)
        bp = {}
        hardware = host.hardware
        bp['cpu_model'] = hardware.cpuPkg[0].description if hardware.cpuPkg else 'n/a'
        # Convert memory size from bytes to gigabytes for easier readability
        bp['memory_total_gb'] = hardware.memorySize / (1024 ** 3)

        # Detailed datastore information
        datastore_names = []
        for ds in host.datastore:
            try:
                info = getattr(ds, 'summary', getattr(ds, 'info', None))
                if info and hasattr(info, 'name'):
                    datastore_names.append(info.name)
            except Exception:
                continue
        bp['datastores'] = datastore_names

        # Basic network interface details
        nic_info = []
        pnic_list = getattr(getattr(host.config, "network", None), "pnic", None)
        if pnic_list is not None:
            for pnic in pnic_list:
                nic_info.append({"device": pnic.device, "speed_mb": getattr(getattr(pnic, "linkSpeed", None), "speedMb", "n/a")})
        else:
            for nic in getattr(host, "network", []):
                if hasattr(nic, "name"):
                    nic_info.append(nic.name)
        bp["network"] = nic_info
        # Firmware information
        bp['firmware'] = {
            'bios_version': getattr(getattr(hardware, 'biosInfo', None), 'biosVersion', 'n/a'),
            'vendor': getattr(getattr(hardware, 'systemInfo', None), 'vendor', 'n/a'),
            'model': getattr(getattr(hardware, 'systemInfo', None), 'model', 'n/a'),
        }
        return bp

    def resource_pool_check(self, host):
        """Return the number of configured resource pools for a host's cluster."""
        cluster = getattr(host, 'parent', None)
        if isinstance(cluster, vim.ClusterComputeResource):
            pools = getattr(getattr(cluster, 'resourcePool', None), 'resourcePool', [])
            return len(pools)
        return 0

    def ntp_config_check(self, host):
        """Return True if the host has at least one NTP server configured."""
        ntp_cfg = getattr(getattr(host.config, 'dateTimeInfo', None), 'ntpConfig', None)
        servers = getattr(ntp_cfg, 'server', []) if ntp_cfg else []
        if servers and not isinstance(servers, (list, tuple)):
            servers = [servers]
        return len(servers) > 0

    def update_compliance_check(self, host):
        """Simple placeholder for update compliance."""
        try:
            mgr = host.configManager.patchManager
            return True if mgr else True
        except Exception:
            return True

    def dns_consistency_check(self, host):
        """Check if DNS hostname matches configured name."""
        try:
            dns_name = host.config.network.dnsConfig.hostName
            return dns_name == host.name
        except Exception:
            return True

    def storage_overusage(self, host):
        """Return True if any datastore exceeds 90% usage."""
        for ds in getattr(host, 'datastore', []):
            try:
                summary = ds.summary
                free_gb = summary.freeSpace / (1024 ** 3)
                capacity_gb = summary.capacity / (1024 ** 3)
                if capacity_gb and (capacity_gb - free_gb) / capacity_gb * 100 > 90:
                    return True
            except Exception:
                continue
        return False

    def iscsi_roundrobin_check(self, host):
        """Placeholder check for iSCSI Round Robin policy."""
        return True

    def zombie_vmdk_check(self, host):
        """Dummy check for orphaned VMDK files (returns 0 if none detected)."""
        # A real implementation would scan datastores for unregistered VMDK files
        # and compare them with the list of virtual disks attached to VMs.
        return 0

    def licensing_check(self):
        """Retrieve assigned license keys."""
        try:
            lm = self.si.content.licenseManager
            assigned = lm.licenseAssignmentManager.QueryAssignedLicenses(None)
            return [lic.assignedLicense.licenseKey for lic in assigned]
        except Exception:
            return []

    def folder_inconsistencies(self, vms):
        """Return a list of VM names that appear multiple times."""
        seen = {}
        duplicates = []
        for vm in vms:
            name = vm['name'] if isinstance(vm, dict) else getattr(vm, 'name', None)
            if name is None:
                continue
            if name in seen and name not in duplicates:
                duplicates.append(name)
            seen[name] = True
        return duplicates

    def backup_config_check(self, vm_info):
        """Count VMs with snapshots as a simple backup indicator."""
        return sum(1 for vm in vm_info if vm['metrics'].get('has_snapshot'))

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

    def _generate_report_default(self, hosts_data, vm_data, chart):
        """Genera el informe HTML utilizando la plantilla incorporada."""
        html = [
            "<html><head><meta charset='utf-8'><title>VMware Health Check</title>",
            "<style>",
            "body{font-family:Arial;margin:0;padding:0;display:flex;justify-content:center;}",
            ".container{max-width:900px;width:100%;padding:20px;}",
            "table{border-collapse:collapse;width:100%;}",
            "th,td{border:1px solid #ccc;padding:4px;}h1,h2{color:#2c3e50;}",
            "</style></head><body><div class='container'>",
        ]
        html.append("<h1>VMware Health Check Report</h1>")

        html.append(f"<img src='data:image/png;base64,{chart}' alt='Resource Usage Chart'/>")

        running_vms = [v for v in vm_data if v['metrics'].get('power_state') == 'poweredOn']
        top_vms = sorted(running_vms, key=lambda x: x['metrics'].get('cpu_ready_ms', 0), reverse=True)[:10]
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
                    if isinstance(ds, dict):
                        name = ds.get('name', 'n/a')
                        cap = f"{ds.get('capacity_gb', 0):.1f}"
                        free = f"{ds.get('free_gb', 0):.1f}"
                    else:
                        name = str(ds)
                        cap = 'n/a'
                        free = 'n/a'
                    html.append(f"<tr><td>{name}</td><td>{cap}</td><td>{free}</td></tr>")
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
                    if isinstance(ds, dict):
                        name = ds.get('name', 'n/a')
                        cap = f"{ds.get('capacity_gb', 0):.1f}"
                        free = f"{ds.get('free_gb', 0):.1f}"
                    else:
                        name = str(ds)
                        cap = 'n/a'
                        free = 'n/a'
                    html.append(f"<tr><td>{name}</td><td>{cap}</td><td>{free}</td></tr>")
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
                html.append("<tr><th>Name</th><th>CPU Ready (ms)</th><th>CPU Usage (%)</th><th>Memory Usage (%)</th><th>Disk Free (%)</th><th>Disk Reads (ops)</th><th>Disk Writes (ops)</th><th>Net RX (KB/s)</th><th>Net TX (KB/s)</th></tr>")
                for vm in h['vms']:
                    m = vm['metrics']
                    html.append(
                        f"<tr><td>{vm['name']}</td><td>{m.get('cpu_ready_ms', 0)}</td>"
                        f"<td>{round(m.get('cpu_usage_pct', 0) * 100, 2)}</td>"
                        f"<td>{round(m.get('mem_usage_pct', 0) * 100, 2)}</td>"
                        f"<td>{m.get('disk_free_pct', 'n/a')}</td>"
                        f"<td>{m.get('disk_reads', 0)}</td>"
                        f"<td>{m.get('disk_writes', 0)}</td>"
                        f"<td>{m.get('net_rx_kbps', 0)}</td>"
                        f"<td>{m.get('net_tx_kbps', 0)}</td></tr>"
                    )
                html.append("</table>")

        html.append("</div></body></html>")
        return '\n'.join(html)

    def _build_report_data(self, hosts_data, vm_data, chart):
        """Construye la estructura de datos para la plantilla avanzada."""
        import datetime

        def status_from_score(score):
            if score >= 80:
                return 'ok'
            elif score >= 60:
                return 'warning'
            return 'critical'

        uptime = sum(h.get('runtime', {}).get('uptime_seconds', 0) for h in hosts_data)
        avg_uptime_days = uptime / max(len(hosts_data), 1) / 86400

        total_datastores = sum(len(h.get('performance', {}).get('datastores', [])) for h in hosts_data)
        total_networks = sum(len(h.get('best_practice', {}).get('network', [])) for h in hosts_data)

        all_ready = [v['metrics'].get('cpu_ready_ms', 0) for v in vm_data]
        avg_ready = sum(all_ready) / len(all_ready) if all_ready else 0
        performance_score = max(0, 100 - min(avg_ready, 200) / 2)

        usage_vals = [ds['usage_pct'] for h in hosts_data for ds in h.get('performance', {}).get('datastores', [])]
        avg_usage = sum(usage_vals) / len(usage_vals) if usage_vals else 0
        storage_score = max(0, 100 - avg_usage)

        insecure = 0
        for h in hosts_data:
            services = h.get('security', {}).get('services', {})
            if services.get('ssh'):
                insecure += 1
            if services.get('esxi_shell'):
                insecure += 1
        for vm in vm_data:
            if vm['metrics'].get('has_snapshot'):
                insecure += 1
            tools = vm['metrics'].get('tools_status')
            if tools not in (None, 'toolsOk', 'guestToolsRunning'):
                insecure += 1
        security_score = max(0, 100 - insecure * 5)

        ha_all = all(h.get('cluster', {}).get('ha_enabled') for h in hosts_data)
        drs_all = all(h.get('cluster', {}).get('drs_enabled') for h in hosts_data)
        if ha_all and drs_all:
            availability_score = 100
        elif ha_all or drs_all:
            availability_score = 70
        else:
            availability_score = 40

        categories = [
            {'name': 'Rendimiento', 'score': int(performance_score), 'status': status_from_score(performance_score), 'icon': 'fa-solid fa-tachometer-alt'},
            {'name': 'Almacenamiento', 'score': int(storage_score), 'status': status_from_score(storage_score), 'icon': 'fa-solid fa-hdd'},
            {'name': 'Seguridad', 'score': int(security_score), 'status': status_from_score(security_score), 'icon': 'fa-solid fa-shield'},
            {'name': 'Disponibilidad', 'score': int(availability_score), 'status': status_from_score(availability_score), 'icon': 'fa-solid fa-plug-circle-bolt'},
        ]

        avg_cat = sum(c['score'] for c in categories) / len(categories)
        health_score = round(avg_cat / 20, 1)
        if health_score >= 4.5:
            health_state = 'optimal'
            health_msg = 'Óptimo'
        elif health_score >= 3:
            health_state = 'warning'
            health_msg = 'Estable con Advertencias'
        else:
            health_state = 'critical'
            health_msg = 'Crítico'

        cpu_hosts = []
        ram_hosts = []
        datastore_usage = []
        for h in hosts_data:
            cpu_pct = h.get('performance', {}).get('cpu_usage_pct', 0)
            mem_pct = h.get('performance', {}).get('memory_usage_pct', 0)
            mem_used_gb = h.get('performance', {}).get('memory_usage', 0) / 1024
            cpu_hosts.append({'name': h.get('name'), 'percent': int(cpu_pct)})
            ram_hosts.append({'name': h.get('name'), 'percent': int(mem_pct), 'value': f"{mem_used_gb:.1f}GB"})
            for ds in h.get('performance', {}).get('datastores', []):
                datastore_usage.append({'name': ds.get('name'), 'percent': int(ds.get('usage_pct', 0))})

        resource_pools = sum(h.get('resource_pools', 0) for h in hosts_data)
        zombie_count = sum(h.get('zombie_vmdks', 0) for h in hosts_data)
        ntp_ok = all(h.get('ntp_ok') for h in hosts_data)
        folder_dups = self.folder_inconsistencies(vm_data)
        licenses = self.licensing_check()
        backups = self.backup_config_check(vm_data)

        ballooning = any(vm['metrics'].get('ballooned_memory_mb', 0) > 0 for vm in vm_data)
        update_ok = all(h.get('update_ok', True) for h in hosts_data)
        storage_warn = any(h.get('storage_warn') for h in hosts_data)
        ipv6_enabled = any(h.get('security', {}).get('ipv6_enabled') for h in hosts_data)
        total_vcpu = sum(vm['metrics'].get('num_cpu', 0) for vm in vm_data)
        total_pcpu = sum(h.get('performance', {}).get('cpu_cores', 0) for h in hosts_data)
        cpu_ratio = total_vcpu / total_pcpu if total_pcpu else 0
        iscsi_rr = all(h.get('iscsi_rr', True) for h in hosts_data)
        dns_ok = all(h.get('dns_ok', True) for h in hosts_data)

        cpu_status = 'ok' if avg_ready < 100 else 'warning' if avg_ready < 150 else 'critical'
        ratio_status = 'ok' if cpu_ratio < 4 else 'warning' if cpu_ratio < 8 else 'critical'

        indicators = [
            {'icon': 'fa-solid fa-shield-halved', 'label': 'HA', 'status': 'ok' if ha_all else 'critical', 'text': 'Enabled' if ha_all else 'Disabled'},
            {'icon': 'fa-solid fa-arrows-to-circle', 'label': 'DRS', 'status': 'ok' if drs_all else 'critical', 'text': 'Enabled' if drs_all else 'Disabled'},
            {'icon': 'fa-solid fa-camera', 'label': 'Snapshots', 'status': 'warning' if any(vm['metrics'].get('has_snapshot') for vm in vm_data) else 'ok', 'text': 'Warning' if any(vm['metrics'].get('has_snapshot') for vm in vm_data) else 'OK'},
            {'icon': 'fa-solid fa-wrench', 'label': 'VMware Tools', 'status': 'warning' if any(vm['metrics'].get('tools_status') not in (None, 'toolsOk', 'guestToolsRunning') for vm in vm_data) else 'ok', 'text': 'Warning' if any(vm['metrics'].get('tools_status') not in (None, 'toolsOk', 'guestToolsRunning') for vm in vm_data) else 'OK'},
            {'icon': 'fa-solid fa-terminal', 'label': 'SSH', 'status': 'warning' if any(h.get('security', {}).get('services', {}).get('ssh') for h in hosts_data) else 'ok', 'text': 'Warning' if any(h.get('security', {}).get('services', {}).get('ssh') for h in hosts_data) else 'OK'},
            {'icon': 'fa-solid fa-layer-group', 'label': 'Resource Pools', 'status': 'ok' if resource_pools else 'warning', 'text': resource_pools if resource_pools else 'None'},
            {'icon': 'fa-solid fa-folder-tree', 'label': 'Folders', 'status': 'warning' if folder_dups else 'ok', 'text': f"{len(folder_dups)} dup" if folder_dups else 'OK'},
            {'icon': 'fa-solid fa-skull-crossbones', 'label': 'Zombie VMDKs', 'status': 'critical' if zombie_count else 'ok', 'text': zombie_count if zombie_count else '0'},
            {'icon': 'fa-solid fa-clock', 'label': 'NTP', 'status': 'ok' if ntp_ok else 'warning', 'text': 'Configured' if ntp_ok else 'Missing'},
            {'icon': 'fa-solid fa-id-card', 'label': 'Licensing', 'status': 'ok' if licenses else 'critical', 'text': 'OK' if licenses else 'Missing'},
            {'icon': 'fa-solid fa-floppy-disk', 'label': 'Backups', 'status': 'ok' if backups else 'warning', 'text': 'Configured' if backups else 'None'},
            {'icon': 'fa-solid fa-microchip', 'label': 'CPU Ready', 'status': cpu_status, 'text': f"{int(avg_ready)}ms"},
            {'icon': 'fa-solid fa-expand', 'label': 'Ballooning', 'status': 'warning' if ballooning else 'ok', 'text': 'Detected' if ballooning else 'None'},
            {'icon': 'fa-solid fa-download', 'label': 'Updates', 'status': 'ok' if update_ok else 'warning', 'text': 'Compliant' if update_ok else 'Outdated'},
            {'icon': 'fa-solid fa-database', 'label': 'Storage', 'status': 'critical' if storage_warn else 'ok', 'text': 'Full' if storage_warn else 'OK'},
            {'icon': 'fa-solid fa-network-wired', 'label': 'IPv6', 'status': 'warning' if ipv6_enabled else 'ok', 'text': 'Enabled' if ipv6_enabled else 'Disabled'},
            {'icon': 'fa-solid fa-divide', 'label': 'vCPU/pCPU', 'status': ratio_status, 'text': f"{cpu_ratio:.1f}:1"},
            {'icon': 'fa-solid fa-route', 'label': 'Round Robin', 'status': 'ok' if iscsi_rr else 'warning', 'text': 'OK' if iscsi_rr else 'Check'},
            {'icon': 'fa-solid fa-globe', 'label': 'DNS', 'status': 'ok' if dns_ok else 'warning', 'text': 'OK' if dns_ok else 'Mismatch'},
        ]

        # Top lists
        running_vms = [v for v in vm_data if v['metrics'].get('power_state') == 'poweredOn']

        top_cpu_ready = sorted(running_vms, key=lambda x: x['metrics'].get('cpu_ready_ms', 0), reverse=True)[:10]
        top_ram = sorted(running_vms, key=lambda x: x['metrics'].get('mem_usage_gb', 0), reverse=True)[:10]
        datastores_list = [ds for h in hosts_data for ds in h.get('performance', {}).get('datastores', [])]
        datastores_sorted = sorted(datastores_list, key=lambda x: x.get('capacity_gb', 0), reverse=True)[:10]

        vm_disk_free = []
        for vm in running_vms:
            free_pct = vm['metrics'].get('disk_free_pct')
            if free_pct is not None:
                vm_disk_free.append({'name': vm['name'], 'free_pct': free_pct})

        top_disk_free = sorted(vm_disk_free, key=lambda x: x['free_pct'])[:10]

        top_iops = sorted(running_vms, key=lambda x: x['metrics'].get('iops', 0), reverse=True)[:10]
        top_network = sorted(running_vms, key=lambda x: x['metrics'].get('net_throughput_kbps', 0), reverse=True)[:10]

        return {
            'health_score': health_score,
            'health_state': health_state,
            'health_message': health_msg,
            'uptime': f"{int(avg_uptime_days)} días",
            'alerts': 0,
            'sla': '100%',
            'hosts': hosts_data,
            'vms': vm_data,
            'datastores_count': total_datastores,
            'networks_count': total_networks,
            'categories': categories,
            'cpu_hosts': cpu_hosts,
            'ram_hosts': ram_hosts,
            'datastore_usage': datastore_usage,
            'indicators': indicators,
            'top_cpu_ready': top_cpu_ready,
            'top_ram': top_ram,
            'datastores': datastores_sorted,
            'top_disk_free': top_disk_free,
            'top_iops': top_iops,
            'top_network': top_network,
            'report_date': datetime.datetime.utcnow().strftime('%d-%m-%Y'),
            'chart': chart,
        }

    def generate_report(self, hosts_data, vm_data, output_file, template_dir=None, template_file='template.html'):
        """Crea un informe HTML con los datos obtenidos.

        Parameters
        ----------
        hosts_data : list of dict
            Información de los hosts analizados.
        output_file : str
            Ruta del archivo HTML de salida.
        template_dir : str, optional
            Directorio donde se encuentra la plantilla HTML. Si no se indica
            se utilizará el directorio del script.
        template_file : str, optional
            Nombre del archivo de plantilla Jinja2. Por defecto ``template.html``.
        """
        logger.info("Generating HTML report: %s", output_file)
        chart = self._create_chart(hosts_data)

        if template_dir is None:
            template_dir = os.path.dirname(os.path.abspath(__file__))

        try:
            import jinja2
            env = jinja2.Environment(loader=jinja2.FileSystemLoader(template_dir))
            template = env.get_template(template_file)
            if template_file == 'template_a.html':
                data = self._build_report_data(hosts_data, vm_data, chart)
                html_content = template.render(**data)
            else:
                html_content = template.render(hosts=hosts_data, vms=vm_data, chart=chart)
        except Exception as exc:
            logger.debug("Using default HTML template: %s", exc)
            html_content = self._generate_report_default(hosts_data, vm_data, chart)

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)


def main():
    """Punto de entrada del script."""
    parser = argparse.ArgumentParser(description='VMware ESXi/vCenter Health Check')
    parser.add_argument('--host', required=True, help='vCenter or ESXi hostname/IP')
    parser.add_argument('--user', required=True, help='username')
    parser.add_argument('--password', required=True, help='password')
    parser.add_argument('--output', help='HTML report file')
    parser.add_argument('--template', help='directory containing the template')
    parser.add_argument('--template-file', default='template.html',
                        help='name of the HTML template file')
    args = parser.parse_args()

    checker = VMwareHealthCheck(args.host, args.user, args.password)
    try:
        checker.connect()

        hosts = checker.get_hosts()
        hosts_data = []
        all_vms = []
        summary = {
            'hosts': 0,
            'vms': 0,
            'datastores': 0,
            'networks': 0,
        }
        for host in hosts:
            logger.info("Processing host %s", host.name)
            security = checker.security_check(host)
            performance = checker.performance_check(host)
            best_practice = checker.best_practice_check(host)
            resource_pools = checker.resource_pool_check(host)
            zombie_vmdks = checker.zombie_vmdk_check(host)
            ntp_ok = checker.ntp_config_check(host)
            update_ok = checker.update_compliance_check(host)
            dns_ok = checker.dns_consistency_check(host)
            storage_warn = checker.storage_overusage(host)
            iscsi_rr = checker.iscsi_roundrobin_check(host)
            runtime = checker.host_runtime_info(host)
            cluster = checker.cluster_features(host)
            vm_info = []
            counters = checker._build_perf_counter_map()
            for vm in getattr(host, 'vm', []):
                metrics = checker.vm_performance_check(vm, counters)
                extra = checker.vm_extra_info(vm)
                metrics.update(extra)
                vm_info.append({'name': vm.name, 'metrics': metrics})
                all_vms.append({'name': vm.name, 'metrics': metrics})
                summary['vms'] += 1

            if vm_info:
                avg_ready = sum(v['metrics'].get('cpu_ready_ms', 0) for v in vm_info) / len(vm_info)
            else:
                avg_ready = 0
            performance['avg_cpu_ready_ms'] = avg_ready

            summary['hosts'] += 1
            summary['datastores'] += len(getattr(host, 'datastore', []))
            summary['networks'] += len(getattr(host, 'network', []))

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
                    if mk in ('cpu_usage_pct', 'mem_usage_pct'):
                        mv = round(mv * 100, 2)
                    print('    {}: {}'.format(mk, mv))
            print()

            hosts_data.append({
                'name': host.name,
                'security': security,
                'performance': performance,
                'best_practice': best_practice,
                'runtime': runtime,
                'cluster': cluster,
                'resource_pools': resource_pools,
                'zombie_vmdks': zombie_vmdks,
                'ntp_ok': ntp_ok,
                'update_ok': update_ok,
                'dns_ok': dns_ok,
                'storage_warn': storage_warn,
                'iscsi_rr': iscsi_rr,
                'vms': vm_info,
            })

        # Basic health scoring
        scores = {
            'performance': 100,
            'storage': 100,
            'security': 100,
            'availability': 100,
        }
        overall_score = sum(scores.values()) / 4

        print('Environment summary:', summary)
        print('Health scores:', scores, 'overall:', overall_score)

        if args.output:
            checker.generate_report(
                hosts_data, all_vms, args.output, args.template, args.template_file
            )
            logger.info("HTML report written to %s", args.output)
    finally:
        checker.disconnect()

if __name__ == '__main__':
    main()
