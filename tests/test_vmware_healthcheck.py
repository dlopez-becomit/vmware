import unittest
from unittest import mock
from types import SimpleNamespace
import os
import tempfile
import sys

# Provide dummy pyVim and pyVmomi modules so the tests do not require the real VMware libraries to be installed.
vim_fake = mock.MagicMock()
pyvmomi_fake = mock.MagicMock(vim=vim_fake)
sys.modules.setdefault('pyVmomi', pyvmomi_fake)
sys.modules.setdefault('pyVmomi.vim', vim_fake)
connect_fake = mock.MagicMock(SmartConnect=mock.MagicMock(), Disconnect=mock.MagicMock())
pyvim_fake = mock.MagicMock(connect=connect_fake)
sys.modules.setdefault('pyVim', pyvim_fake)
sys.modules.setdefault('pyVim.connect', connect_fake)

# Stub matplotlib modules used by the script so tests don't require the actual library.
matplotlib_fake = mock.MagicMock()
pyplot_fake = mock.MagicMock()
matplotlib_fake.pyplot = pyplot_fake
sys.modules.setdefault('matplotlib', matplotlib_fake)
sys.modules.setdefault('matplotlib.pyplot', pyplot_fake)

# Stub jinja2 so it is not required during tests
class FakeTemplate:
    def render(self, *args, **kwargs):
        return "VMware Health Check Report"

class FakeEnvironment:
    def __init__(self, *args, **kwargs):
        pass
    def get_template(self, name):
        return FakeTemplate()

jinja2_fake = mock.MagicMock(Environment=FakeEnvironment, FileSystemLoader=mock.MagicMock())
sys.modules.setdefault('jinja2', jinja2_fake)

from vmware_healthcheck import VMwareHealthCheck


class VMwareHealthCheckTests(unittest.TestCase):
    def _fake_host(self):
        host = SimpleNamespace()
        host.name = 'esxi1'
        host.summary = SimpleNamespace(
            config=SimpleNamespace(
                name='esxi1',
                product=SimpleNamespace(fullName='ESXi 7')
            ),
            quickStats=SimpleNamespace(
                overallCpuUsage=1000,
                overallMemoryUsage=2048
            )
        )
        host.config = SimpleNamespace(
            lockdownMode='strict'
        )
        # Minimal network config so performance and best practice checks work
        host.config.network = SimpleNamespace(pnic=[])
        host.configManager = SimpleNamespace(
            serviceSystem=SimpleNamespace(
                serviceInfo=SimpleNamespace(
                    service=[
                        SimpleNamespace(key='TSM-SSH', running=True),
                        SimpleNamespace(key='TSM', running=False)
                    ]
                )
            ),
            firewallSystem=SimpleNamespace(
                firewallInfo=SimpleNamespace(
                    ruleset=[SimpleNamespace(key='ssh'), SimpleNamespace(key='http')]
                )
            )
        )
        host.config.dateTimeInfo = SimpleNamespace(
            ntpConfig=SimpleNamespace(server=['0.pool.ntp.org', '1.pool.ntp.org'])
        )
        host.hardware = SimpleNamespace(
            cpuPkg=[SimpleNamespace(description='Intel Xeon')],
            memorySize=16 * 1024 ** 3,
            biosInfo=SimpleNamespace(biosVersion='1.0'),
            systemInfo=SimpleNamespace(vendor='Dell', model='PowerEdge')
        )
        host.datastore = [
            SimpleNamespace(
                summary=SimpleNamespace(
                    name='ds1',
                    capacity=100 * 1024 ** 3,
                    freeSpace=50 * 1024 ** 3
                )
            )
        ]
        host.network = [SimpleNamespace(name='nw1')]
        host.vm = [SimpleNamespace(name='vm1'), SimpleNamespace(name='vm2')]
        return host

    def test_security_check(self):
        checker = VMwareHealthCheck('h', 'u', 'p')
        host = self._fake_host()
        result = checker.security_check(host)
        self.assertEqual(result['lockdown_mode'], 'strict')
        self.assertIn('ssh', result['services'])
        self.assertTrue(result['services']['ssh'])
        self.assertEqual(result['ntp_servers'], ['0.pool.ntp.org', '1.pool.ntp.org'])
        self.assertEqual(result['firewall_exceptions'], ['ssh', 'http'])

    def test_performance_check(self):
        checker = VMwareHealthCheck('h', 'u', 'p')
        host = self._fake_host()
        result = checker.performance_check(host)
        self.assertEqual(result['cpu_usage'], 1000)
        self.assertEqual(result['memory_usage'], 2048)
        self.assertEqual(result['num_vms'], 2)

    def test_best_practice_check(self):
        checker = VMwareHealthCheck('h', 'u', 'p')
        host = self._fake_host()
        result = checker.best_practice_check(host)
        self.assertEqual(result['cpu_model'], 'Intel Xeon')
        self.assertEqual(result['memory_total_gb'], 16)
        self.assertEqual(result['datastores'][0]['name'], 'ds1')
        self.assertEqual(result['network'], [])

    def test_generate_report_creates_file(self):
        checker = VMwareHealthCheck('h', 'u', 'p')
        hosts_data = [
            {
                'name': 'host1',
                'security': {'lockdown': 'on'},
                'performance': {'cpu_usage': 10, 'memory_usage': 20},
                'best_practice': {'cpu_model': 'model'},
                'vms': []
            }
        ]
        vm_data = []
        with tempfile.TemporaryDirectory() as td:
            output = os.path.join(td, 'report.html')
            with mock.patch.object(checker, '_create_chart', return_value='img'):
                checker.generate_report(hosts_data, vm_data, output)
            self.assertTrue(os.path.exists(output))
            with open(output, 'r', encoding='utf-8') as f:
                content = f.read()
            self.assertIn('VMware Health Check Report', content)


if __name__ == '__main__':
    unittest.main()
