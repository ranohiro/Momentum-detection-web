import os
import subprocess
import datetime

# === 設定 ===
LOG_DIR = "logs"
SCRIPTS = [
    "1-csv_downloader_individuals_v01.py",
    "2-csv_downloader_index_v01.py",
    "3-data_processor_v01.py",
    "4-google_sheets_uploader_v02.py",
    "5-momentum_analyzer_v02.py",
    "6-summary_sender_v01.py"
]

# === ログディレクトリ作成 ===
os.makedirs(LOG_DIR, exist_ok=True)


def run_script(script_name):
    """指定スクリプトをサブプロセスで実行し、ログを残す"""
    timestamp = datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S")
    log_path = os.path.join(LOG_DIR, f"main_log_{datetime.date.today()}.txt")

    with open(log_path, "a", encoding="utf-8") as log_file:
        log_file.write(f"\n[{timestamp}] === {script_name} 実行開始 ===\n")
        try:
            result = subprocess.run(
                ["python", script_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True
            )
            log_file.write(result.stdout)
            log_file.write(f"\n[{timestamp}] === {script_name} 実行完了 ===\n")
        except subprocess.CalledProcessError as e:
            log_file.write(f"\n[ERROR] {script_name} 実行中にエラー:\n{e.stderr}\n")
            print(f"❌ {script_name} 実行中にエラーが発生しました。ログを確認してください。")
            raise e


def run_all_scripts():
    """全スクリプトを順に実行"""
    print("=== モメンタム検知処理開始 ===")
    for script in SCRIPTS:
        print(f"▶ {script} 実行中...")
        run_script(script)
    print("=== 全処理完了 ===")


if __name__ == "__main__":
    run_all_scripts()