#!/usr/bin/env python3
import os
import sys
import subprocess
import datetime
import logging
from dotenv import load_dotenv

load_dotenv()
import argparse
import time
import requests
try:
    import jpholiday
except ImportError:
    jpholiday = None
from cleanup_old_data import run_cleanup

run_cleanup()

# ==============================
# 設定（必要なら変更）
# ==============================
ROOT_DIR = os.path.abspath(os.path.dirname(__file__))
LOG_DIR = os.path.join(ROOT_DIR, "logs")
SCRIPTS = [
    "1-csv_downloader_individuals_v01.py",
    "2-csv_downloader_index_v01.py",
    "3-data_processor_v01.py",
    # "4-google_sheets_uploader_v02.py", # Removed for Streamlit
    # "5-momentum_analyzer_v03.py",
    # "6-summary_sender_v01.py"
]
DEFAULT_TIMEOUT = 600

os.makedirs(LOG_DIR, exist_ok=True)

# ==============================
# ロギング設定
# ==============================
today_str = datetime.date.today().strftime("%Y%m%d")
log_file_path = os.path.join(LOG_DIR, f"main_log_{today_str}.txt")

logger = logging.getLogger("main")
logger.setLevel(logging.INFO)
fmt = logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s", "%Y/%m/%d %H:%M:%S")

sh = logging.StreamHandler(sys.stdout)
sh.setFormatter(fmt)
logger.addHandler(sh)

fh = logging.FileHandler(log_file_path, encoding="utf-8")
fh.setFormatter(fmt)
logger.addHandler(fh)

# ==============================
# Discord 通知
# ==============================
DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK")
def notify_discord(msg: str):
    if not DISCORD_WEBHOOK:
        return
    try:
        requests.post(DISCORD_WEBHOOK, json={"content": msg}, timeout=10)
    except Exception as e:
        logger.warning(f"Discord通知に失敗: {e}")

# ==============================
# 実行ユーティリティ
# ==============================
def run_script(script_name: str, timeout: int = DEFAULT_TIMEOUT):
    script_path = os.path.join(ROOT_DIR, script_name)
    if not os.path.exists(script_path):
        raise FileNotFoundError(f"{script_path} does not exist")

    cmd = [sys.executable, script_path]
    start = datetime.datetime.now()
    logger.info(f"START {script_name}")
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout)
        if proc.stdout:
            for line in proc.stdout.splitlines():
                logger.info(f"[{script_name}] {line}")
        if proc.stderr:
            for line in proc.stderr.splitlines():
                logger.error(f"[{script_name}][ERR] {line}")
        if proc.returncode != 0:
            raise subprocess.CalledProcessError(proc.returncode, cmd)
        elapsed = (datetime.datetime.now() - start).total_seconds()
        logger.info(f"END {script_name} (elapsed {elapsed:.1f}s)")
        return True
    except Exception as e:
        logger.exception(f"Error running {script_name}: {e}")
        return False

# ==============================
# 実行スキップ判定（土日祝）
# ==============================
def is_holiday_or_weekend(date: datetime.date) -> bool:
    if date.weekday() >= 5:  # 5=土, 6=日
        return True
    if jpholiday and jpholiday.is_holiday(date):
        return True
    return False

# ==============================
# メイン処理
# ==============================
def run_pipeline(continue_on_error=False):
    """
    StreamlitやCLIから呼び出せるデータ更新パイプライン
    """
    today = datetime.date.today()
    # 休場日チェックは呼び出し元で行うか、ここで行うか。
    # Streamlitで強制実行ボタンがある場合、チェックをスキップしたいかもしれないが、
    # 基本的にはデータが無いのでスキップでよいか、あるいは「強制」オプションをつけるか。
    # いったん既存ロジックを踏襲。
    if is_holiday_or_weekend(today):
        msg = f"⏭️ {today} は休場日（土日祝）のためスキップしました。"
        logger.info(msg)
        # notify_discord(msg) # Streamlit主体なら通知は必須ではないが残してもよい
        return msg

    overall_ok = True
    for script in SCRIPTS:
        ok = run_script(script)
        if not ok:
            overall_ok = False
            if not continue_on_error:
                break

    if overall_ok:
        msg = f"✅ Momentum run succeeded: {datetime.datetime.now().isoformat()}"
        notify_discord(msg)
        return msg
    else:
        msg = f"❌ Momentum run FAILED: {datetime.datetime.now().isoformat()}"
        notify_discord(msg)
        raise Exception(msg)

def main(continue_on_error=False):
    try:
        run_pipeline(continue_on_error)
        return 0
    except Exception as e:
        logger.error(str(e))
        return 2

# ==============================
# CLI 起動
# ==============================
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--continue-on-error", action="store_true")
    args = parser.parse_args()

    if os.environ.get("GITHUB_ACTIONS") or args.once:
        sys.exit(main(continue_on_error=args.continue_on_error))

    try:
        import schedule
        logger.info("Starting local scheduler (daily at 17:00). Use Ctrl+C to stop.")
        schedule.every().day.at("17:00").do(lambda: main(continue_on_error=args.continue_on_error))
        while True:
            schedule.run_pending()
            time.sleep(30)
    except KeyboardInterrupt:
        logger.info("Interrupted by user. Exiting.")
        sys.exit(0)