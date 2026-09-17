"""Streamlit dashboard for the production line.

Shows line throughput, first-pass yield, station-by-station cycle time,
the traceability completeness score over time (with a red/yellow/green
alert banner), and a recall-query search box.

Run: streamlit run dashboard/app.py

If you haven't run the local simulation (no `traceability.db` in the repo
root), this falls back to the bundled `dashboard/demo_data.db` -- a real
dataset from a past local run -- so the dashboard has something to show
out of the box, e.g. on a fresh Streamlit Community Cloud deploy where
there's no MQTT broker or station processes running behind it.
"""
import os
from pathlib import Path

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from traceability.config import COMPLETENESS_TARGET, DB_URL
from traceability.models import Base, DailyScore, StationEvent, Unit
from recall.query import get_unit_trace, get_units_by_batch

st.set_page_config(page_title="Line Traceability Dashboard", layout="wide")

DEMO_DB_PATH = Path(__file__).parent / "demo_data.db"


def _resolve_db_url() -> str:
    """Prefer an explicit DB_URL env var, then a local traceability.db
    from running the real pipeline, then the bundled demo dataset."""
    if os.environ.get("DB_URL"):
        return os.environ["DB_URL"]
    if Path("traceability.db").exists():
        return DB_URL
    if DEMO_DB_PATH.exists():
        return f"sqlite:///{DEMO_DB_PATH}"
    return DB_URL


@st.cache_resource
def get_session():
    resolved_url = _resolve_db_url()
    connect_args = {"check_same_thread": False} if resolved_url.startswith("sqlite") else {}
    engine = create_engine(resolved_url, connect_args=connect_args)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def load_events_df(session) -> pd.DataFrame:
    rows = session.query(
        StationEvent.unit_id,
        StationEvent.station,
        StationEvent.timestamp,
        StationEvent.operator,
        StationEvent.cycle_time,
        StationEvent.temperature,
        StationEvent.pass_fail,
        StationEvent.reconciled,
    ).all()
    return pd.DataFrame(
        rows,
        columns=[
            "unit_id", "station", "timestamp", "operator",
            "cycle_time", "temperature", "pass_fail", "reconciled",
        ],
    )


def load_scores_df(session) -> pd.DataFrame:
    rows = session.query(
        DailyScore.score_date, DailyScore.score, DailyScore.total_units, DailyScore.complete_units
    ).order_by(DailyScore.score_date).all()
    return pd.DataFrame(rows, columns=["date", "score", "total_units", "complete_units"])


def render_banner(latest_score: float | None) -> None:
    if latest_score is None:
        st.info("No completeness score computed yet. Run `python -m integrity.report` first.")
        return
    pct = latest_score * 100
    if latest_score >= COMPLETENESS_TARGET:
        st.success(f"🟢 Traceability completeness: {pct:.1f}% (target {COMPLETENESS_TARGET*100:.0f}%)")
    elif latest_score >= COMPLETENESS_TARGET - 0.05:
        st.warning(f"🟡 Traceability completeness: {pct:.1f}% (target {COMPLETENESS_TARGET*100:.0f}%)")
    else:
        st.error(f"🔴 Traceability completeness: {pct:.1f}% (target {COMPLETENESS_TARGET*100:.0f}%)")


def main() -> None:
    st.title("Production Line Traceability Dashboard")

    if not Path("traceability.db").exists() and DEMO_DB_PATH.exists():
        st.caption(
            "📦 Showing bundled demo data from a past local simulation run "
            "(no live `traceability.db` found in this environment)."
        )

    session = get_session()
    events_df = load_events_df(session)
    scores_df = load_scores_df(session)

    if events_df.empty:
        st.info("No events ingested yet. Start Mosquitto + the stations + the ingest service.")
        return

    events_df["timestamp"] = pd.to_datetime(events_df["timestamp"])

    latest_score = scores_df["score"].iloc[-1] if not scores_df.empty else None
    render_banner(latest_score)

    col1, col2, col3 = st.columns(3)

    with col1:
        st.subheader("Line throughput")
        assembly_df = events_df[events_df["station"] == "assembly"].copy()
        assembly_df["hour"] = assembly_df["timestamp"].dt.floor("h")
        throughput = assembly_df.groupby("hour").size().rename("units")
        st.line_chart(throughput)
        if not throughput.empty:
            st.metric("Avg units/hour", f"{throughput.mean():.1f}")

    with col2:
        st.subheader("First-pass yield")
        yield_by_station = (
            events_df.groupby("station")["pass_fail"]
            .apply(lambda s: (s == "pass").mean() * 100)
            .reindex(["assembly", "test", "pack"])
        )
        st.bar_chart(yield_by_station)
        overall_yield = (events_df["pass_fail"] == "pass").mean() * 100
        st.metric("Overall yield", f"{overall_yield:.1f}%")

    with col3:
        st.subheader("Cycle time by station")
        cycle_by_station = (
            events_df.groupby("station")["cycle_time"]
            .mean()
            .reindex(["assembly", "test", "pack"])
        )
        st.bar_chart(cycle_by_station)

    st.subheader("Traceability completeness score over time")
    if scores_df.empty:
        st.info("Run `python -m integrity.report --fix` to compute and store daily scores.")
    else:
        st.line_chart(scores_df.set_index("date")["score"])
        st.dataframe(scores_df, use_container_width=True)

    st.divider()
    st.subheader("Recall query")
    st.caption("Enter a unit_id for a full trace, or a batch_id to list every unit from that batch.")

    search_value = st.text_input("Search unit_id or batch_id", placeholder="UNIT-ABCDEF1234 or BATCH-001")
    if search_value:
        if search_value.upper().startswith("UNIT-"):
            trace = get_unit_trace(session, search_value)
            if trace is None:
                st.error(f"No unit found with id {search_value}")
            else:
                st.write(f"**Batch:** {trace['batch_id']} ({trace['material_source']})")
                st.write(f"**Created:** {trace['created_at']}")
                st.dataframe(pd.DataFrame(trace["events"]), use_container_width=True)
        elif search_value.upper().startswith("BATCH-"):
            units = get_units_by_batch(session, search_value)
            st.write(f"**{len(units)} unit(s)** made from batch {search_value}")
            st.dataframe(pd.DataFrame({"unit_id": units}), use_container_width=True)
        else:
            st.warning("Enter an id starting with UNIT- or BATCH-")


if __name__ == "__main__":
    main()
