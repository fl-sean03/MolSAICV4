"""Smoke tests for pm2msi — verify imports and config loading work.

For full pipeline tests with real systems, see the consumer projects
(e.g., 31-Hydrogenation/system-building/rn_v2/tests/).
"""

import pytest
from pm2msi import build, enrich, load_config, SystemConfig
from pm2msi.config import TemplateConfig, CellConfig


def test_imports():
    """All public API can be imported."""
    assert callable(build)
    assert callable(enrich)
    assert callable(load_config)
    assert SystemConfig is not None


def test_cell_config_explicit():
    """CellConfig with all dimensions set is_explicit."""
    cell = CellConfig(a=100.0, b=100.0, c=100.0)
    assert cell.is_explicit
    assert cell.a == 100.0


def test_cell_config_auto():
    """CellConfig with no dimensions is not explicit (auto mode)."""
    cell = CellConfig(padding=5.0)
    assert not cell.is_explicit
    assert cell.padding == 5.0


def test_template_config():
    """TemplateConfig accepts required fields."""
    tc = TemplateConfig(mdf="foo.mdf", pdb_resname="FOO", grouping="single")
    assert tc.mdf == "foo.mdf"
    assert tc.grouping == "single"


def test_load_config_yaml(tmp_path):
    """YAML config file loads correctly."""
    yaml_content = """
pdb: foo.pdb
templates:
  - mdf: a.mdf
    pdb_resname: A
    grouping: single
  - mdf: b.mdf
    pdb_resname: B
    grouping: separate
cell:
  a: 100.0
  b: 100.0
  c: 100.0
output: out
"""
    yaml_path = tmp_path / "system.yaml"
    yaml_path.write_text(yaml_content)
    config = load_config(str(yaml_path))
    assert config.pdb == "foo.pdb"
    assert len(config.templates) == 2
    assert config.cell.is_explicit
    assert config.output == "out"


def test_load_config_auto_cell(tmp_path):
    """YAML without cell uses auto mode."""
    yaml_content = """
pdb: foo.pdb
templates:
  - mdf: a.mdf
    pdb_resname: A
output: out
"""
    yaml_path = tmp_path / "system.yaml"
    yaml_path.write_text(yaml_content)
    config = load_config(str(yaml_path))
    assert not config.cell.is_explicit
    assert config.cell.padding == 5.0
