import streamlit as st
import pandas as pd
from pathlib import Path
import sys
import os
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

def load_latest_file(directory: Path):
    if not directory.exists():
        return None, None
    files = sorted(directory.glob("*.csv"))
    if not files:
        return None, None
    latest_file = files[-1]
    df = pd.read_csv(latest_file)
    return df, latest_file.name

def main_app():
    st.title("Momentum Detector Dashboard")

    st.sidebar.title("Navigation")
    page = st.sidebar.radio("Go to", ["Dashboard", "Data Management"])

    if page == "Dashboard":
        show_dashboard()
    elif page == "Data Management":
        show_data_management()

# ... (Previous imports)
import altair as alt

# ... (Previous functions)

def load_all_momentum_data(directory: Path):
    if not directory.exists():
        return None
    files = sorted(directory.glob("*.csv"))
    if not files:
        return None
    
    df_list = []
    for f in files:
        try:
            tmp = pd.read_csv(f)
            # 日付カラムがあることを前提
            if "日付" in tmp.columns:
                df_list.append(tmp)
        except Exception as e:
            pass
            
    if not df_list:
        return None
        
    return pd.concat(df_list, ignore_index=True)

def show_dashboard():
    st.header("📊 Market Momentum")

    tab1, tab2, tab3 = st.tabs(["Sector Summary", "Momentum Summary", "Momentum Trends"])

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
            st.dataframe(df_momentum, use_container_width=True)

            # 簡単な可視化
            if "売買代金5日平均/20日平均比率" in df_momentum.columns:
                st.bar_chart(df_momentum.set_index("業種")["売買代金5日平均/20日平均比率"])
        else:
            st.warning("No Momentum Summary data found.")

    with tab3:
        st.subheader("📈 Momentum Trends (Time Series)")
        
        df_all = load_all_momentum_data(MOMENTUM_DIR)
        if df_all is not None:
            # データ前処理
            df_all["日付"] = pd.to_datetime(df_all["日付"])
            
            # 1. Line Chart: 5/20日比率の推移
            st.markdown("#### 5-Day / 20-Day Ratio Trend")
            
            # セクター選択
            all_sectors = sorted(df_all["業種"].unique())
            default_sectors = all_sectors[:5] if len(all_sectors) > 5 else all_sectors
            selected_sectors = st.multiselect("Select Sectors to Compare", all_sectors, default=default_sectors)
            
            if selected_sectors:
                subset = df_all[df_all["業種"].isin(selected_sectors)]
                
                chart = alt.Chart(subset).mark_line(point=True).encode(
                    x="日付:T",
                    y=alt.Y("売買代金5日平均/20日平均比率", title="Ratio (5d/20d)"),
                    color="業種",
                    tooltip=["日付", "業種", "売買代金5日平均/20日平均比率"]
                ).interactive()
                st.altair_chart(chart, use_container_width=True)
            else:
                st.info("Select sectors to view trends.")
                
            # 2. Heatmap: 全セクターの比率一覧
            st.markdown("#### Momentum Heatmap")
            st.caption("Intensity of 5d/20d Ratio across all sectors")
            
            # ピボットテーブル作成
            pivot_df = df_all.pivot(index="業種", columns="日付", values="売買代金5日平均/20日平均比率")
            
            # ヒートマップ表示 (Altair)
            # データ量が多いと重いので、直近N日に絞るオプション等があっても良いが、まずは全量
            heatmap = alt.Chart(df_all).mark_rect().encode(
                x="日付:T",
                y="業種:N",
                color=alt.Color("売買代金5日平均/20日平均比率", scale=alt.Scale(scheme="redblue", domain=[0.5, 1.5], clamp=True)),
                tooltip=["日付", "業種", "売買代金5日平均/20日平均比率"]
            ).properties(height=600).interactive()
            
            st.altair_chart(heatmap, use_container_width=True)
            
        else:
            st.warning("No historical momentum data found to display trends.")


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
