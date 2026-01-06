import os
import time
from datetime import datetime, timedelta

def cleanup_old_files(base_dir, days_to_keep):
    """
    指定日数より古いファイルを削除する関数
    """
    now = time.time()
    cutoff = now - (days_to_keep * 86400)

    for root, _, files in os.walk(base_dir):
        for file in files:
            file_path = os.path.join(root, file)
            if os.path.isfile(file_path):
                if os.path.getmtime(file_path) < cutoff:
                    os.remove(file_path)
                    print(f"[削除] {file_path}")

def run_cleanup():
    """
    各フォルダごとに削除条件を設定
    """
    base_dirs = {
        "data/raw": 30,       # 30日より古いデータを削除
        "data/processed": 30, # 同上
        "logs": 10            # 10日より古いログを削除
    }

    print(f"\n=== 古いデータ削除開始 ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) ===")
    for path, days in base_dirs.items():
        if os.path.exists(path):
            cleanup_old_files(path, days)
        else:
            print(f"[スキップ] フォルダが存在しません: {path}")
    print("=== 古いデータ削除完了 ===\n")


if __name__ == "__main__":
    run_cleanup()