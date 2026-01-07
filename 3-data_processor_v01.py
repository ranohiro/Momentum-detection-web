# -*- coding: utf-8 -*-
import pandas as pd
from pathlib import Path
from industry_name_mapping import industry_name_mapping
import sys

# === ディレクトリ準備 ===
raw_stock_dir = Path("data/raw/japan_all_stock")
raw_index_dir = Path("data/raw/tosho_index")
sector_dir = Path("data/processed_data/sector_summary")
momentum_dir = Path("data/processed_data/momentum_summary")
sector_dir.mkdir(parents=True, exist_ok=True)
momentum_dir.mkdir(parents=True, exist_ok=True)

# === 時価総額帯分類 ===
def classify_market_cap(x):
    if x < 10_000:
        return "小型"
    elif x < 100_000:
        return "中型"
    elif x < 1_000_000:
        return "大型"
    else:
        return "超大型"

# === sector_summary 集計ロジック ===
def process_sector_summary(stock_file, index_file, date_slash, date_str):
    print(f"   Processing Sector Summary for {date_str}...")
    stock_df = pd.read_csv(stock_file, encoding="cp932")
    if "業種" in stock_df.columns:
        stock_df = stock_df[stock_df["業種"] != "株価指数"]

    stock_df["業種"] = stock_df["業種"].replace(industry_name_mapping)

    # 数値化
    stock_df["時価総額（百万円）"] = (
        stock_df["時価総額（百万円）"].astype(str).str.replace(",", "").replace("-", "0").astype(float)
    )
    stock_df["前日比"] = pd.to_numeric(stock_df["前日比"], errors="coerce").fillna(0)
    stock_df["前日比（％）"] = pd.to_numeric(stock_df["前日比（％）"], errors="coerce").fillna(0)
    stock_df["売買代金（千円）"] = pd.to_numeric(stock_df["売買代金（千円）"], errors="coerce").fillna(0)

    stock_df["時価総額帯"] = stock_df["時価総額（百万円）"].apply(classify_market_cap)
    stock_df["上昇フラグ"] = stock_df["前日比"] > 0
    stock_df["下落フラグ"] = stock_df["前日比"] <= 0

    index_df = pd.read_csv(index_file, encoding="cp932")

    result = []
    grouped = stock_df.groupby(["業種", "時価総額帯"])
    for (industry, cap), group in grouped:
        up = group["上昇フラグ"].sum()
        down = group["下落フラグ"].sum()
        total_val = group["売買代金（千円）"].sum()

        # 時価総額加重平均騰落率
        total_cap = group["時価総額（百万円）"].sum()
        if total_cap > 0:
            weighted_avg = (group["前日比（％）"] * group["時価総額（百万円）"]).sum() / total_cap
        else:
            weighted_avg = 0

        result.append({
            "日付": date_slash,
            "業種": industry,
            "時価総額帯": cap,
            "上昇銘柄数": int(up),
            "下落銘柄数": int(down),
            "時価総額加重平均騰落率": round(weighted_avg, 3),
            "売買代金合計": int(total_val)
        })

    sector_df = pd.DataFrame(result)
    if sector_df.empty:
        return

    # 全体行追加
    new_rows = []
    for industry, group in sector_df.groupby("業種"):
        total_val = group["売買代金合計"].sum()
        # weighted average of weighted averages needs care, simpler to go back to stock_df but here we approximate or re-aggregate
        # Correct way: use raw stock_df for sector total
        sub_stock = stock_df[stock_df["業種"] == industry]
        total_cap_sub = sub_stock["時価総額（百万円）"].sum()
        if total_cap_sub > 0:
            w_avg_total = (sub_stock["前日比（％）"] * sub_stock["時価総額（百万円）"]).sum() / total_cap_sub
        else:
            w_avg_total = 0

        new_rows.append({
            "日付": date_slash,
            "業種": industry,
            "時価総額帯": "全体",
            "上昇銘柄数": int(group["上昇銘柄数"].sum()),
            "下落銘柄数": int(group["下落銘柄数"].sum()),
            "時価総額加重平均騰落率": round(w_avg_total, 3), # ここはindex_dfの値で上書きされるロジックだったが、計算値を入れる
            "売買代金合計": int(total_val)
        })

    sector_df = pd.concat([sector_df, pd.DataFrame(new_rows)], ignore_index=True)

    # 全体区分の平均騰落率を index_df から取得 (既存ロジック踏襲)
    for idx, row in sector_df.iterrows():
        if row["時価総額帯"] == "全体":
            matched = index_df[index_df["指数名"] == row["業種"]]
            if not matched.empty:
                sector_df.at[idx, "時価総額加重平均騰落率"] = float(matched.iloc[0]["前日比（％）"])

    # ランキング（全体）
    ranking = sector_df[sector_df["時価総額帯"]=="全体"].copy()
    if not ranking.empty:
        ranking["平均騰落率順位"] = ranking["時価総額加重平均騰落率"].rank(ascending=False, method="min").astype(int)
        sector_df = sector_df.merge(ranking[["業種","平均騰落率順位"]], on="業種", how="left")

    output_file = sector_dir / f"{date_str}_sector_summary.csv"
    sector_df.to_csv(output_file, index=False, encoding="utf-8-sig")


# === momentum_summary 集計ロジック ===
def process_momentum_summary(stock_files_sorted, target_date_str, date_slash):
    print(f"   Processing Momentum Summary for {target_date_str}...")

    # 最新日ファイルのインデックス
    target_idx = -1
    for i, f in enumerate(stock_files_sorted):
        if f.stem.endswith(target_date_str):
            target_idx = i
            break

    if target_idx == -1:
        return

    # 過去20営業日分
    start_idx = max(0, target_idx - 19)
    recent_files = stock_files_sorted[start_idx : target_idx + 1]

    df_list = []
    for f in recent_files:
        df_tmp = pd.read_csv(f, encoding="cp932")
        if "業種" in df_tmp.columns:
            df_tmp = df_tmp[df_tmp["業種"] != "株価指数"]

        df_tmp["業種"] = df_tmp["業種"].replace(industry_name_mapping)

        # 売買代金
        val_col_candidates = [c for c in df_tmp.columns if "売買代金" in c]
        if not val_col_candidates:
            continue
        val_col = val_col_candidates[0]
        df_tmp["売買代金（千円）"] = pd.to_numeric(df_tmp[val_col].astype(str).str.replace(",", ""), errors="coerce").fillna(0)

        # 時価総額（時価総額帯用）
        cap_col_candidates = [c for c in df_tmp.columns if "時価総額" in c]
        if cap_col_candidates:
            cap_col = cap_col_candidates[0]
            df_tmp["時価総額（百万円）"] = pd.to_numeric(df_tmp[cap_col].astype(str).str.replace(",", "").replace("-","0"), errors="coerce").fillna(0)
            df_tmp["時価総額帯"] = df_tmp["時価総額（百万円）"].apply(classify_market_cap)
        else:
            df_tmp["時価総額帯"] = "不明"

        if "日付" in df_tmp.columns:
            # 日付フォーマット統一
            d_str = str(df_tmp.iloc[0]["日付"]).replace("/","").replace("-","") # 簡易処理
            df_tmp["日付"] = d_str # YYYYMMDD想定

        df_list.append(df_tmp[["日付", "業種", "時価総額帯", "売買代金（千円）"]])

    if not df_list:
        return

    df_concat = pd.concat(df_list, ignore_index=True)

    # --- 集計1: 業種別 ---
    # 日付ごと業種別売買代金合計
    daily_sector = df_concat.groupby(["日付", "業種"], as_index=False)["売買代金（千円）"].sum()

    # Rolling平均計算
    for n in [3, 5, 10, 20]:
        col_name = f"売買代金{n}日平均"
        daily_sector[col_name] = daily_sector.groupby("業種")["売買代金（千円）"].transform(
            lambda x: x.rolling(n, min_periods=1).mean()
        )

    daily_sector["区分"] = "業種"
    daily_sector = daily_sector.rename(columns={"業種": "名称"}) # 共通カラム名に変更

    # --- 集計2: 時価総額帯別 ---
    daily_cap = df_concat.groupby(["日付", "時価総額帯"], as_index=False)["売買代金（千円）"].sum()

    for n in [3, 5, 10, 20]:
        col_name = f"売買代金{n}日平均"
        daily_cap[col_name] = daily_cap.groupby("時価総額帯")["売買代金（千円）"].transform(
            lambda x: x.rolling(n, min_periods=1).mean()
        )

    daily_cap["区分"] = "時価総額帯"
    daily_cap = daily_cap.rename(columns={"時価総額帯": "名称"})

    # 結合
    combined_df = pd.concat([daily_sector, daily_cap], ignore_index=True)

    # 比率計算
    combined_df["売買代金5日平均/20日平均比率"] = (combined_df["売買代金5日平均"] / combined_df["売買代金20日平均"]).round(3)
    combined_df["売買代金3日平均/10日平均比率"] = (combined_df["売買代金3日平均"] / combined_df["売買代金10日平均"]).round(3)

    # 最新日のみ抽出（日付フォーマットの揺れに注意）
    # df_concat["日付"]は元ファイルの形式、ここでのlatest判定は引数date_strと比較
    # df_listで読み込んだ日付はYYYYMMDD形式に変換してある前提
    # target_date_str は YYYYMMDD

    # 実際の日付列の値を確認 (各ファイルの中身に依存するが、dummy dataでは YYYY/MM/DD)
    # df_tmp["日付"] = d_str (YYYYMMDD) とした。

    latest_df = combined_df[combined_df["日付"].astype(str).str.replace("/","") == target_date_str].copy()

    if latest_df.empty:
        # 日付マッチしない場合のバックアップ：データ内の最大日付を使う
        max_date = combined_df["日付"].max()
        latest_df = combined_df[combined_df["日付"] == max_date].copy()

    # 出力整形
    # app.py との互換性のために "業種" カラムもあったほうがいいかもしれないが、
    # 今回は app.py も改修するため "名称" と "区分" で統一する。
    # ただし、app.py の既存ロジックが "業種" を探すかもしれないので、"業種" に "名称" をコピーしておく
    latest_df["業種"] = latest_df["名称"]
    latest_df["日付"] = date_slash # 保存用にスラッシュ区切り

    output_file = momentum_dir / f"{target_date_str}_momentum_summary.csv"
    latest_df.to_csv(output_file, index=False, encoding="utf-8-sig")


# === メイン処理 ===
def main():
    stock_files = sorted(raw_stock_dir.glob("japan-all-stock-prices_*.csv"))
    if not stock_files:
        print("No stock files found.")
        return

    print(f"Found {len(stock_files)} stock files. Start processing...")

    for stock_file in stock_files:
        date_str = stock_file.stem.split("_")[-1]
        date_slash = f"{date_str[:4]}/{date_str[4:6]}/{date_str[6:]}"

        index_file_name = f"tosho-index-data_{date_str}.csv"
        index_file = raw_index_dir / index_file_name

        if not index_file.exists():
            print(f"Skipping {date_str}: Index file not found.")
            continue

        # Sector Summary
        process_sector_summary(stock_file, index_file, date_slash, date_str)

        # Momentum Summary (Market Cap included)
        process_momentum_summary(stock_files, date_str, date_slash)

    print("All processing complete.")

if __name__ == "__main__":
    main()
