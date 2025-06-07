import argparse
import ssl
from pyVim.connect import SmartConnect, Disconnect
from pyVmomi import vim

class VMwareHealthCheck:
    def __init__(self, host, user, password, port=443):
        self.host = host
        self.user = user
        self.password = password
        self.port = port
        self.si = None

    def connect(self):
        context = ssl._create_unverified_context()
        self.si = SmartConnect(host=self.host, user=self.user, pwd=self.password, port=self.port, sslContext=context)
        return self.si

    def disconnect(self):
        if self.si:
            Disconnect(self.si)

    def get_hosts(self):
        content = self.si.RetrieveContent()
        container = content.viewManager.CreateContainerView(content.rootFolder, [vim.HostSystem], True)
        hosts = list(container.view)
        container.Destroy()
        return hosts

    def security_check(self, host):
        summary = host.summary
        config = host.config
        security = {}
        security['name'] = summary.config.name
        security['version'] = summary.config.product.fullName
        security['lockdown_mode'] = config.adminDisabled
        security['services'] = {
            'ssh': any(s.key == 'TSM-SSH' and s.running for s in host.configManager.serviceSystem.serviceInfo.service),
            'esxi_shell': any(s.key == 'TSM' and s.running for s in host.configManager.serviceSystem.serviceInfo.service)
        }
        security['ntp_servers'] = [ntp.server for ntp in (config.dateTimeInfo.ntpConfig.server or [])]
        security['firewall_exceptions'] = [rule.key for rule in host.configManager.firewallSystem.firewallInfo.rules]
        return security

    def performance_check(self, host):
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
        bp = {}
        hardware = host.hardware
        bp['cpu_model'] = hardware.cpuPkg[0].description if hardware.cpuPkg else 'n/a'
        bp['memory_total'] = hardware.memorySize
        bp['datastores'] = [ds.info.name for ds in host.datastore]
        bp['network'] = [nw.name for nw in host.network]
        return bp


def main():
    parser = argparse.ArgumentParser(description='VMware ESXi/vCenter Health Check')
    parser.add_argument('--host', required=True, help='vCenter or ESXi hostname/IP')
    parser.add_argument('--user', required=True, help='username')
    parser.add_argument('--password', required=True, help='password')
    args = parser.parse_args()

    checker = VMwareHealthCheck(args.host, args.user, args.password)
    checker.connect()

    hosts = checker.get_hosts()
    for host in hosts:
        print('--- Host: {} ---'.format(host.name))
        print('Security:')
        for k, v in checker.security_check(host).items():
            print('  {}: {}'.format(k, v))
        print('Performance:')
        for k, v in checker.performance_check(host).items():
            print('  {}: {}'.format(k, v))
        print('Best Practices:')
        for k, v in checker.best_practice_check(host).items():
            print('  {}: {}'.format(k, v))
        print()

    checker.disconnect()

if __name__ == '__main__':
    main()
