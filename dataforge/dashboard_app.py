"""Run: streamlit run dataforge/dashboard_app.py --server.address 127.0.0.1

The dashboard issues bounded, aggregated, read-only SQL. It is a local demo,
not an authenticated public deployment or a live NYC government service.
"""

from __future__ import annotations

import hashlib
import os
import sys
from datetime import timedelta
from pathlib import Path

# Streamlit executes this file as a script; ensure package imports work on Win.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def build_daily_trend_chart(rows: list[dict]):
    """Render a source-local daily trend with exactly one date category per day.

    Using a temporal axis for midnight timestamps introduced misleading 12 PM
    tick labels between observations in the Windows five-day dashboard.
    """
    import altair as alt
    import pandas as pd

    frame = pd.DataFrame(rows)
    if frame.empty:
        return None
    frame["day_label"] = pd.to_datetime(frame["day"]).dt.strftime("%Y-%m-%d")
    long_frame = frame.melt(
        id_vars="day_label", value_vars=["requests", "closed_requests"],
        var_name="metric", value_name="count",
    )
    return (
        alt.Chart(long_frame).mark_line(point=True, strokeWidth=2)
        .encode(
            x=alt.X("day_label:O", sort="ascending", title="Created date",
                    axis=alt.Axis(labelAngle=-35, labelOverlap="greedy")),
            y=alt.Y("count:Q", title="Requests"),
            color=alt.Color("metric:N", title="Series"),
            tooltip=[alt.Tooltip("day_label:O", title="Date"), "metric:N", "count:Q"],
        )
        .properties(height=330)
    )


def main() -> None:
    import pandas as pd
    import streamlit as st

    from dataforge.analytics import (
        DashboardFilters, aggregate_csv, dimension_options_query, extent_query, fetch_rows,
        metric_query,
    )

    st.set_page_config(page_title="DataForge 360 | NYC 311 Intelligence",
                       page_icon="🏙️", layout="wide", initial_sidebar_state="expanded")
    st.markdown("""
    <style>
      .block-container {padding-top: 2.1rem; padding-bottom: 2rem; max-width: 1500px;}
      h1, h2, h3 {letter-spacing: -0.025em;}
      div[data-testid="stMetric"] {
        border: 1px solid rgba(110,130,155,.25); border-radius: 16px;
        padding: 18px; background: rgba(91,124,178,.055);
      }
      div[data-testid="stMetricValue"] {font-weight: 750;}
    </style>""", unsafe_allow_html=True)

    @st.cache_data(ttl=240, max_entries=40, show_spinner=False)
    def cached_metric(metric: str, filters: DashboardFilters, schema: str,
                      db_signature: str, _dsn: str) -> list[dict]:
        statement, parameters = metric_query(metric, filters, prefix=schema)
        return fetch_rows(_dsn, statement, parameters)

    @st.cache_data(ttl=240, max_entries=12, show_spinner=False)
    def cached_info(key: str, schema: str, db_signature: str, _dsn: str) -> list[dict]:
        statement, parameters = (extent_query(prefix=schema) if key == "extent"
                                 else dimension_options_query(key, prefix=schema))
        return fetch_rows(_dsn, statement, parameters)

    st.title("🏙️ DataForge 360")
    st.caption("NYC 311 · Data Engineering & Service Operations Intelligence")
    dsn = os.environ.get("DATABASE_URL", "")
    schema = os.environ.get("DBT_SCHEMA", "analytics")
    if not dsn:
        st.error("DATABASE_URL is not set. Configure the local warehouse before opening the dashboard.")
        st.code("$env:DATABASE_URL = '<your local PostgreSQL connection URL>'",
                language="powershell")
        st.stop()

    signature = hashlib.sha256(dsn.encode("utf-8")).hexdigest()
    try:
        extent = cached_info("extent", schema, signature, dsn)[0]
    except Exception:
        st.error("Could not query analytics marts. Check Docker, DATABASE_URL and the dbt build.")
        st.stop()
    if not extent["fact_rows"]:
        st.warning("No service requests in the analytics fact. Ingest records and run dbt first.")
        st.stop()

    first_day, last_day = extent["first_day"], extent["last_day"]
    min_default = max(first_day, last_day - timedelta(days=29))
    with st.sidebar:
        st.header("Explore service requests")
        st.caption("All filters execute inside PostgreSQL; the browser receives aggregates only.")
        start = st.date_input("Created from", min_default,
                              min_value=first_day, max_value=last_day)
        end = st.date_input("Created through", last_day,
                            min_value=first_day, max_value=last_day)
        if start > end or (end - start).days > 366:
            st.error("Use an ascending date range no longer than 367 calendar days.")
            st.stop()
        try:
            options = {
                name: [row["label"] for row in cached_info(name, schema, signature, dsn)]
                for name in ("borough", "agency", "complaint", "status")
            }
        except Exception:
            st.error("Could not load dimension filters. Check the analytics marts.")
            st.stop()
        boroughs = st.multiselect("Borough", options["borough"], placeholder="All boroughs")
        agencies = st.multiselect("Agency", options["agency"], placeholder="All agencies")
        complaints = st.multiselect("Problem / complaint", options["complaint"],
                                    placeholder="All complaint types")
        statuses = st.multiselect("Status", options["status"], placeholder="All statuses")
        st.caption("For larger backfills, explore a narrower interval to keep queries responsive.")

    try:
        filters = DashboardFilters(
            start=start, end=end, boroughs=tuple(boroughs), agencies=tuple(agencies),
            complaints=tuple(complaints), statuses=tuple(statuses),
        )
    except ValueError as exc:
        st.error(str(exc))
        st.stop()

    try:
        with st.spinner("Computing validated warehouse metrics …"):
            overview = cached_metric("overview", filters, schema, signature, dsn)[0]
            daily = cached_metric("daily", filters, schema, signature, dsn)
            borough = cached_metric("borough", filters, schema, signature, dsn)
            agency = cached_metric("agency", filters, schema, signature, dsn)
            complaint = cached_metric("complaint", filters, schema, signature, dsn)
            status = cached_metric("status", filters, schema, signature, dsn)
    except Exception:
        st.error("An analytics query failed. Verify the dbt marts and choose a narrower interval.")
        st.stop()

    total = overview["total_requests"]
    closed = overview["closed_requests"]
    median = overview["median_resolution_hours"]
    avg = overview["avg_resolution_hours"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Service requests", f"{total:,}")
    c2.metric("Closed requests", f"{closed:,}")
    c3.metric("Closure share", f"{closed / total * 100:.1f}%" if total else "—")
    c4.metric("Median closure time", f"{float(median):,.1f} h" if median is not None else "N/A")

    if not total:
        st.info("No requests matched the selected filters. Adjust the sidebar to explore another slice.")
        st.stop()

    st.caption(
        f"Window: {start.isoformat()} to {end.isoformat()} (inclusive, source-local dates) · "
        f"Valid duration observations: {overview['valid_resolution_count']:,} · "
        f"Mean valid duration: {float(avg):.1f} h" if avg is not None
        else f"Window: {start.isoformat()} to {end.isoformat()} · No valid resolution durations"
    )

    trend_tab, breakdown_tab, geo_tab, data_tab = st.tabs(
        ["📈 Activity", "🏢 Operations", "🗺️ Geographic clusters", "📁 BI exports"])

    with trend_tab:
        st.subheader("Service request trend")
        chart = build_daily_trend_chart(daily)
        if chart is not None:
            st.altair_chart(chart, use_container_width=True)
        x, y = st.columns(2)
        with x:
            st.subheader("Borough workload")
            if borough:
                st.bar_chart(pd.DataFrame(borough).set_index("label")["requests"],
                             horizontal=True)
            else:
                st.info("No borough data.")
        with y:
            st.subheader("Request status")
            st.bar_chart(pd.DataFrame(status).set_index("label")["requests"],
                         horizontal=True)

    with breakdown_tab:
        left, right = st.columns(2)
        with left:
            st.subheader("Top responding agencies")
            st.bar_chart(pd.DataFrame(agency).set_index("label")["requests"],
                         horizontal=True)
        with right:
            st.subheader("Top problem categories")
            st.bar_chart(pd.DataFrame(complaint).set_index("label")["requests"],
                         horizontal=True)
        st.subheader("Borough performance")
        st.dataframe(pd.DataFrame(borough).rename(columns={
            "label": "Borough", "requests": "Requests", "closed_requests": "Closed",
            "median_resolution_hours": "Median hours (valid timestamps)",
        }), use_container_width=True, hide_index=True)

    with geo_tab:
        st.subheader("Geographic concentration (approximate)")
        st.caption("Coordinates are rounded to 2 decimals. Only grid cells containing at least "
                   "5 requests are displayed; individual incident locations are not exposed.")
        try:
            clusters = cached_metric("map", filters, schema, signature, dsn)
        except Exception:
            st.warning("Geographic aggregates are temporarily unavailable.")
            clusters = []
        if clusters:
            st.map(pd.DataFrame(clusters), latitude="lat", longitude="lon", size="requests")
            st.caption(f"Displaying {len(clusters)} aggregated geographic cells (limit 400); "
                       "additional eligible cells may be omitted.")
        else:
            st.info("This slice has no location cells meeting the 5-request privacy threshold.")

    with data_tab:
        st.subheader("Aggregated BI-ready extracts")
        st.caption("Downloads contain grouped metrics only—no IDs, exact coordinates or raw complaints.")
        for title, data, slug in (
            ("Daily activity", daily, "daily"),
            ("Borough metrics", borough, "borough"),
            ("Agency metrics", agency, "agency"),
            ("Complaint metrics", complaint, "complaint"),
        ):
            st.download_button(
                f"Download {title} · CSV", aggregate_csv(data),
                file_name=f"dataforge_{slug}_{start.isoformat()}_{end.isoformat()}.csv",
                mime="text/csv", key=f"download_{slug}",
            )
        with st.expander("Dataset and interpretation notes"):
            st.write(f"Available source-local dates: {first_day} → {last_day}")
            st.write(f"Current fact table: {extent['fact_rows']:,} loaded requests")
            st.write("Request counts reflect the latest ingested snapshot, not citywide totals "
                     "unless a complete backfill has been independently verified. Closed requests "
                     "use status='Closed'; duration statistics exclude missing/invalid timestamps. "
                     "Created dates have not been normalized to UTC.")

    st.divider()
    st.caption("Independent portfolio demo · Public NYC Open Data · Not an official NYC 311 service")


if __name__ == "__main__":
    main()
