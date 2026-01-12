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

if st.sidebar.button("Clear Cache"):
    st.cache_data.clear()
    st.rerun()

# パス設定
DATA_DIR = Path("data/processed_data")
SECTOR_DIR = DATA_DIR / "sector_summary"
MOMENTUM_DIR = DATA_DIR / "momentum_summary"
INDICES_DIR = DATA_DIR / "indices"

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
def load_synthetic_index(sector_name):
    """Load synthetic sector index data."""
    # Handle filename safety
    safe_name = sector_name.replace("・", "_").replace("、", "_").replace(" ", "_")
    path = INDICES_DIR / f"{safe_name}.csv"
    if not path.exists():
        return None
    df = pd.read_csv(path)
    df["日付"] = pd.to_datetime(df["日付"])
    return df

@st.cache_data
def load_benchmark_data(benchmark_name):
    """Load Benchmark data from raw tosho files or stock files (cached)."""
    if benchmark_name == "Nikkei 225":
        # Read from japan-all-stock-prices
        RAW_STOCK_DIR = Path("data/raw/japan_all_stock")
        files = sorted(RAW_STOCK_DIR.glob("japan-all-stock-prices_*.csv"))
        dfs = []
        for f in files:
            try:
                # 只のID検索だが全ファイル読むのは重い (Optimization later)
                temp = pd.read_csv(f, encoding="cp932")
                # SC is string "0001"
                row = temp[temp["SC"].astype(str) == "0001"]
                if not row.empty:
                    d_str = f.stem.split("_")[-1]
                    d_fmt = f"{d_str[:4]}/{d_str[4:6]}/{d_str[6:]}"
                    price_col = "株価" if "株価" in row.columns else "終値"
                    close_val = str(row[price_col].values[0]).replace(",","") if not row.empty else "0"
                    if close_val == "-": close_val = 0
                    close = float(close_val)
                    dfs.append({"日付": d_fmt, "Close": close})
            except:
                continue
        if not dfs: return None
        df = pd.DataFrame(dfs)
        df["日付"] = pd.to_datetime(df["日付"])
        return df

    else:
        # Read from tosho-index-data
        name_map = {
            "TOPIX": "TOPIX",
            "Growth 250": "東証グロース市場250指数"
        }
        target = name_map.get(benchmark_name)
        if not target:
            return None
            
        dfs = []
        RAW_INDEX_DIR = Path("data/raw/tosho_index") 
        files = sorted(RAW_INDEX_DIR.glob("tosho-index-data_*.csv"))
        for f in files:
            try:
                temp = pd.read_csv(f, encoding="cp932")
                row = temp[temp["指数名"] == target]
                if not row.empty:
                    if "日付" in row.columns:
                        d = str(row["日付"].values[0])
                        d_fmt = f"{d[:4]}/{d[4:6]}/{d[6:]}"
                    else:
                        d_str = f.stem.split("_")[-1]
                        d_fmt = f"{d_str[:4]}/{d_str[4:6]}/{d_str[6:]}"
                    
                    close_val = str(row["終値"].values[0]).replace(",","")
                    if close_val == "-": close_val = 0
                    close = float(close_val)
                    dfs.append({"日付": d_fmt, "Close": close})
            except:
                continue
                
        if not dfs:
            return None
            
        df = pd.DataFrame(dfs)
# ... (Previous imports)
import altair as alt
alt.data_transformers.disable_max_rows()

# --- Helper Functions ---

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

def show_momentum_trends():
    st.header("📈 Momentum Trends (Time Series)")
    
    df_all = load_all_momentum_data(MOMENTUM_DIR)
    if df_all is None:
        st.error("Data not found. Please run batch processing.")
        return

    df_all["日付"] = pd.to_datetime(df_all["日付"])
    
    # Controls
    col1, col2 = st.columns([2, 1])
    with col1:
        # Metric Selection (Updated for Relative Momentum)
        heatmap_metric = st.radio(
            "Metric",
            ["Trading Value Momentum (5d/20d)", "Relative Momentum (vs TOPIX)"],
            horizontal=True
        )
    with col2:
        # Date Slider
        min_date = df_all["日付"].min().date()
        max_date = df_all["日付"].max().date()
        slider_range = st.slider(
            "Date Range",
            min_value=min_date, max_value=max_date, value=(min_date, max_date),
            format="YYYY/MM/DD"
        )

    # Filter Data (Include Market Overall)
    df_heatmap = df_all.copy()
    
    mask = (df_heatmap["日付"].dt.date >= slider_range[0]) & (df_heatmap["日付"].dt.date <= slider_range[1])
    df_heatmap = df_heatmap.loc[mask].copy()
    df_heatmap["date_str"] = df_heatmap["日付"].dt.strftime("%Y/%m/%d")

    # Rename "市場全体" -> "TOPIX (Market Overall)"
    df_heatmap["業種"] = df_heatmap["業種"].replace("市場全体", "TOPIX (Market Overall)")

    # Calculate Relative Momentum
    # 1. Extract Market Ratios per date
    market_ratios = df_heatmap[df_heatmap["業種"] == "TOPIX (Market Overall)"].set_index("date_str")["売買代金5日平均/20日平均比率"]
    
    # 2. Map back to df
    df_heatmap["Market_Ratio"] = df_heatmap["date_str"].map(market_ratios)
    
    # 3. Calculate Relative Ratio (Sector Ratio / Market Ratio)
    # Avoid division by zero if necessary (though Ratio shouldn't be 0 generally)
    df_heatmap["Relative_Ratio"] = df_heatmap["売買代金5日平均/20日平均比率"] / df_heatmap["Market_Ratio"].replace(0, 1)

    # Sort Logic: TOPIX at the bottom
    unique_sectors = sorted([s for s in df_heatmap["業種"].unique() if s != "TOPIX (Market Overall)"])
    if "TOPIX (Market Overall)" in df_heatmap["業種"].values:
        unique_sectors.append("TOPIX (Market Overall)")
        
    sort_order = unique_sectors

    # Config based on Metric
    if "Relative" in heatmap_metric:
        plot_col = "Relative_Ratio"
        # Domain centered at 1.0 (High=Red (Stronger than Market), Low=Blue)
        color_opts = alt.Color(f"{plot_col}:Q", 
                               scale=alt.Scale(domain=[0.5, 1.0, 1.5], range=['blue', 'white', 'red']), 
                               title="Rel. Ratio")
        tooltip_val = alt.Tooltip(plot_col, format=".3f")
    else:
        plot_col = "売買代金5日平均/20日平均比率"
        color_opts = alt.Color(f"{plot_col}:Q", 
                               scale=alt.Scale(domain=[0.5, 1.0, 1.5], range=['blue', 'white', 'red']), 
                               title="Ratio")
        tooltip_val = alt.Tooltip(plot_col, format=".3f")

    # Current Selection State
    current_sector = st.session_state.get("target_sector_selector", None)
    if current_sector is None and len(df_heatmap) > 0:
            current_sector = unique_sectors[0]

    # 1. Labels Chart (Clickable Y-Axis)
    # OPTIMIZATION: Aggregate unique sectors
    df_labels = df_heatmap[["業種"]].drop_duplicates()
    # Add dummy date column to force X-axis rendering for layout alignment
    if not df_heatmap.empty:
            df_labels["date_str"] = df_heatmap["date_str"].iloc[0]

    select_label = alt.selection_point(fields=['業種'], name="label_select")
    
    labels_chart = alt.Chart(df_labels).mark_text(align='right', baseline='middle', dx=-10).encode(
        y=alt.Y("業種:N", title=None, axis=None, sort=sort_order),
        # Dummy X-axis to force identical bottom padding (matching rotated dates)
        x=alt.X("date_str:O", title="Date", axis=alt.Axis(labelAngle=-90, labelColor='transparent', titleColor='transparent', ticks=False)),
        text=alt.Text("業種:N"),
        color=alt.condition(select_label, alt.value("black"), alt.value("#555")),
        opacity=alt.value(1.0)
    ).properties(
        title="Sector", 
        height=600
    ).add_params(
        select_label
    )

    # 2. Heatmap Chart
    select_heatmap = alt.selection_point(fields=['業種'], name="heatmap_select")
    
    heatmap_chart = alt.Chart(df_heatmap).mark_rect().encode(
        x=alt.X("date_str:O", title="Date", axis=alt.Axis(labelAngle=-90)),
        y=alt.Y("業種:N", title=None, axis=None, sort=sort_order), 
        color=color_opts,
        opacity=alt.value(1.0), # Always full opacity
        tooltip=["日付", "業種", tooltip_val]
    ).properties(
        height=600,
        title="Click a sector to view details below"
    ).add_params(
        select_heatmap
    ).interactive()

    # Layout: Side-by-side
    # Adjust ratios: Labels (1.5) : Heatmap (5.5) to give more space for text
    c_labels, c_map = st.columns([1.5, 5.5], gap="small")
    
    with c_labels:
        evt_labels = st.altair_chart(labels_chart, use_container_width=True, on_select="rerun")
        
    with c_map:
        evt_heatmap = st.altair_chart(heatmap_chart, use_container_width=True, on_select="rerun")
    
    # Handle Selection Events
    new_selection = None
    
    # Check Labels
    if evt_labels and "selection" in evt_labels and "label_select" in evt_labels["selection"]:
            sel = evt_labels["selection"]["label_select"]
            if len(sel) > 0: 
                new_selection = str(sel[0]["業種"])

    # Check Heatmap
    if evt_heatmap and "selection" in evt_heatmap and "heatmap_select" in evt_heatmap["selection"]:
            sel = evt_heatmap["selection"]["heatmap_select"]
            if len(sel) > 0: 
                new_selection = str(sel[0]["業種"])
    
    if new_selection and new_selection != st.session_state.get("target_sector_selector"):
            st.session_state["target_sector_selector"] = new_selection
            st.rerun()

    # 2. Detail Analysis Section (Bottom)
    st.divider()
    st.subheader("2. Sector Detail Analysis")
    
    # Ensure session state is initialized if needed (though selectbox will create it)
    if "target_sector_selector" not in st.session_state:
        st.session_state.target_sector_selector = sorted(df_all["業種"].unique())[0]

    target_sector = st.selectbox(
        "Select Sector to Analyze", 
        sorted(df_all["業種"].unique()),
        key="target_sector_selector"
    )
    
    if target_sector:
        # LOAD FULL DATA (No pre-filtering by date here)
        idx_df = load_synthetic_index(target_sector)
        
        if idx_df is not None:
            # Controls
            col_d1, col_d2 = st.columns(2)
            with col_d1:
                cap_class = st.selectbox("Market Cap Class", ["全体", "大型", "中型", "小型", "超大型"], index=0)
            with col_d2:
                benchmark = st.selectbox("Benchmark Overlay", ["None", "TOPIX", "Nikkei 225", "Growth 250"])

            # Filter by Cap
            subset_all = idx_df[idx_df["時価総額帯"] == cap_class].copy()
            subset_all = subset_all.sort_values("日付")

            if subset_all.empty:
                st.warning(f"No data for {target_sector} - {cap_class}")
            else:
                # Generate SMA on FULL dataset to avoid missing head
                subset_all["SMA5"] = subset_all["終値"].rolling(5).mean()
                subset_all["SMA25"] = subset_all["終値"].rolling(25).mean()
                subset_all["SMA75"] = subset_all["終値"].rolling(75).mean()

                # Filter for Display Range (AFTER SMA calc)
                mask = (subset_all["日付"].dt.date >= slider_range[0]) & (subset_all["日付"].dt.date <= slider_range[1])
                subset = subset_all.loc[mask].copy()
                
                # Format Date as String for Ordinal Axis (skips gaps)
                subset["date_str"] = subset["日付"].dt.strftime("%Y/%m/%d")

                # Base Chart (Candlestick)
                # Use Ordinal X axis to skip holidays
                base = alt.Chart(subset).encode(
                    x=alt.X("date_str:O", title="Date", axis=alt.Axis(labelAngle=-90))
                )
                
                # Candlestick: Rule (Low-High) + Bar (Open-Close)
                rule = base.mark_rule().encode(
                    y=alt.Y("安値:Q", title=f"{target_sector} ({cap_class})", scale=alt.Scale(zero=False)),
                    y2="高値:Q",
                    color=alt.condition("datum.始値 <= datum.終値", alt.value("red"), alt.value("blue"))
                )
                bar = base.mark_bar().encode(
                    y="始値:Q",
                    y2="終値:Q",
                    color=alt.condition("datum.始値 <= datum.終値", alt.value("red"), alt.value("blue"))
                )
                
                candlestick = rule + bar
                
                # SMA Lines
                sma5 = base.mark_line(color='orange').encode(y='SMA5', tooltip=['SMA5'])
                sma25 = base.mark_line(color='purple').encode(y='SMA25', tooltip=['SMA25'])
                sma75 = base.mark_line(color='green').encode(y='SMA75', tooltip=['SMA75'])
                
                main_chart = candlestick + sma5 + sma25 + sma75
                
                # Benchmark Overlay
                if benchmark != "None":
                    bm_df = load_benchmark_data(benchmark)
                    if bm_df is not None:
                        # Normalize Benchmark matches Sector Start
                        # 1. Filter benchmark to match range roughly
                        bm_subset = bm_df[(bm_df["日付"] >= subset["日付"].min()) & (bm_df["日付"] <= subset["日付"].max())].copy()
                        
                        if not bm_subset.empty and not subset.empty:
                            # Rebase Factor
                            # Find the closest available data point for start date
                            sector_start_val = subset.iloc[0]["終値"]
                            bench_start_val = bm_subset.iloc[0]["Close"]
                            
                            if bench_start_val > 0:
                                factor = sector_start_val / bench_start_val
                                bm_subset["Rebased_Close"] = bm_subset["Close"] * factor
                                bm_subset["date_str"] = bm_subset["日付"].dt.strftime("%Y/%m/%d")
                                
                                # Filter to match subset dates for ordinal axis alignment
                                bm_subset = bm_subset[bm_subset["date_str"].isin(subset["date_str"])]

                                bm_line = alt.Chart(bm_subset).mark_line(strokeDash=[5,5], color='gray').encode(
                                    x=alt.X("date_str:O", axis=None), 
                                    y=alt.Y("Rebased_Close:Q", title=benchmark) # Share scale roughly
                                )
                                # Layer WITHOUT resolve_scale to enforce shared Y axis logic (since we rebased)
                                main_chart = alt.layer(main_chart, bm_line) 

                # Volume Chart (Ordinal X)
                vol_chart = base.mark_bar(color='gray').encode(
                    y=alt.Y("売買代金:Q", title="Volume"),
                    tooltip=["日付", "売買代金"]
                ).properties(height=100)
                
                final_chart = alt.vconcat(main_chart.properties(height=400, title=f"{target_sector} ({cap_class}) Price"), vol_chart)
                
                st.altair_chart(final_chart, use_container_width=True)

                # Breadth Stats
                # Calculate for the LAST DAY in the selected range
                if not subset.empty:
                    last_row = subset.iloc[-1]
                    last_date = last_row["date_str"]
                    up = int(last_row["上昇銘柄数"])
                    down = int(last_row["下落銘柄数"])
                    total = int(last_row["銘柄数"])
                    unchanged = total - (up + down)
                    
                    st.html(f"""
                    <h4>Market Breadth ({last_date})</h4>
                    <div style="font-size: 3em; font-weight: bold;">
                        Total: {total}
                    </div>
                    <div>
                        <span style="background-color: #e6fffa; color: #00b050; padding: 4px 8px; border-radius: 4px;">↑ Up: {up}</span>
                        <span style="background-color: #fff5f5; color: #e53e3e; padding: 4px 8px; border-radius: 4px;">↓ Down: {down}</span>
                        <span style="background-color: #edf2f7; color: #4a5568; padding: 4px 8px; border-radius: 4px;">→ Unchanged: {unchanged}</span>
                    </div>
                    """)

                    # === 3. Stock List Detail ===
                    st.divider()
                    st.subheader("3. Stock List Detail")
                    
                    STOCK_LIST_DIR = DATA_DIR / "stock_list"
                    date_clean = last_date.replace("/", "")
                    target_file = STOCK_LIST_DIR / f"{date_clean}_stock_list.csv"
                    
                    if target_file.exists():
                        df_list = pd.read_csv(target_file)
                        
                        # 1. Filter by Sector
                        # "TOPIX (Market Overall)" means ALL sectors
                        if target_sector != "TOPIX (Market Overall)":
                            df_list = df_list[df_list["Sector"] == target_sector]
                            
                        # 2. Filter by Market Cap
                        if cap_class != "全体":
                            df_list = df_list[df_list["MarketCapClass"] == cap_class]
                        
                        # Tabs
                        tab_all, tab_up, tab_down, tab_unchanged = st.tabs(["All", "Up", "Down", "Unchanged"])
                        
                        # Column Config
                        col_config = {
                            "Code": st.column_config.TextColumn("Code"),
                            "Name": st.column_config.TextColumn("Name"),
                            "Close": st.column_config.NumberColumn("Close", format="%.0f"),
                            "Return_1d": st.column_config.NumberColumn("1d Ret", format="%.2%", help="1 Day Return"),
                            "Return_1w": st.column_config.NumberColumn("1w Ret", format="%.2%", help="1 Week Return"),
                            "Return_1m": st.column_config.NumberColumn("1m Ret", format="%.2%", help="1 Month Return"),
                            "Volume_20d_Avg": st.column_config.NumberColumn("20d Avg Vol", format="%d", help="20-Day Average Trading Volume"),
                            "Sector": st.column_config.TextColumn("Sector"),
                        }
                        
                        # Sorting Default
                        df_list = df_list.sort_values("Return_1d", ascending=False)
                        
                        # Selecting Columns
                        display_cols = ["Code", "Name", "Sector", "Close", "Return_1d", "Return_1w", "Return_1m", "Volume_20d_Avg"]
                        
                        with tab_all:
                            st.dataframe(df_list[display_cols], use_container_width=True, hide_index=True, column_config=col_config)
                            
                        with tab_up:
                            st.dataframe(df_list[df_list["Return_1d"] > 0][display_cols], use_container_width=True, hide_index=True, column_config=col_config)
                            
                        with tab_down:
                            st.dataframe(df_list[df_list["Return_1d"] < 0][display_cols], use_container_width=True, hide_index=True, column_config=col_config)
                            
                        with tab_unchanged:
                            st.dataframe(df_list[df_list["Return_1d"] == 0][display_cols], use_container_width=True, hide_index=True, column_config=col_config)
                            
                    else:
                        st.info("No detailed stock list available for this date.")
        else:
            st.info("Synthetic index data not available yet.")

def show_verification():
    st.header("✅ Data Verification")
    st.write("Below are the raw summary data used for validation purposes.")

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
            st.dataframe(df_momentum, use_container_width=True)

            # 簡単な可視化
            if "売買代金5日平均/20日平均比率" in df_momentum.columns:
                st.bar_chart(df_momentum.set_index("業種")["売買代金5日平均/20日平均比率"])
        else:
            st.warning("No Momentum Summary data found.")

def show_data_management():
    st.header("⚙️ Data Management")
    
    st.info("""
    **機能の目的**:
    このページは、データの更新状態の確認や、手動でのデータ更新を行うための管理画面です。
    通常の運用では、データは自動的にバッチ処理で更新されるため、ここで操作を行う必要はありません。
    
    **使用シーン**:
    1.  **データが最新でない場合**: ダッシュボードの日付が古い場合、右の「Run Data Update」ボタンを押して強制的に最新データを取り込むことができます。
    2.  **エラー確認**: システムに異常がある場合、下の「Logs」からエラー内容を確認できます。
    """)

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

def main_app():
    st.title("Momentum Detector Dashboard")

    st.sidebar.title("Navigation")
    
    # Updated Navigation
    page = st.sidebar.radio("Go to", ["Momentum Trends", "Data Verification", "Data Management"])

    if page == "Momentum Trends":
        show_momentum_trends()
    elif page == "Data Verification":
        show_verification()
    elif page == "Data Management":
        show_data_management()

if __name__ == "__main__":
    main_app()
