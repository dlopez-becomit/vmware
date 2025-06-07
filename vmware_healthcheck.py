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
    def __init__(self, host, user, password, port=443):
        self.host = host
        self.user = user
        self.password = password
        self.port = port
        self.si = None

    def connect(self):
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
        except Exception as exc:
            logger.exception("Error connecting to %s", self.host)
            raise
        return self.si

    def disconnect(self):
        if self.si:
            logger.info("Disconnecting from %s", self.host)
            Disconnect(self.si)

    def get_hosts(self):
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
        logger.info("Gathering performance metrics from %s", host.name)
        summary = host.summary
        stats = summary.quickStats
        perf = {
            'cpu_usage': stats.overallCpuUsage,
            'memory_usage': stats.overallMemoryUsage,
            'num_vms': summary.runtime.numVms
        }
        # Additional metrics can be gathered from host.configManager or perfManager
        return perf

    def best_practice_check(self, host):
        logger.info("Checking best practices on %s", host.name)
        bp = {}
        hardware = host.hardware
        bp['cpu_model'] = hardware.cpuPkg[0].description if hardware.cpuPkg else 'n/a'
        bp['memory_total'] = hardware.memorySize
        bp['datastores'] = [ds.info.name for ds in host.datastore]
        bp['network'] = [nw.name for nw in host.network]
        return bp

    def _create_chart(self, hosts_data):
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

    def generate_report(self, hosts_data, output_file):
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

        for h in hosts_data:
            html.append(f"<h2>Host: {h['name']}</h2>")
            html.append("<h3>Security</h3><table>")
            for k, v in h['security'].items():
                html.append(f"<tr><th>{k}</th><td>{v}</td></tr>")
            html.append("</table>")

            html.append("<h3>Performance</h3><table>")
            for k, v in h['performance'].items():
                html.append(f"<tr><th>{k}</th><td>{v}</td></tr>")
            html.append("</table>")

            html.append("<h3>Best Practices</h3><table>")
            for k, v in h['best_practice'].items():
                html.append(f"<tr><th>{k}</th><td>{v}</td></tr>")
            html.append("</table>")

        html.append("</body></html>")

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(html))


def main():
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
        for host in hosts:
            logger.info("Processing host %s", host.name)
            security = checker.security_check(host)
            performance = checker.performance_check(host)
            best_practice = checker.best_practice_check(host)

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
            print()

            hosts_data.append({
                'name': host.name,
                'security': security,
                'performance': performance,
                'best_practice': best_practice
            })

        if args.output:
            checker.generate_report(hosts_data, args.output)
            logger.info("HTML report written to %s", args.output)
    finally:
        checker.disconnect()

if __name__ == '__main__':
    main()
