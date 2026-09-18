"""Repository hygiene and example projects (skipped when run outside a checkout)."""
import glob
import os
import shutil

import pytest

from lavaflow_suite import common as lfc
from lavaflow_suite import mapper, speed

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXAMPLES = sorted(glob.glob(os.path.join(ROOT, "examples", "*", "config_*.txt")))


@pytest.mark.skipif(not EXAMPLES, reason="no example projects in this checkout")
@pytest.mark.parametrize("cfg_file", EXAMPLES, ids=lambda p: os.path.basename(os.path.dirname(p)))
def test_example_configs_have_no_private_key(cfg_file):
    for line in open(cfg_file, encoding="utf-8", errors="replace"):
        if line.strip().startswith("map_key"):
            value = line.split("=", 1)[1].strip()
            assert value in ("", "INSERT_YOUR_MAP_KEY_HERE"), \
                f"{cfg_file} contains a FIRMS MAP_KEY — remove it before committing"


@pytest.mark.skipif(not EXAMPLES, reason="no example projects in this checkout")
@pytest.mark.parametrize("cfg_file", EXAMPLES, ids=lambda p: os.path.basename(os.path.dirname(p)))
def test_example_project_runs_end_to_end(cfg_file, workdir):
    src = os.path.dirname(cfg_file)
    name = os.path.basename(src)
    if not glob.glob(os.path.join(src, "historical_VIIRS_*.csv")):
        pytest.skip("example data not present")
    dst = os.path.join("examples", name)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("*.html", "*.mp4", ".tile_cache"))
    lfc.set_active_folder(dst)
    cfg = lfc.load_global_config()
    out = mapper.run_filter(cfg, dst)
    assert len(out) > 0
    p = speed.process_speed_data(dst)
    assert p is not None and p["max_distance"].max() > 0
