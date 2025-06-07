import unittest
from unittest import mock
from types import SimpleNamespace
import types
import os
import tempfile
import sys

# Provide dummy pyVim and pyVmomi modules so the tests do not require the real
# VMware libraries to be installed.
vim_fake = mock.MagicMock()
pyvmomi_fake = mock.MagicMock(vim=vim_fake)
sys.modules.setdefault('pyVmomi', pyvmomi_fake)
sys.modules.setdefault('pyVmomi.vim', vim_fake)
connect_fake = mock.MagicMock(SmartConnect=mock.MagicMock(), Disconnect=mock.MagicMock())
pyvim_fake = mock.MagicMock(connect=connect_fake)
sys.modules.setdefault('pyVim', pyvim_fake)
sys.modules.setdefault('pyVim.connect', connect_fake)

# Stub matplotlib modules used by the script so tests don't require the actual
# library.
matplotlib_fake = mock.MagicMock()
pyplot_fake = mock.MagicMock()
matplotlib_fake.pyplot = pyplot_fake
sys.modules.setdefault('matplotlib', matplotlib_fake)
sys.modules.setdefault('matplotlib.pyplot', pyplot_fake)

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
            memorySize=16 * 1024 ** 3
        )
        host.datastore = [SimpleNamespace(info=SimpleNamespace(name='ds1'))]
        host.network = [SimpleNamespace(name='nw1')]
        host.vm = [SimpleNamespace(name='vm1'), SimpleNamespace(name='vm2')]
        return host

    def _fake_vm(self):
        vm = SimpleNamespace()
        vm.name = 'vmx'
        vm.snapshot = object()
        vm.guest = SimpleNamespace(toolsStatus='toolsOk')
        return vm

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
        self.assertEqual(result['datastores'], ['ds1'])
        self.assertEqual(result['network'], ['nw1'])

    def test_runtime_info(self):
        checker = VMwareHealthCheck('h', 'u', 'p')
        host = self._fake_host()
        host.runtime = SimpleNamespace(bootTime=None)
        info = checker.host_runtime_info(host)
        self.assertIn('uptime_seconds', info)

    def test_vm_extra_info(self):
        checker = VMwareHealthCheck('h', 'u', 'p')
        vm = self._fake_vm()
        info = checker.vm_extra_info(vm)
        self.assertTrue(info['has_snapshot'])
        self.assertEqual(info['tools_status'], 'toolsOk')

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

    def test_report_handles_string_datastores(self):
        checker = VMwareHealthCheck('h', 'u', 'p')
        hosts_data = [{
            'name': 'host1',
            'security': {},
            'performance': {
                'cpu_usage': 10,
                'memory_usage': 20,
                'datastores': [{'name': 'ds1', 'capacity_gb': 1, 'free_gb': 0.5}]
            },
            'best_practice': {
                'cpu_model': 'model',
                'memory_total_gb': 16,
                'datastores': ['ds1']
            },
            'vms': []
        }]
        with mock.patch.object(checker, '_create_chart', return_value='img'):
            html = checker._generate_report_default(hosts_data, [], 'img')
        self.assertIn('ds1', html)

    def test_generate_report_template_a(self):
        checker = VMwareHealthCheck('h', 'u', 'p')
        hosts_data = [{
            'name': 'host1',
            'security': {},
            'performance': {
                'cpu_usage': 10,
                'memory_usage': 20,
                'datastores': [{'name': 'ds1', 'capacity_gb': 1, 'free_gb': 0.5, 'usage_pct': 50}],
            },
            'best_practice': {},
            'cluster': {'ha_enabled': True, 'drs_enabled': True},
            'runtime': {'uptime_seconds': 86400},
            'vms': []
        }]
        vm_data = []
        with tempfile.TemporaryDirectory() as td:
            output = os.path.join(td, 'report.html')
            with mock.patch.object(checker, '_create_chart', return_value='img'):
                dummy_jinja = types.SimpleNamespace(
                    Environment=lambda loader: types.SimpleNamespace(
                        get_template=lambda name: types.SimpleNamespace(render=lambda **k: 'Rendered '+name)
                    ),
                    FileSystemLoader=lambda path: None
                )
                with mock.patch.dict('sys.modules', {'jinja2': dummy_jinja}):
                    checker.generate_report(hosts_data, vm_data, output, template_file='template_a.html')
            self.assertTrue(os.path.exists(output))
            with open(output, 'r', encoding='utf-8') as f:
                content = f.read()
            self.assertIn('Rendered template_a.html', content)

    def test_generate_report_template_a_content(self):
        checker = VMwareHealthCheck('h', 'u', 'p')
        hosts_data = [{
            'name': 'host1',
            'security': {'lockdown_mode': 'strict'},
            'performance': {
                'cpu_usage': 10,
                'memory_usage': 20,
                'datastores': [{'name': 'ds1', 'capacity_gb': 1, 'free_gb': 0.5, 'usage_pct': 50}],
            },
            'best_practice': {'network': ['n1']},
            'cluster': {'ha_enabled': True, 'drs_enabled': False},
            'runtime': {'uptime_seconds': 86400},
            'vms': []
        }]
        vm_data = [{
            'name': 'vm1',
            'metrics': {
                'cpu_ready_ms': 100,
                'mem_usage_pct': 0.5,
                'iops': 50,
                'net_throughput_kbps': 1000
            }
        }]
        with tempfile.TemporaryDirectory() as td:
            output = os.path.join(td, 'report.html')
            with mock.patch.object(checker, '_create_chart', return_value='img'):
                def render_dummy(**ctx):
                    return f"Score {ctx['health']['score']} Indicator {ctx['indicators'][0]['label']}"

                dummy_jinja = types.SimpleNamespace(
                    Environment=lambda loader: types.SimpleNamespace(
                        get_template=lambda name: types.SimpleNamespace(render=render_dummy)
                    ),
                    FileSystemLoader=lambda path: None
                )
                with mock.patch.dict('sys.modules', {'jinja2': dummy_jinja}):
                    checker.generate_report(hosts_data, vm_data, output, template_file='template_a.html')
            with open(output, 'r', encoding='utf-8') as f:
                content = f.read()
            self.assertIn('Score 100', content)
            self.assertIn('Indicator HA', content)

if __name__ == '__main__':
    unittest.main()
