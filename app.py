import streamlit as st
import pandas as pd
from pathlib import Path
import sys
import os
import altair as alt
import plotly.express as px
from dotenv import load_dotenv

load_dotenv()

# main.py の run_pipeline をインポートするためにパスを追加
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from main import run_pipeline

# ページ設定
st.set_page_config(
    page_title="Momentum Detector Dashboard",
    layout="wide",
    initial_sidebar_state="expanded",
)

# パス設定
DATA_DIR = Path("data/processed_data")
SECTOR_DIR = DATA_DIR / "sector_summary"
MOMENTUM_DIR = DATA_DIR / "momentum_summary"

@st.cache_data
def load_latest_file(directory: Path):
    if not directory.exists():
        return None, None
    files = sorted(directory.glob("*.csv"))
    if not files:
        return None, None
    latest_file = files[-1]
    df = pd.read_csv(latest_file)
    return df, latest_file.name

@st.cache_data
def load_all_history(directory: Path):
    """ディレクトリ内の全CSVを読み込んで結合する"""
    if not directory.exists():
        return pd.DataFrame()
    files = sorted(directory.glob("*.csv"))
    if not files:
        return pd.DataFrame()

    df_list = []
    for f in files:
        try:
            temp_df = pd.read_csv(f)
            # 日付カラムのフォーマット確認/変換
            if "日付" in temp_df.columns:
                 temp_df["日付"] = pd.to_datetime(temp_df["日付"]).dt.date
            df_list.append(temp_df)
        except Exception as e:
            st.warning(f"Failed to read {f.name}: {e}")

    if df_list:
        return pd.concat(df_list, ignore_index=True)
    return pd.DataFrame()

def main_app():
    st.title("Momentum Detector Dashboard")

    st.sidebar.title("Navigation")
    page = st.sidebar.radio("Go to", ["Dashboard", "Momentum Trends", "Data Management"])

    if page == "Dashboard":
        show_dashboard()
    elif page == "Momentum Trends":
        show_momentum_trends()
    elif page == "Data Management":
        show_data_management()

def show_dashboard():
    st.header("📊 Market Momentum (Latest)")

    tab1, tab2 = st.tabs(["Sector Summary", "Momentum Summary"])

    with tab1:
        st.subheader("Sector Performance")
        df_sector, fname = load_latest_file(SECTOR_DIR)
        if df_sector is not None:
            st.caption(f"Data Source: {fname}")

            # フィルタリング
            caps = ["すべて"] + list(df_sector["時価総額帯"].unique()) if "時価総額帯" in df_sector.columns else []
            selected_cap = st.selectbox("Market Cap Filter", caps, index=0)

            if selected_cap != "すべて":
                df_display = df_sector[df_sector["時価総額帯"] == selected_cap]
            else:
                df_display = df_sector

            st.dataframe(df_display, use_container_width=True)
        else:
            st.warning("No Sector Summary data found.")

    with tab2:
        st.subheader("Trading Value Momentum")
        df_momentum, fname = load_latest_file(MOMENTUM_DIR)
        if df_momentum is not None:
            st.caption(f"Data Source: {fname}")

            # デフォルトで業種のみ表示
            if "区分" in df_momentum.columns:
                df_display = df_momentum[df_momentum["区分"] == "業種"]
            else:
                df_display = df_momentum

            st.dataframe(df_display, use_container_width=True)

            # 簡単な可視化
            if "売買代金5日平均/20日平均比率" in df_display.columns:
                chart_data = df_display.set_index("名称") if "名称" in df_display.columns else df_display.set_index("業種")
                st.bar_chart(chart_data["売買代金5日平均/20日平均比率"])
        else:
            st.warning("No Momentum Summary data found.")

def show_momentum_trends():
    st.header("📈 Momentum Trends")

    # データ読み込み
    df_history = load_all_history(MOMENTUM_DIR)

    if df_history.empty:
        st.warning("No historical data found.")
        return

    # フィルタリングUI
    col1, col2 = st.columns(2)
    with col1:
        # 区分（Sector vs Market Cap）
        types = list(df_history["区分"].unique()) if "区分" in df_history.columns else ["業種"]
        selected_type = st.selectbox("Analysis Type", types, index=0)

    # 選択された区分に基づいてデータをフィルタ
    if "区分" in df_history.columns:
        df_filtered = df_history[df_history["区分"] == selected_type].copy()
    else:
        df_filtered = df_history.copy()

    # 名称リスト
    name_col = "名称" if "名称" in df_filtered.columns else "業種"
    available_names = sorted(df_filtered[name_col].unique())

    with col2:
        selected_names = st.multiselect("Select Targets", available_names, default=available_names[:5])

    if not selected_names:
        st.info("Please select at least one target.")
        return

    df_chart = df_filtered[df_filtered[name_col].isin(selected_names)].copy()

    # 可視化：折れ線グラフ (5日/20日平均比率)
    st.subheader("Trading Value Momentum (5d/20d Ratio)")

    chart = alt.Chart(df_chart).mark_line(point=True).encode(
        x=alt.X("日付:T", title="Date"),
        y=alt.Y("売買代金5日平均/20日平均比率:Q", title="5d/20d Ratio"),
        color=alt.Color(f"{name_col}:N", title="Name"),
        tooltip=["日付", name_col, "売買代金5日平均/20日平均比率", "売買代金（千円）"]
    ).interactive()

    st.altair_chart(chart, use_container_width=True)

    # ヒートマップ
    st.subheader("Momentum Heatmap")

    # Pivot for heatmap: Index=Name, Columns=Date, Values=Ratio
    heatmap_data = df_chart.pivot_table(
        index=name_col,
        columns="日付",
        values="売買代金5日平均/20日平均比率"
    )

    # Plotly for better heatmap
    fig = px.imshow(
        heatmap_data,
        labels=dict(x="Date", y="Name", color="Ratio"),
        x=heatmap_data.columns,
        y=heatmap_data.index,
        color_continuous_scale="RdBu_r", # Red for high momentum? Usually High Ratio > 1.
        origin='lower'
    )
    st.plotly_chart(fig, use_container_width=True)


def show_data_management():
    st.header("⚙️ Data Management")

    st.write("Click the button below to manually trigger the data update process.")

    if st.button("Run Data Update"):
        with st.spinner("Running data collection pipeline..."):
            try:
                # ログをキャプチャしたいが、今回は簡易的に実行結果だけ表示
                msg = run_pipeline(continue_on_error=True)
                st.success(f"Result: {msg}")
            except Exception as e:
                st.error(f"Error during execution: {e}")

    st.subheader("Logs")
    log_dir = Path("logs")
    if log_dir.exists():
        log_files = sorted(log_dir.glob("main_log_*.txt"), reverse=True)
        if log_files:
            selected_log = st.selectbox("Select Log File", [f.name for f in log_files])
            if selected_log:
                with open(log_dir / selected_log, "r", encoding="utf-8") as f:
                    st.text_area("Log Content", f.read(), height=300)
        else:
            st.info("No log files found.")

if __name__ == "__main__":
    main_app()
