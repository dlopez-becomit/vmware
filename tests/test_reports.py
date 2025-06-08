import os
import sys
import json
import types
from unittest.mock import patch

# Provide dummy pyVmomi modules so vmware_healthcheck can be imported without
# the real pyvmomi dependency.
pyvim = types.ModuleType("pyVim")
connect_mod = types.ModuleType("pyVim.connect")
connect_mod.SmartConnect = lambda *a, **k: None
connect_mod.Disconnect = lambda *a, **k: None
sys.modules.setdefault("pyVim", pyvim)
sys.modules.setdefault("pyVim.connect", connect_mod)
pyvmomi = types.ModuleType("pyVmomi")
vim_mod = types.ModuleType("pyVmomi.vim")
sys.modules.setdefault("pyVmomi", pyvmomi)
sys.modules.setdefault("pyVmomi.vim", vim_mod)

# Stub matplotlib to avoid heavy dependency in tests
mpl = types.ModuleType("matplotlib")
mpl.use = lambda *a, **k: None
pyplot_mod = types.ModuleType("matplotlib.pyplot")
pyplot_mod.subplots = lambda *a, **k: (None, types.SimpleNamespace(bar=lambda *a, **k: None, set_xticks=lambda *a, **k: None, legend=lambda: None, set_xticklabels=lambda *a, **k: None))
pyplot_mod.savefig = lambda *a, **k: None
pyplot_mod.tight_layout = lambda *a, **k: None
pyplot_mod.close = lambda *a, **k: None
sys.modules.setdefault("matplotlib", mpl)
sys.modules.setdefault("matplotlib.pyplot", pyplot_mod)

# Stub openai for openai_report import
openai_mod = types.ModuleType("openai")
class DummyChat:
    @staticmethod
    def create(*a, **k):
        return {"choices": [{"message": {"content": ""}}]}

openai_mod.ChatCompletion = DummyChat
sys.modules.setdefault("openai", openai_mod)

# Minimal stub for jinja2 just to load templates and perform basic substitution
jinja2_mod = types.ModuleType("jinja2")

class DummyTemplate:
    def __init__(self, text):
        self.text = text

    def render(self, **kwargs):
        result = self.text
        for k, v in kwargs.items():
            result = result.replace(f"{{{{ {k} }}}}", str(v))
        return result


class DummyLoader:
    def __init__(self, searchpath):
        self.searchpath = searchpath


class DummyEnvironment:
    def __init__(self, loader):
        self.loader = loader

    def get_template(self, name):
        path = os.path.join(self.loader.searchpath, name)
        with open(path, encoding="utf-8") as f:
            return DummyTemplate(f.read())


jinja2_mod.Environment = DummyEnvironment
jinja2_mod.FileSystemLoader = DummyLoader
jinja2_mod.TemplateNotFound = type('TemplateNotFound', (Exception,), {})
sys.modules.setdefault("jinja2", jinja2_mod)

from vmware_healthcheck import VMwareHealthCheck

# Dummy host and VM data for tests
HOSTS = [
    {
        'name': 'h1',
        'runtime': {'uptime_seconds': 86400},
        'performance': {
            'cpu_usage_pct': 10,
            'memory_usage_pct': 20,
            'memory_usage': 2048,
            'cpu_cores': 4,
            'datastores': [
                {'name': 'ds1', 'usage_pct': 70, 'capacity_gb': 100, 'free_gb': 30}
            ],
        },
        'best_practice': {
            'network': ['n1'],
        },
        'security': {
            'services': {'ssh': False, 'esxi_shell': False},
            'ipv6_enabled': False,
        },
        'cluster': {'ha_enabled': True, 'drs_enabled': True},
        'resource_pools': 1,
        'zombie_vmdks': 0,
        'ntp_ok': True,
        'update_ok': True,
        'storage_warn': False,
        'iscsi_rr': True,
        'dns_ok': True,
    },
    {
        'name': 'h2',
        'runtime': {'uptime_seconds': 172800},
        'performance': {
            'cpu_usage_pct': 15,
            'memory_usage_pct': 25,
            'memory_usage': 4096,
            'cpu_cores': 8,
            'datastores': [
                {'name': 'ds2', 'usage_pct': 60, 'capacity_gb': 200, 'free_gb': 80}
            ],
        },
        'best_practice': {
            'network': ['n1', 'n2'],
        },
        'security': {
            'services': {'ssh': False, 'esxi_shell': False},
            'ipv6_enabled': False,
        },
        'cluster': {'ha_enabled': True, 'drs_enabled': True},
        'resource_pools': 2,
        'zombie_vmdks': 0,
        'ntp_ok': True,
        'update_ok': True,
        'storage_warn': False,
        'iscsi_rr': True,
        'dns_ok': True,
    },
]

VMS = [
    {
        'name': 'vm1',
        'metrics': {
            'cpu_ready_ms': 50,
            'mem_usage_pct': 0.5,
            'disk_free_pct': 10,
            'iops': 100,
            'net_throughput_kbps': 1000,
            'power_state': 'poweredOn',
            'num_cpu': 2,
            'disk_reads': 0,
            'disk_writes': 0,
            'net_rx_kbps': 0,
            'net_tx_kbps': 0,
            'ballooned_memory_mb': 0,
            'has_snapshot': False,
            'tools_status': 'toolsOk',
        },
    },
    {
        'name': 'vm2',
        'metrics': {
            'cpu_ready_ms': 30,
            'mem_usage_pct': 0.3,
            'disk_free_pct': 20,
            'iops': 80,
            'net_throughput_kbps': 800,
            'power_state': 'poweredOn',
            'num_cpu': 2,
            'disk_reads': 0,
            'disk_writes': 0,
            'net_rx_kbps': 0,
            'net_tx_kbps': 0,
            'ballooned_memory_mb': 0,
            'has_snapshot': False,
            'tools_status': 'toolsOk',
        },
    },
]

REQUIRED_KEYS = {
    'health_score', 'health_state', 'health_message', 'uptime', 'alerts',
    'sla', 'hosts', 'vms', 'datastores_count', 'networks_count',
    'categories', 'cpu_hosts', 'ram_hosts', 'datastore_usage',
    'indicators', 'top_cpu_ready', 'top_ram', 'datastores',
    'top_disk_free', 'top_iops', 'top_network', 'report_date'
}


def _checker():
    return VMwareHealthCheck('vc', 'u', 'p')


def test_build_report_data_structure():
    checker = _checker()
    with patch.object(checker, 'licensing_check', return_value=['key']), \
         patch.object(checker, 'backup_config_check', return_value=0), \
         patch.object(checker, 'folder_inconsistencies', return_value=[]):
        data = checker._build_report_data(HOSTS, VMS, chart='c')
        checker._validate_report_data(data)
        assert REQUIRED_KEYS.issubset(data.keys())


def test_generate_report_html(tmp_path):
    output = tmp_path / 'out.html'
    checker = _checker()
    with patch.object(checker, '_create_chart', return_value='c'), \
         patch.object(checker, 'licensing_check', return_value=['key']), \
         patch.object(checker, 'backup_config_check', return_value=0), \
         patch.object(checker, 'folder_inconsistencies', return_value=[]), \
         patch('openai_connector.fetch_completion', return_value='AI text'):
        checker.generate_report(HOSTS, VMS, str(output), template_file='template_a_detailed.html')

    html = output.read_text()
    assert 'Resumen de Categorías' in html
    assert 'Análisis Detallado' in html
    assert 'Rendimiento' in html
    assert 'Seguridad' in html
    assert 'Disponibilidad' in html
    assert 'AI text' in html


def test_generate_report_full_html(tmp_path):
    output = tmp_path / 'full.html'
    checker = _checker()
    with patch.object(checker, '_create_chart', return_value='c'), \
         patch.object(checker, 'licensing_check', return_value=['key']), \
         patch.object(checker, 'backup_config_check', return_value=0), \
         patch.object(checker, 'folder_inconsistencies', return_value=[]), \
         patch('openai_connector.fetch_completion', return_value='AI text'):
        checker.generate_report(HOSTS, VMS, str(output), template_file='template_full.html')

    html = output.read_text()
    assert 'Recomendaciones y Plan de Acción' in html
    assert 'Glosario' in html
    assert 'AI text' in html


def test_generate_full_report_html(tmp_path):
    output = tmp_path / 'full2.html'
    checker = _checker()
    with patch.object(checker, '_create_chart', return_value='c'), \
         patch.object(checker, 'licensing_check', return_value=['key']), \
         patch.object(checker, 'backup_config_check', return_value=0), \
         patch.object(checker, 'folder_inconsistencies', return_value=[]), \
         patch('openai_connector.fetch_completion', return_value='AI text'):
        data = checker._build_report_data(HOSTS, VMS, chart='c')
        checker._validate_report_data(data, template_file='template_full.html')
        checker.generate_report(HOSTS, VMS, str(output), template_file='template_full.html')

    html = output.read_text()
    assert 'portada' in html.lower()
    assert 'Resumen Ejecutivo' in html
    assert 'Conclusiones' in html
    assert 'AI text' in html


def test_generate_spanish_report_html(tmp_path):
    output = tmp_path / 'full_es.html'
    checker = _checker()
    with patch.object(checker, '_create_chart', return_value='c'), \
         patch.object(checker, 'licensing_check', return_value=['key']), \
         patch.object(checker, 'backup_config_check', return_value=0), \
         patch.object(checker, 'folder_inconsistencies', return_value=[]), \
         patch('openai_connector.fetch_completion', return_value='AI text'):
        checker.generate_report(HOSTS, VMS, str(output), template_file='template_full_es.html')

    html = output.read_text()
    assert 'Glosario de Términos Técnicos' in html


def test_configure_openai_from_file(tmp_path):
    cfg = {
        "api_key": "key",
        "api_type": "azure",
        "api_base": "base",
        "api_version": "v",
        "model": "m",
    }
    cfg_file = tmp_path / "cfg.json"
    cfg_file.write_text(json.dumps(cfg))

    import openai_connector

    openai_connector.configure_openai(config_file=str(cfg_file))
    import openai as openai_mod

    assert openai_mod.api_key == "key"
    assert openai_mod.api_type == "azure"
    assert openai_mod.api_base == "base"
    assert openai_mod.api_version == "v"
    assert openai_connector._DEFAULT_MODEL == "m"


def test_configure_openai_env_overrides_file(monkeypatch, tmp_path):
    cfg = {
        "api_key": "file-key",
        "api_type": "openai",
        "model": "file-model",
    }
    cfg_file = tmp_path / "cfg.json"
    cfg_file.write_text(json.dumps(cfg))

    monkeypatch.setenv("OPENAI_API_KEY", "env-key")
    monkeypatch.setenv("OPENAI_API_TYPE", "azure")
    monkeypatch.setenv("OPENAI_MODEL", "env-model")

    import openai_connector

    openai_connector.configure_openai(config_file=str(cfg_file))
    import openai as openai_mod

    assert openai_mod.api_key == "env-key"
    assert openai_mod.api_type == "azure"
    assert openai_connector._DEFAULT_MODEL == "env-model"


def test_configure_openai_verbose_logs(monkeypatch, capsys):
    monkeypatch.setenv("OPENAI_CONFIG_FILE", "missing.json")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    import importlib
    import openai_connector
    importlib.reload(openai_connector)

    openai_connector.configure_openai(verbose=True)
    captured = capsys.readouterr().out
    assert "missing.json" in captured
    assert "no definido" in captured.lower()

