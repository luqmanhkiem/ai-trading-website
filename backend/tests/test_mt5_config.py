import importlib.util
from pathlib import Path
import pytest

@pytest.fixture
def helper(tmp_path):
    source=Path(__file__).resolve().parents[2]/'scripts/configure_mt5.py'
    spec=importlib.util.spec_from_file_location('mt5_config',source)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.ROOT=tmp_path
    (tmp_path/'backend').mkdir()
    (tmp_path/'backend/.env.example').write_text('DATA_MODE=simulated\nTELEGRAM_ENABLED=false\n')
    return module

def test_configure_preserves_settings_and_does_not_print_secret(helper,capsys):
    helper.configure('XAUUSD.vxc')
    path=helper.ROOT/'backend/.env';text=path.read_text()
    token=[line.split('=',1)[1] for line in text.splitlines() if line.startswith('MT5_BRIDGE_TOKEN=')][0]
    assert len(token)>=32 and token not in capsys.readouterr().out
    assert 'DATA_MODE=mt5' in text and 'TELEGRAM_ENABLED=false' in text
    assert 'MT5_SYMBOL=XAUUSD.vxc' in text
    assert path.stat().st_mode & 0o777 == 0o600
    helper.configure('XAUUSD.vx')
    assert token in path.read_text() and path.read_text().count('DATA_MODE=')==1

def test_invalid_symbol_never_writes(helper):
    with pytest.raises(ValueError):helper.configure('EURUSD')
    assert not (helper.ROOT/'backend/.env').exists()
