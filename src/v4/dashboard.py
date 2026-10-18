
from pathlib import Path

import streamlit as st

# 프로젝트 최상위 경로
ROOT = Path(__file__).resolve().parents[2]

st.set_page_config(
    page_title="Production Management AI | V4",
    page_icon="🏭",
    layout="wide",
)

st.title("Production Management AI")
st.caption("V4 | Evidence-based Production Review Dashboard")

st.info(
    "본 시스템은 생산관리자의 검토 우선순위 결정을 지원합니다. "
    "이상 원인이나 실제 개선 효과를 자동으로 확정하지 않습니다."
)

st.subheader("Overview")

# V2 분석 결과 파일
KPI_PATH = ROOT / "results" / "v2_daily_kpi_screening.csv"

if not KPI_PATH.exists():
    st.error(
        "V2 KPI 분석 결과가 없습니다. "
        "먼저 V2 분석 결과 파일을 생성해야 합니다."
    )
    st.stop()

import pandas as pd

df = pd.read_csv(KPI_PATH)

# 우선 검토 대상 날짜
TARGET_DATE = "2022-11-03"

target = df.loc[
    df["date"].astype(str) == TARGET_DATE
]

st.subheader("Priority Review")

if target.empty:
    st.warning(f"{TARGET_DATE} 데이터가 없습니다.")
else:
    record = target.iloc[0]

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "Operating Ratio",
            f"{float(record['operating_ratio']) * 100:.2f}%"
        )

    with col2:
        st.metric(
            "Hourly Downtime",
            f"{float(record['downtime_h']):.2f} h"
        )

    with col3:
        st.metric(
            "Downtime Events",
            f"{int(record['event_count'])} events"
        )

    st.caption(
        f"Review target: {TARGET_DATE} | "
        "Relative screening priority only. "
        "Root cause not established."
    )

st.write("V2 Daily KPI Screening")

st.dataframe(
    df,
    use_container_width=True,
    hide_index=True,
)

st.caption(
    "Screening 결과는 상대적인 검토 우선순위입니다. "
    "원인 확정이나 개선 성과를 의미하지 않습니다."
)

# V4-A / V4-B 검증 결과 표시
import json

BRIDGE_PATH = ROOT / "results" / "v4" / "v3_bridge_demo.json"

st.divider()
st.subheader("Evidence Validation")

if not BRIDGE_PATH.exists():
    st.warning("V4 Evidence 검증 결과 파일이 없습니다.")
else:
    with open(BRIDGE_PATH, "r", encoding="utf-8") as f:
        bridge = json.load(f)

    validation_results = bridge.get("validation_results", [])

    passed = sum(
        1 for item in validation_results
        if item.get("passed") is True
    )

    st.metric(
        "Validated Factual Claims",
        f"{passed} / {len(validation_results)}"
    )

    st.dataframe(
        validation_results,
        use_container_width=True,
        hide_index=True,
    )

    st.warning(
        "검증된 수치 사실과 원인 판단은 구분됩니다. "
        "Manager의 원인 해석은 별도 검토가 필요하며, "
        "실제 근본 원인은 확정되지 않았습니다."
    )


# V4-B Next Checks
NEXT_CHECK_PATH = ROOT / "results" / "v4" / "next_check_demo.json"

st.divider()
st.subheader("Next Checks")

if not NEXT_CHECK_PATH.exists():
    st.warning("V4-B Next Check 결과 파일이 없습니다.")
else:
    with open(NEXT_CHECK_PATH, "r", encoding="utf-8") as f:
        next_check_data = json.load(f)

    checks = next_check_data.get("checks", [])

    col1, col2 = st.columns(2)

    with col1:
        st.metric("Required Checks", len(checks))

    with col2:
        st.metric(
            "Root Cause Status",
            next_check_data.get(
                "root_cause_status",
                "NOT_ESTABLISHED"
            )
        )

    st.caption(
        f"Review: {next_check_data.get('review_id', 'Unknown')} | "
        f"Target Date: {next_check_data.get('target_date', 'Unknown')}"
    )

    selection_reason = next_check_data.get("selection_reason")
    if selection_reason:
        st.info(f"Selection Reason: {selection_reason}")

    for check in checks:
        check_id = check.get("check_id", "UNKNOWN")
        question = check.get("question", "No question")

        with st.expander(f"{check_id} | {question}"):
            st.write("**Category**")
            st.write(check.get("category", "Unknown"))

            st.write("**Required Data**")
            st.write(
                ", ".join(check.get("required_data", []))
            )

            st.write("**If Confirmed**")
            st.write(
                check.get("if_confirmed", "Not specified")
            )

            st.write("**If Not Confirmed**")
            st.write(
                check.get("if_not_confirmed", "Not specified")
            )

    st.caption(
        "Next Checks는 추가 확인을 위한 질문입니다. "
        "원인 확정이나 개선 효과 검증을 의미하지 않습니다."
    )


# V4-C Action Tracking
import sqlite3
from contextlib import closing

ACTION_DB_PATH = ROOT / "data" / "v4" / "action_tracking.db"

st.divider()
st.subheader("Action Tracking")

if not ACTION_DB_PATH.exists():
    st.warning(
        "Action Tracking DB가 없습니다. "
        "점검 등록 데이터가 생성되지 않은 상태입니다."
    )
else:
    try:
        with closing(sqlite3.connect(ACTION_DB_PATH)) as conn:
            actions_df = pd.read_sql_query(
                """
                SELECT
                    action_id,
                    check_id,
                    assignee,
                    status,
                    finding,
                    due_date,
                    closure_type,
                    updated_at
                FROM actions
                ORDER BY check_id
                """,
                conn,
            )

        if actions_df.empty:
            st.info("등록된 Action이 없습니다.")
        else:
            st.metric(
                "Registered Actions",
                len(actions_df)
            )

            st.dataframe(
                actions_df,
                use_container_width=True,
                hide_index=True,
            )

            st.caption(
                "Action의 완료 상태는 원인 확인 또는 "
                "개선 효과 검증을 의미하지 않습니다."
            )

    except sqlite3.Error as exc:
        st.error(
            f"Action Tracking DB 조회 실패: {exc}"
        )


# V4-D KPI Comparison Validation
from action_evidence_validation import validate_action_evidence

st.divider()
st.subheader("KPI Comparison Validation")

if not ACTION_DB_PATH.exists():
    st.warning("Action DB가 없어 조치 증빙을 검증할 수 없습니다.")

elif actions_df.empty:
    st.info("검증할 Action이 없습니다.")

else:
    selected_action_id = st.selectbox(
        "Select Action",
        options=actions_df["action_id"].tolist(),
        key="kpi_validation_action",
    )

    evidence_result = validate_action_evidence(
        selected_action_id,
        db_path=ACTION_DB_PATH,
    )

    col1, col2 = st.columns(2)

    with col1:
        st.metric(
            "Execution Evidence",
            "VERIFIED" if evidence_result["verified"] else "NOT VERIFIED",
        )

    with col2:
        st.metric(
            "Action Status",
            evidence_result.get("action_status", "UNKNOWN"),
        )

    if evidence_result["verified"] is not True:
        st.warning(
            "KPI 전후 비교 불가: "
            + evidence_result.get("reason", "UNKNOWN_REASON")
        )

    st.caption(
        "실제 조치 수행 증빙이 확인되지 않은 경우 "
        "개선율을 계산하거나 개선 효과를 주장하지 않습니다."
    )