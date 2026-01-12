import gspread
import pandas as pd
import numpy as np
import requests
from google.oauth2.service_account import Credentials

# ==============================
# Googleスプレッドシート設定
# ==============================
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SERVICE_ACCOUNT_FILE = "credentials.json"
SPREADSHEET_ID = "1CTRQdjsgFsRPgRdsT_c_rJheztivNAa1gyTKjxL-QR4"

SECTOR_LOG_SHEET = "sector_log"
MOMENTUM_LOG_SHEET = "momentum_log"

DISCORD_WEBHOOK = "https://discord.com/api/webhooks/1429728811041423401/AzVtazbLgQs3sq-zjSR2knkCIhQMgDPLDgl6z_YY6_fNvJUjpYQXzSpHq_goD2bVldUE"

SECTOR_ORDER = [
    "水産・農林業", "鉱業", "建設業", "食料品", "繊維製品", "パルプ・紙", "化学",
    "医薬品", "石油・石炭製品", "ゴム製品", "ガラス・土石製品", "鉄鋼", "非鉄金属",
    "金属製品", "機械", "電気機器", "輸送用機器", "精密機器", "その他製品", "電気・ガス業",
    "陸運業", "海運業", "空運業", "倉庫・運輸関連業", "情報・通信業", "卸売業", "小売業",
    "銀行業", "証券、商品先物取引業", "保険業", "その他金融業", "不動産業", "サービス業"
]

# ==============================
# Google認証
# ==============================
creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
gc = gspread.authorize(creds)
sh = gc.open_by_key(SPREADSHEET_ID)

# ==============================
# DataFrame取得
# ==============================
def get_sheet_df(sheet_name):
    ws = sh.worksheet(sheet_name)
    data = ws.get_all_values()
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data[1:], columns=data[0])
    return df

# ==============================
# 連続日数計算
# ==============================
def calc_consecutive_days(df, key_col, sort_col, top_n=True):
    """
    df: 日付順にソート済み DataFrame
    key_col: 業種列
    sort_col: 順位・比率列
    top_n: Trueならトップn、Falseならボトムn
    """
    df_sorted = df.sort_values("日付")  # 日付順
    last_date = df_sorted["日付"].max()
    consecutive = {}
    for sector in df_sorted[key_col].unique():
        sector_df = df_sorted[df_sorted[key_col]==sector].sort_values("日付")
        count = 0
        # 行を逆順に
        for _, row in sector_df.iloc[::-1].iterrows():
            if (top_n and row[sort_col] in sector_df[sort_col].nlargest(5).values) or \
               (not top_n and row[sort_col] in sector_df[sort_col].nsmallest(5).values):
                count += 1
            else:
                break
        consecutive[sector] = count
    return consecutive

# ==============================
# Discord送信
# ==============================
def send_discord(message):
    requests.post(DISCORD_WEBHOOK, json={"content": message})

# ==============================
# メイン処理
# ==============================
def main():
    # ===== sector_log =====
    sector_df = get_sheet_df(SECTOR_LOG_SHEET)
    sector_df = sector_df[sector_df["時価総額帯"]=="全体"].copy()

    # 数値化
    for col in ["上昇銘柄数","下落銘柄数","時価総額加重平均騰落率"]:
        sector_df[col] = pd.to_numeric(sector_df[col].str.replace(",",""), errors="coerce")

    # 上昇率
    sector_df["上昇銘柄数率"] = sector_df["上昇銘柄数"] / (sector_df["上昇銘柄数"] + sector_df["下落銘柄数"])

    # 最新日
    latest_date = sector_df["日付"].max()
    latest_sector = sector_df[sector_df["日付"]==latest_date]

    # トップ5／ボトム5
    top5_sector = latest_sector.nlargest(5, "時価総額加重平均騰落率")
    bottom5_sector = latest_sector.nsmallest(5, "時価総額加重平均騰落率")

    # 連続日数
    top5_days = calc_consecutive_days(sector_df, "業種", "時価総額加重平均騰落率", top_n=True)
    bottom5_days = calc_consecutive_days(sector_df, "業種", "時価総額加重平均騰落率", top_n=False)

    # ===== momentum_log =====
    mom_df = get_sheet_df(MOMENTUM_LOG_SHEET)
    for col in ["売買代金5日平均/20日平均比率", "売買代金3日平均/10日平均比率"]:
        mom_df[col] = pd.to_numeric(mom_df[col], errors="coerce")
    latest_mom = mom_df[mom_df["日付"]==latest_date]

    top5_mom = latest_mom.nlargest(5, "売買代金5日平均/20日平均比率")
    bottom5_mom = latest_mom.nsmallest(5, "売買代金5日平均/20日平均比率")

    top5_mom_days = calc_consecutive_days(mom_df, "業種", "売買代金5日平均/20日平均比率", top_n=True)
    bottom5_mom_days = calc_consecutive_days(mom_df, "業種", "売買代金5日平均/20日平均比率", top_n=False)

    # ===== Discordメッセージ作成 =====
    msg = f"📊 {latest_date} モメンタムショートサマリー\n\n"

    # --- 騰落率トップ5 ---
    msg += "```業種別 騰落率トップ5\n"
    msg += "```順位 | 業種 | 上昇率 | 平均騰落率 | 連続日数\n"
    msg += "----------------------------------------------\n"
    for i, (_, row) in enumerate(top5_sector.iterrows(), 1):
        msg += f"{i} | {row['業種']} | {row['上昇銘柄数']}/{row['上昇銘柄数']+row['下落銘柄数']} ({row['上昇銘柄数率']:.2f}) | {row['時価総額加重平均騰落率']:.2f} | {top5_days.get(row['業種'],0)}\n"
    msg += "```\n"

    # --- 騰落率ボトム5 ---
    msg += "```業種別 騰落率ボトム5\n"
    msg += "```順位 | 業種 | 上昇率 | 平均騰落率 | 連続日数\n"
    msg += "----------------------------------------------\n"
    for i, (_, row) in enumerate(bottom5_sector.iterrows(), 1):
        msg += f"{i} | {row['業種']} | {row['上昇銘柄数']}/{row['上昇銘柄数']+row['下落銘柄数']} ({row['上昇銘柄数率']:.2f}) | {row['時価総額加重平均騰落率']:.2f} | {bottom5_days.get(row['業種'],0)}\n"
    msg += "```\n"

    # --- 売買代金5日平均/20日平均 比率トップ5 ---
    msg += "```業種別 売買代金5日平均/20日平均 比率トップ5\n"
    msg += "```順位 | 業種 | 比率 | 連続日数\n"
    msg += "-----------------------------\n"
    for i, (_, row) in enumerate(top5_mom.iterrows(), 1):
        msg += f"{i} | {row['業種']} | {row['売買代金5日平均/20日平均比率']:.2f} | {top5_mom_days.get(row['業種'],0)}\n"
    msg += "```\n"

    # --- 売買代金5日平均/20日平均 比率ボトム5 ---
    msg += "```業種別 売買代金5日平均/20日平均 比率ボトム5\n"
    msg += "```順位 | 業種 | 比率 | 連続日数\n"
    msg += "-----------------------------\n"
    for i, (_, row) in enumerate(bottom5_mom.iterrows(), 1):
        msg += f"{i} | {row['業種']} | {row['売買代金5日平均/20日平均比率']:.2f} | {bottom5_mom_days.get(row['業種'],0)}\n"
    msg += "```\n"

    # ===== 送信 =====
    send_discord(msg)
    print("✅ Discord送信完了")

# ==============================
# 実行
# ==============================
if __name__=="__main__":
    main()