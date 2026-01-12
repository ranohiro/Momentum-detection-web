# -*- coding: utf-8 -*-
import pandas as pd
from pathlib import Path
from industry_name_mapping import industry_name_mapping
import logging

# ロギング設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ... (existing imports)
import math

# ... (logging setup)

# === ディレクトリ準備 ===
raw_stock_dir = Path("data/raw/japan_all_stock")
raw_index_dir = Path("data/raw/tosho_index")
sector_dir = Path("data/processed_data/sector_summary")
momentum_dir = Path("data/processed_data/momentum_summary")
indices_dir = Path("data/processed_data/indices")
indices_daily_dir = indices_dir / "daily"
stock_list_dir = Path("data/processed_data/stock_list")
sector_dir.mkdir(parents=True, exist_ok=True)
momentum_dir.mkdir(parents=True, exist_ok=True)
indices_dir.mkdir(parents=True, exist_ok=True)
indices_daily_dir.mkdir(parents=True, exist_ok=True)
stock_list_dir.mkdir(parents=True, exist_ok=True)

# === 時価総額帯分類 (Updated Def) ===
def classify_market_cap(x):
    # x is in Millions JPY
    # 小型: < 100億円 (10,000 百万円)
    # 中型: < 1000億円 (100,000 百万円)
    # 大型: < 1兆円 (1,000,000 百万円)
    # 超大型: >= 1兆円
    if x < 10_000:
        return "小型"
    elif x < 100_000:
        return "中型"
    elif x < 1_000_000:
        return "大型"
    else:
        return "超大型"

# === sector_summary 集計 ===
def aggregate_sector(stock_df, index_df, date_slash):
    result = []
    grouped = stock_df.groupby(["業種", "時価総額帯"])
    for (industry, cap), group in grouped:
        up = group["上昇フラグ"].sum()
        down = group["下落フラグ"].sum()
        total_val = group["売買代金（千円）"].sum()
        if cap == "全体":
            weighted_avg = 0  # 後で全体を index_df から取得
        else:
            div = max(group["時価総額（百万円）"].sum(), 1)
            weighted_avg = (group["前日比（％）"] * group["時価総額（百万円）"]).sum() / div
        result.append({
            "日付": date_slash,
            "業種": industry,
            "時価総額帯": cap,
            "上昇銘柄数": int(up),
            "下落銘柄数": int(down),
            "時価総額加重平均騰落率": round(weighted_avg,3),
            "売買代金合計": int(total_val)
        })
    sector_df = pd.DataFrame(result)

    # 全体行追加
    new_rows = []
    for industry, group in sector_df.groupby("業種"):
        total_val = group["売買代金合計"].sum()
        div = max(total_val, 1)
        weighted_avg = (group["時価総額加重平均騰落率"] * group["売買代金合計"]).sum() / div
        new_rows.append({
            "日付": date_slash,
            "業種": industry,
            "時価総額帯": "全体",
            "上昇銘柄数": int(group["上昇銘柄数"].sum()),
            "下落銘柄数": int(group["下落銘柄数"].sum()),
            "時価総額加重平均騰落率": 0,  # 後で index_df から置換
            "売買代金合計": int(total_val)
        })
    
    if new_rows:
        sector_df = pd.concat([sector_df, pd.DataFrame(new_rows)], ignore_index=True)

    # 全体区分の平均騰落率を index_df から取得
    for idx, row in sector_df.iterrows():
        if row["時価総額帯"] == "全体":
            matched = index_df[index_df["指数名"] == row["業種"]]
            if not matched.empty:
                sector_df.at[idx, "時価総額加重平均騰落率"] = float(matched.iloc[0]["前日比（％）"])
    return sector_df

# === momentum_summary 集計 ===
def compute_momentum(stock_files, date_str):
    stock_files_sorted = sorted(stock_files)
    
    # 対象日ファイルのインデックスを探す
    target_idx = -1
    for i, f in enumerate(stock_files_sorted):
        if f.stem.endswith(date_str):
            target_idx = i
            break
            
    if target_idx == -1:
        return None

    # 過去20営業日分
    start_idx = max(0, target_idx-19)
    recent_files = stock_files_sorted[start_idx:target_idx+1]

    df_list = []
    for f in recent_files:
        try:
            df_tmp = pd.read_csv(f, encoding="cp932")
        except Exception as e:
            logger.warning(f"Failed to read {f}: {e}")
            continue

        if "業種" in df_tmp.columns:
            df_tmp = df_tmp[df_tmp["業種"] != "株価指数"] # ダミー行削除

        df_tmp["業種"] = df_tmp["業種"].replace(industry_name_mapping)
        val_col_candidates = [c for c in df_tmp.columns if "売買代金" in c]
        if not val_col_candidates:
            continue
        val_col = val_col_candidates[0]
        df_tmp["売買代金（千円）"] = pd.to_numeric(df_tmp[val_col].astype(str).str.replace(",", ""), errors="coerce").fillna(0)
        
        # 日付カラムがない場合はファイル名から推測、あるいは既にあると仮定
        if "日付" in df_tmp.columns:
            # 日付フォーマットの正規化
            # data/rawのcsv日付フォーマットに依存するが、ここでは単純に読み込み
            df_tmp["日付"] = pd.to_datetime(df_tmp["日付"].astype(str))
        else:
             # ファイル名から日付を取得して付与 (YYYYMMDD -> YYYY/MM/DD)
            d_str = f.stem.split("_")[-1]
            if len(d_str) == 8:
                df_tmp["日付"] = f"{d_str[:4]}/{d_str[4:6]}/{d_str[6:]}"

        # 日付型へ変換して統一
        df_tmp["日付"] = pd.to_datetime(df_tmp["日付"]).dt.date
        
        df_list.append(df_tmp[["日付","業種","売買代金（千円）"]])
    
    if not df_list:
        return None

    # 過去20営業日分を結合
    df_concat = pd.concat(df_list, ignore_index=True)
    df_concat = df_concat.sort_values(["業種","日付"])

    # 日付ごと業種別売買代金合計
    daily_sum = df_concat.groupby(["日付", "業種"], as_index=False)["売買代金（千円）"].sum()

    # === 市場全体（All Market）の追加 ===
    market_sum = df_concat.groupby(["日付"], as_index=False)["売買代金（千円）"].sum()
    market_sum["業種"] = "市場全体"
    daily_sum = pd.concat([daily_sum, market_sum], ignore_index=True)
    
    # ソート（日付順、業種順）
    daily_sum = daily_sum.sort_values(["日付", "業種"])

    # 各業種ごとの rolling 平均
    for n in [3, 5, 10, 20]:
        col_name = f"売買代金{n}日平均"
        daily_sum[col_name] = daily_sum.groupby("業種")["売買代金（千円）"].transform(
            lambda x: x.rolling(n, min_periods=1).mean()
        )

    # 比率計算
    daily_sum["売買代金5日平均/20日平均比率"] = (daily_sum["売買代金5日平均"] / daily_sum["売買代金20日平均"]).round(3)
    daily_sum["売買代金3日平均/10日平均比率"] = (daily_sum["売買代金3日平均"] / daily_sum["売買代金10日平均"]).round(3)

    # 最新日(処理対象日)だけ抽出
    target_date = pd.to_datetime(date_str).date() # date_str (YYYYMMDD) -> logic date
    momentum_df = daily_sum[daily_sum["日付"]==target_date].copy()

    # 保存用に日付を "YYYY/MM/DD" に変換
    momentum_df["日付"] = pd.to_datetime(momentum_df["日付"]).dt.strftime("%Y/%m/%d")

    return momentum_df

# === Synthetic Index Generation (Return-Based) ===
def generate_synthetic_indices(stock_df, date_str):
    """
    Generate synthetic Index data based on Weighted Average Returns.
    This avoids "share count" discontinuities.
    Returns: [Date, Industry, Cap, Wt_Ret_Open, Wt_Ret_High, Wt_Ret_Low, Wt_Ret_Close, Volume, Breadth...]
    """
    # Required cols: 始値, 高値, 安値, 終値, 前日終値, 時価総額（百万円）, 売買代金（千円）
    
    # 1. Cleaning
    stock_df = stock_df.copy()
    stock_df["終値"] = pd.to_numeric(stock_df["終値"], errors="coerce")
    stock_df["前日終値"] = pd.to_numeric(stock_df["前日終値"], errors="coerce")
    
    # Fill Open/High/Low with Close if missing (for liquidity holes)
    for col in ["始値", "高値", "安値"]:
        stock_df[col] = pd.to_numeric(stock_df[col], errors="coerce").fillna(stock_df["終値"])
        
    # If PrevClose is missing, assume it equals Open (0% gap) or Close (0% move)?
    # Usually Previous Close should exist. If not (IPO), exclude from weight?
    # For now, fill with Open to imply no overnight gap, or exclude.
    # Exclude is safer for "Same Store Sales" logic.
    valid_data = stock_df.dropna(subset=["前日終値", "時価総額（百万円）"])
    valid_data = valid_data[valid_data["前日終値"] > 0]
    
    # 2. Calculate Individual Returns (vs Prev Close)
    # Note: 1.05 means +5%. 
    # We want weighted average of these Ratios.
    # Ratio_Open = Open / PrevClose
    valid_data["R_Open"] = valid_data["始値"] / valid_data["前日終値"]
    valid_data["R_High"] = valid_data["高値"] / valid_data["前日終値"]
    valid_data["R_Low"] = valid_data["安値"] / valid_data["前日終値"]
    valid_data["R_Close"] = valid_data["終値"] / valid_data["前日終値"]
    
    # Weights
    valid_data["Weight_Val"] = valid_data["時価総額（百万円）"]
    
    results = []
    
    def agg_group(grp, industry, cap_class):
        total_cap = grp["Weight_Val"].sum()
        total_vol = grp["売買代金（千円）"].sum()
        
        # Breadth (Use raw stock_df to include even if prices weird, but consistency matters)
        # Using grp (valid data only) is safer for return calc, but breadth might want all.
        # Let's use grp for consistency.
        up = (grp["前日比"] > 0).sum()
        down = (grp["前日比"] < 0).sum()
        total = len(grp)
        
        if total_cap > 0:
            # Weighted Averages of Ratios
            # Sum(Ratio * Cap) / Sum(Cap)
            w_r_open = (grp["R_Open"] * grp["Weight_Val"]).sum() / total_cap
            w_r_high = (grp["R_High"] * grp["Weight_Val"]).sum() / total_cap
            w_r_low = (grp["R_Low"] * grp["Weight_Val"]).sum() / total_cap
            w_r_close = (grp["R_Close"] * grp["Weight_Val"]).sum() / total_cap
        else:
            w_r_open = w_r_high = w_r_low = w_r_close = 1.0 # Flat
            
        return {
            "日付": date_str,
            "業種": industry,
            "時価総額帯": cap_class,
            "R_Open": w_r_open,
            "R_High": w_r_high,
            "R_Low": w_r_low,
            "R_Close": w_r_close,
            "売買代金": total_vol,
            "上昇銘柄数": up,
            "下落銘柄数": down,
            "銘柄数": total
        }

    # Group by Industry & Cap
    for (ind, cap), grp in valid_data.groupby(["業種", "時価総額帯"]):
        results.append(agg_group(grp, ind, cap))
        
    # Group by Industry (All)
    for ind, grp in valid_data.groupby("業種"):
        results.append(agg_group(grp, ind, "全体"))
        
    return pd.DataFrame(results)

def consolidate_indices():
    logger.info("Consolidating indices (Chain-Linking)...")
    daily_files = sorted(indices_daily_dir.glob("*.csv"))
    if not daily_files:
        logger.warning("No daily index files found.")
        return

    all_dfs = []
    for f in daily_files:
        try:
            all_dfs.append(pd.read_csv(f))
        except:
            pass
            
    if not all_dfs:
        return
        
    full_df = pd.concat(all_dfs, ignore_index=True)
    full_df = full_df.sort_values(["業種", "時価総額帯", "日付"])
    
    # Process each group to chain-link
    # Base Value = 1000
    
    def calculate_index_series(grp):
        grp = grp.sort_values("日付").reset_index(drop=True)
        # Init arrays
        opens = []
        highs = []
        lows = []
        closes = []
        
        current_close = 1000.0
        
        # We need to construct the series.
        # Day 0: We only have returns relative to "Yesterday".
        # But we don't have Yesterday's index.
        # Assume Day 0 starts at 1000 (Open? or PrevClose?)
        # Let's assume PrevClose of Day 0 was 1000.
        
        for idx, row in grp.iterrows():
            # Apply today's moves to PrevClose
            # PrevClose is `current_close` from last iteration
            
            day_open = current_close * row["R_Open"]
            day_high = current_close * row["R_High"]
            day_low = current_close * row["R_Low"]
            day_close = current_close * row["R_Close"]
            
            opens.append(day_open)
            highs.append(day_high)
            lows.append(day_low)
            closes.append(day_close)
            
            current_close = day_close
            
        grp["始値"] = opens
        grp["高値"] = highs
        grp["安値"] = lows
        grp["終値"] = closes
        
        # Drop logic columns
        return grp.drop(columns=["R_Open", "R_High", "R_Low", "R_Close"])

    # Split by Industry and Save
    # Split by Industry and Save
    # Actual loop
    unique_industries = full_df["業種"].unique()
    logger.info(f"Unique Industries: {len(unique_industries)}")
    
    for industry in unique_industries:
        ind_df = full_df[full_df["業種"] == industry]
        
        # Apply chain linking per Cap Class
        processed_dfs = []
        for cap, subgrp in ind_df.groupby("時価総額帯"):
            # logger.info(f"Calculating series for {industry} - {cap} (Rows: {len(subgrp)})")
            res = calculate_index_series(subgrp)
            # logger.info(f"Result cols: {res.columns.tolist()}")
            processed_dfs.append(res)
            
        final_ind_df = pd.concat(processed_dfs).sort_values(["日付", "時価総額帯"])
        
        # Verify columns before save
        if "始値" not in final_ind_df.columns:
             logger.error(f"Failed to generate OHLC for {industry}. Cols: {final_ind_df.columns}")
        
        safe_name = industry.replace("・", "_").replace("、", "_").replace(" ", "_")
        output_path = indices_dir / f"{safe_name}.csv"
        final_ind_df.to_csv(output_path, index=False, encoding="utf-8-sig")
        
    # Market Overall per Cap Class
    # Need to aggregate R_Close etc. similarly?
    # No, "Market Overall" needs to be weighted average of SECTORS?
    # Or just sum of all Valid Data? 
    # Let's Agg again from full_df?
    # No, full_df has 'Industry' rows.
    # To get 'Market Overall', ideally we aggregate all raw stocks.
    # But here we only have sector summaries.
    # Aggregating sector Ratios by sector Weights? We calculated Sector Ratios. 
    # We didn't save Sector Total Caps in `generate_synthetic_indices`.
    # It's better to just skip Market Overall *Index* for now, or just Sum Breadth/Volume.
    
    market_grp = full_df.groupby(["日付", "時価総額帯"], as_index=False).apply(lambda x: pd.Series({
        "売買代金": x["売買代金"].sum(),
        "上昇銘柄数": x["上昇銘柄数"].sum(),
        "下落銘柄数": x["下落銘柄数"].sum(),
        "銘柄数": x["銘柄数"].sum()
    })) # Deprecated apply usage, but sticking to pattern
    market_grp["業種"] = "市場全体"
    # No prices for Market Overall yet.
    
    market_output = indices_dir / "市場全体.csv"
    market_grp.to_csv(market_output, index=False, encoding="utf-8-sig")
    
    logger.info("Consolidation complete.")

# === Stock List Generation (for App Detail View) ===
def generate_stock_list(stock_files, date_str):
    stock_files_sorted = sorted(stock_files)
    
    # Target Index
    target_idx = -1
    for i, f in enumerate(stock_files_sorted):
        if f.stem.endswith(date_str):
            target_idx = i
            break
            
    if target_idx == -1:
        return False

    # Define range (Past 20 files max)
    # used for Volume Avg and 1m Return
    start_idx = max(0, target_idx - 19)
    recent_files = stock_files_sorted[start_idx : target_idx + 1]
    
    # Load all files in range
    dfs = []
    for f in recent_files:
        try:
            d_s = f.stem.split("_")[-1]
            # Date object
            dt = pd.to_datetime(d_s).date()
            
            df = pd.read_csv(f, encoding="cp932")
            # Rename Raw Columns (SC -> コード, 名称 -> 銘柄名)
            df = df.rename(columns={"SC": "コード", "名称": "銘柄名", "株価": "終値"})

            # Cleaning
            if "業種" in df.columns:
                df = df[df["業種"] != "株価指数"]
            
            df["業種"] = df["業種"].replace(industry_name_mapping)
            
            # Numeric conversion
            df["終値"] = pd.to_numeric(df["終値"].astype(str).str.replace(",", "").replace("-", ""), errors="coerce")
            
            # Identify Volume Column
            val_col_candidates = [c for c in df.columns if "売買代金" in c]
            if val_col_candidates:
                df["売買代金"] = pd.to_numeric(df[val_col_candidates[0]].astype(str).str.replace(",", ""), errors="coerce").fillna(0)
            else:
                df["売買代金"] = 0
                
            # Cap Class (Need to recalc or trust raw? Recalc specific to date)
            df["時価総額（百万円）"] = pd.to_numeric(df["時価総額（百万円）"].astype(str).str.replace(",", "").replace("-","0"), errors="coerce")
            df["MarketCapClass"] = df["時価総額（百万円）"].apply(classify_market_cap)

            # Keep necessary cols
            # コード, 銘柄名, 業種, 終値, 売買代金, MarketCapClass
            df = df[["コード", "銘柄名", "業種", "終値", "売買代金", "MarketCapClass"]].copy()
            df["Date"] = dt
            dfs.append(df)
            
        except Exception as e:
            logger.warning(f"Error reading stock file {f}: {e}")
            continue
            
    if not dfs:
        return False
        
    df_concat = pd.concat(dfs, ignore_index=True)
    
    # --- Base Data (Today) ---
    target_date = pd.to_datetime(date_str).date()
    df_base = df_concat[df_concat["Date"] == target_date].copy()
    if df_base.empty:
        return False
        
    df_base = df_base.rename(columns={"終値": "Close", "銘柄名": "Name", "業種": "Sector", "コード": "Code"})
    
    # --- 1. Volume 20d Avg ---
    # Avg of available data in the 20d window
    vol_avg = df_concat.groupby("コード")["売買代金"].mean().reset_index().rename(columns={"売買代金": "Volume_20d_Avg", "コード": "Code"})
    df_base = df_base.merge(vol_avg, on="Code", how="left")
    
    # --- 2. Returns Calculation ---
    # Helper to get past close
    def get_past_close(days_ago_idx):
        # recent_files is [..., target]
        # target_idx is recent_files[-1]
        # days_ago is index from end. 
        # e.g. 1d ago = -2, 5d ago = -6
        if len(recent_files) >= days_ago_idx:
             past_date = pd.to_datetime(recent_files[-days_ago_idx].stem.split("_")[-1]).date()
             # extract from df_concat
             past_df = df_concat[df_concat["Date"] == past_date][["コード", "終値"]]
             return past_df.rename(columns={"終値": "Close_Past", "コード": "Code"})
        return None

    # 1d Return (vs 1 file ago) - 2nd from last
    r1_df = get_past_close(2)
    if r1_df is not None:
        df_base = df_base.merge(r1_df, on="Code", how="left", suffixes=("", "_1d"))
        df_base["Return_1d"] = (df_base["Close"] / df_base["Close_Past"] - 1)
        df_base = df_base.drop(columns=["Close_Past"])
    else:
        df_base["Return_1d"] = 0.0

    # 1w Return (vs 5 files ago) - 6th from last
    r1w_df = get_past_close(6) 
    if r1w_df is not None:
        df_base = df_base.merge(r1w_df, on="Code", how="left", suffixes=("", "_1w"))
        df_base["Return_1w"] = (df_base["Close"] / df_base["Close_Past"] - 1)
        df_base = df_base.drop(columns=["Close_Past"])
    else:
        df_base["Return_1w"] = 0.0

    # 1m Return (vs 20 files ago) - 20 (approx 1 month) -> file list length is 20, so 1st file (index 0) = -20
    # recent_files has max 20 items. index 0 is the oldest.
    # index 0 corresponds to 'Length' days ago?
    # No, recent_files[-20] is the first item.
    r1m_df = get_past_close(20)
    if r1m_df is not None:
        df_base = df_base.merge(r1m_df, on="Code", how="left", suffixes=("", "_1m"))
        df_base["Return_1m"] = (df_base["Close"] / df_base["Close_Past"] - 1)
        df_base = df_base.drop(columns=["Close_Past"])
    else:
        df_base["Return_1m"] = 0.0
        
    # Formatting
    # Rounding
    for col in ["Return_1d", "Return_1w", "Return_1m"]:
        df_base[col] = df_base[col].fillna(0).round(4)
        
    df_base["Volume_20d_Avg"] = df_base["Volume_20d_Avg"].fillna(0).astype(int)
    
    # Save
    out_path = stock_list_dir / f"{date_str}_stock_list.csv"
    
    # Select final columns
    out_cols = ["Code", "Name", "Sector", "MarketCapClass", "Close", "Return_1d", "Return_1w", "Return_1m", "Volume_20d_Avg"]
    df_base[out_cols].to_csv(out_path, index=False, encoding="utf-8-sig")
    return True

# === Main Batch Processing ===
def process_date(date_str, stock_file, index_file, stock_files_all):
    logger.info(f"Processing {date_str}...")
    try:
        # 日付文字列 (YYYY/MM/DD)
        date_slash = f"{date_str[:4]}/{date_str[4:6]}/{date_str[6:]}"

        # === CSV読込 ===
        stock_df = pd.read_csv(stock_file, encoding="cp932")
        stock_df = stock_df.rename(columns={"株価": "終値"}) # 株価 -> 終値
        stock_df = stock_df[stock_df["業種"] != "株価指数"] 
        index_df = pd.read_csv(index_file, encoding="cp932")

        # 日付列統一
        for df in [stock_df, index_df]:
            if "日付" in df.columns:
                df["日付"] = pd.to_datetime(df["日付"].astype(str)).dt.strftime("%Y/%m/%d")

        # 業種名統一
        stock_df["業種"] = stock_df["業種"].replace(industry_name_mapping)

        # 数値化
        stock_df["時価総額（百万円）"] = (
            stock_df["時価総額（百万円）"].astype(str).str.replace(",", "").replace("-", "0").astype(float)
        )
        stock_df["前日比"] = pd.to_numeric(stock_df["前日比"], errors="coerce").fillna(0)
        stock_df["売買代金（千円）"] = pd.to_numeric(stock_df["売買代金（千円）"], errors="coerce").fillna(0)
        stock_df["前日比（％）"] = pd.to_numeric(stock_df["前日比（％）"], errors="coerce").fillna(0)

        # 時価総額帯分類
        stock_df["時価総額帯"] = stock_df["時価総額（百万円）"].apply(classify_market_cap)

        # 上昇/下落フラグ
        stock_df["上昇フラグ"] = stock_df["前日比"] > 0
        stock_df["下落フラグ"] = stock_df["前日比"] <= 0

        # 1. Sector Summary 作成
        sector_df = aggregate_sector(stock_df, index_df, date_slash)
        
        # ランキング（全体）
        ranking = sector_df[sector_df["時価総額帯"]=="全体"].copy()
        ranking["平均騰落率順位"] = ranking["時価総額加重平均騰落率"].rank(ascending=False, method="min").astype(int)
        sector_df = sector_df.merge(ranking[["業種","平均騰落率順位"]], on="業種", how="left")

        # 保存
        output_sector = sector_dir / f"{date_str}_sector_summary.csv"
        sector_df.to_csv(output_sector, index=False, encoding="utf-8-sig")

        # 2. Momentum Summary 作成
        momentum_df = compute_momentum(stock_files_all, date_str)
        if momentum_df is not None and not momentum_df.empty:
            # === 騰落率データの結合 ===
            industry_returns = sector_df[sector_df["時価総額帯"]=="全体"][["業種", "時価総額加重平均騰落率"]]
            
            # 市場全体(Market Overall)の騰落率計算
            total_cap = stock_df["時価総額（百万円）"].sum()
            if total_cap > 0:
                market_return = (stock_df["前日比（％）"] * stock_df["時価総額（百万円）"]).sum() / total_cap
            else:
                market_return = 0.0
            
            market_return_df = pd.DataFrame([{"業種": "市場全体", "時価総額加重平均騰落率": round(market_return, 3)}])
            industry_returns = pd.concat([industry_returns, market_return_df], ignore_index=True)
            
            momentum_df = momentum_df.merge(industry_returns, on="業種", how="left")
            output_momentum = momentum_dir / f"{date_str}_momentum_summary.csv"
            momentum_df.to_csv(output_momentum, index=False, encoding="utf-8-sig")
            
        # 3. Synthetic Index (Daily) 作成
        syn_df = generate_synthetic_indices(stock_df, date_str)
        # 日付フォーマットを YYYY/MM/DD になおしておく
        syn_df["日付"] = date_slash
        syn_output = indices_daily_dir / f"{date_str}_synthetic.csv"
        syn_df.to_csv(syn_output, index=False, encoding="utf-8-sig")

        # 4. Stock List Generation (Detail View)
        # Only run if raw files exist (already checked in process_date but we neeed stock_files_all)
        # We pass stock_files_all to it.
        generate_stock_list(stock_files_all, date_str)

        return True

    except Exception as e:
        logger.error(f"Error processing {date_str}: {e}")
        return False


def main():
    # ファイル一覧取得
    stock_files = sorted(raw_stock_dir.glob("japan-all-stock-prices_*.csv"))
    index_files = sorted(raw_index_dir.glob("tosho-index-data_*.csv"))
    
    stock_map = {f.stem.split("_")[-1]: f for f in stock_files}
    index_map = {f.stem.split("_")[-1]: f for f in index_files}
    
    common_dates = sorted(list(set(stock_map.keys()) & set(index_map.keys())))
    
    logger.info(f"Found {len(common_dates)} dates to process.")
    
    for date_str in common_dates:
        process_date(date_str, stock_map[date_str], index_map[date_str], stock_files)

    # Post-processing
    consolidate_indices()

    logger.info("Batch processing completed.")

if __name__ == "__main__":
    main()