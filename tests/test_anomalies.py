import pandas as pd

from lavaflow_suite import anomalies


def _agg(start="2024-03-01", end="2024-03-20"):
    df = anomalies.load_historical_data()
    return df, anomalies.aggregate_counts(df, start, end, week_day=3)


def test_load_historical_data_reads_all_sensors(project):
    df = anomalies.load_historical_data()
    assert set(df["source"]) == set(anomalies.SENSORS)
    assert df["acq_date"].notna().all()
    # MODIS file uses DD/MM/YYYY: dates must still fall in March 2024
    modis = df[df["source"] == "MODIS (AQUA/TERRA)"]
    assert modis["acq_date"].dt.month.eq(3).all()


def test_totals_agree_between_daily_weekly_monthly_and_summary(project):
    df, agg = _agg()
    total = agg["summary"]["total_period"]
    assert total == len(df)
    assert agg["daily"]["Total"].sum() == total
    assert agg["weekly"]["Total"].sum() == total
    assert agg["monthly"]["Total"].sum() == total
    # Total column is the sum of the sensor columns
    assert (agg["weekly"][anomalies.SENSORS].sum(axis=1) == agg["weekly"]["Total"]).all()


def test_short_period_summary(project):
    _, agg = _agg()
    sm = agg["summary"]
    assert agg["short"] and sm["short"]
    assert sm["n_days"] == 20
    assert sm["peak_day"] == agg["daily"]["Total"].max()
    labels = [t[0] for t in anomalies.summary_tiles(sm)]
    assert "Max per day" in labels and "Max per week" in labels
    assert not any("month" in lbl.lower() for lbl in labels)


def test_long_period_summary(project):
    _, agg = _agg("2024-01-01", "2024-06-30")
    sm = agg["summary"]
    assert not sm["short"]
    labels = [t[0] for t in anomalies.summary_tiles(sm)]
    assert "Max per month" in labels and "Last month" in labels
    assert sm["peak_month_label"] == "March 2024"


def test_partial_weeks_flagged(project):
    # 2024-03-01 is a Friday; weeks start on Thursday (week_day=3)
    _, agg = _agg("2024-03-01", "2024-03-20")
    assert pd.Timestamp("2024-02-29") in agg["partial_weeks"]       # starts mid-week
    assert agg["summary"]["last_week_partial"] is False              # 14-20 March is complete
    _, agg = _agg("2024-03-01", "2024-03-18")
    assert agg["summary"]["last_week_partial"] is True
    assert agg["summary"]["last_week_end"] == "18/03/2024"


def test_empty_data():
    agg = anomalies.aggregate_counts(pd.DataFrame(), "2024-03-01", "2024-03-10")
    assert agg["summary"] == {}
    assert agg["daily"]["Total"].sum() == 0


def test_figure_panels_follow_period_length(project):
    _, short = _agg()
    fig = anomalies.build_counts_figure(short, "Testvolcano")
    # one bar trace per sensor per panel
    assert len([t for t in fig.data if t.type == "bar"]) == 2 * len(anomalies.SENSORS)
    # every bar with data gets a vertical total label
    labels = [a for a in fig.layout.annotations if a.textangle == -90]
    assert len(labels) >= (short["daily"]["Total"] > 0).sum()

    _, long_ = _agg("2024-01-01", "2024-06-30")
    fig2 = anomalies.build_counts_figure(long_, "Testvolcano")
    # long periods: weekly (26 weeks) on top, monthly (6 months) below
    bars2 = [t for t in fig2.data if t.type == "bar"]
    top, bottom = bars2[0], bars2[len(anomalies.SENSORS)]
    assert len(top.x) == len(long_["weekly"]) and len(bottom.x) == len(long_["monthly"])
    top_s = [t for t in fig.data if t.type == "bar"][0]
    assert len(top_s.x) == len(short["daily"])
