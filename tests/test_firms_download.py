"""FIRMS download logic with the NASA API mocked (no network, no real key)."""
import os

import pandas as pd
import pytest

from lavaflow_suite import firms_download as fd

from conftest import synthetic_viirs


def test_calculate_bbox_is_centred_on_vent():
    w, s, e, n = map(float, fd.calculate_bbox(-0.4, -91.5, 11132).split(","))
    assert (w + e) / 2 == pytest.approx(-91.5, abs=1e-4)
    assert (s + n) / 2 == pytest.approx(-0.4, abs=1e-4)
    assert n - s == pytest.approx(0.2, abs=1e-3)


@pytest.mark.parametrize("values, expected", [
    (["2024-03-05", "2024-03-06"], ["2024-03-05", "2024-03-06"]),
    (["05/03/2024", "06/03/2024"], ["2024-03-05", "2024-03-06"]),
    (["5/3/24", "6/3/24"], ["2024-03-05", "2024-03-06"]),
])
def test_parse_acq_date(values, expected):
    out = fd.parse_acq_date(pd.Series(values))
    assert list(out.dt.strftime("%Y-%m-%d")) == expected


def test_migrate_historical_dates(workdir):
    os.makedirs("p")
    pd.DataFrame({"acq_date": ["05/03/2024"], "frp": [1]}).to_csv("p/h.csv", index=False)
    fd.migrate_historical_dates("p", {"x": "h.csv", "missing": "nope.csv"})
    assert pd.read_csv("p/h.csv")["acq_date"].iloc[0] == "2024-03-05"


def test_download_requires_key(project):
    msg = fd.process_download("2024-03-01", "2024-03-02", 5000)
    assert "API Key" in str(msg)


def test_download_without_project(workdir):
    assert "Active volcano not set" in str(fd.process_download("2024-03-01", "2024-03-02", 5000))


class _Resp:
    def __init__(self, text, status=200):
        self.text, self.status_code = text, status

    def json(self):
        return {"current_transactions": 7}


def test_download_merges_and_deduplicates(project, monkeypatch):
    cfg_file = os.path.join(project, "config_Testvolcano.txt")
    txt = open(cfg_file).read().replace("INSERT_YOUR_MAP_KEY_HERE", "FAKEKEY")
    open(cfg_file, "w").write(txt)

    calls = []

    def fake_get(url, **kw):
        calls.append(url)
        if "mapkey_status" in url:
            return _Resp("")
        assert "/FAKEKEY/" in url
        # the API returns the new days; the first day overlaps the stored history
        start = url.rstrip("/").split("/")[-1]
        days = int(url.rstrip("/").split("/")[-2])
        return _Resp(synthetic_viirs(start, days, "N", seed=42).to_csv(index=False))

    monkeypatch.setattr(fd.requests, "get", fake_get)
    before = pd.read_csv(os.path.join(project, "historical_VIIRS_SNPP_NRT_Testvolcano.csv"))
    fd.process_download("2024-03-20", "2024-04-02", 5000)

    data_calls = [c for c in calls if "/api/area/" in c]
    n_chunks = -(-14 // fd.FIRMS_API_MAX_DAYS)
    assert len(data_calls) == 4 * n_chunks        # every sensor, split into API-sized chunks
    after = pd.read_csv(os.path.join(project, "historical_VIIRS_SNPP_NRT_Testvolcano.csv"))
    assert after["acq_date"].str.match(r"^\d{4}-\d{2}-\d{2}$").all()
    assert after["acq_date"].max() == "2024-04-02"
    # 20 March was refreshed, not duplicated
    per_day_before = (before["acq_date"] == "2024-03-20").sum()
    assert (after["acq_date"] == "2024-03-20").sum() == per_day_before
    assert not after.duplicated(subset=["latitude", "longitude", "acq_date", "acq_time"]).any()
