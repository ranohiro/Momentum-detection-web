# 📈 Momentum Detector

**東証33業種のモメンタム（資金流入の初動）を自動解析し、結果をGoogleスプレッドシートおよびDiscordに送信するシステムです。**
株価データを取得 → 集計 → シート更新 → サマリー送信までをGitHub Actionsで自動実行します。

---

## 🚀 プロジェクト概要

| フェーズ | 概要 |
|-----------|------|
| **1. データ収集・加工** | 株式情報サイト（kabu.plus）から業種別データを取得・加工し、`processed_data`配下に保存。 |
| **2. スプレッドシート更新** | 加工済みCSVをGoogleスプレッドシート（`sector_log` / `momentum_log`）にアップロード。 |
| **3. 可視化生成** | シート内容をもとに、業種別の騰落率・売買代金比率を整形し可視化用データを生成。 |
| **4. サマリー通知** | 最新データをもとに業種別ランキングをDiscordへ自動送信。 |
| **5. 定期実行** | GitHub Actions (`run.yml`) により、毎日17:00（JST）に自動実行。 |

---

## 📂 ディレクトリ構成

```
momentum-detector/
├── main.py                        　　　　# 全体の実行制御
├── 1-csv_downloader_individuals_v01.py   # KABU＋からデータ取得
├── 2-csv_summary_creator_v01.py          # KABU＋からデータ取得
├── 3-data_processor_v02.py               # データの前処理・集計
├── 4-google_sheets_uploader_v02.py       # GoogleスプレッドシートへCSVアップロード
├── 5-momentum_analyzer_v02.py      　　　 # 業種別モメンタム分析とランキング生成
├── 6-summary_sender_v01.py               # Discordへ日次サマリー通知
├── requirements.txt                      # 依存ライブラリ
├── run.yml                               # GitHub Actions設定（自動実行）
data/
│    ├─ raw/
│    │   ├─ japan_all_stock/
│    │   └─ tosho_index/
│    └─ processed_data/
│        ├─ sector_summary/               # セクター別集計CSV格納
│        └─ momentum_summary/             # モメンタム分析用CSV格納
└── credentials.json                # GCP認証情報（Secrets経由で生成）
```

---

## ⚙️ 各スクリプトの役割

### 1. csv_downloader_individuals_v01.py
- 各銘柄の株価データを、「KABU +(https://kabu.plus)」より取得
- 出力先：`data/raw/` 以下に日付付きで保存
- 使用ライブラリ：`requests`, `pandas`, `urllib3`

---

### 2. csv_downloader_index_v01.py
- ダウンロード済みの個別株データを集計
- 各業種や市場別に平均上昇率・出来高変化率を算出
- 出力：`YYMMDD_sector_summary.csv`, `YYMMDD_momentum_summary.csv`

---

### 3. data_processor_v01.py
- 業種名統一化
- 業種別・時価総額帯別に集計、モメンタム指標を計算

---

### 4. google_sheets_uploader_v02.py
- 集計結果CSVをGoogle Sheetsへ自動アップロード
- 出力：`momentum_log` や `sector_log` へデータ蓄積

---

### 5. momentum_analyzer_v03.py
- 銘柄やセクター単位での売買代金比からモメンタムの経時変化ログをとる
- 騰落率の経時変化ログをとる
- 出力：`momentum_flow` や `sector_ranking` へ結果転記

---

### 6. summary_sender_v01.py
- Discordに「本日の相場 ショートサマリー」を送信

---

## 🧩 使用ライブラリ

`requirements.txt` に以下が含まれます。
requests
urllib3
pandas
numpy
schedule
gspread
jpholiday
google-auth
google-auth-oauthlib
google-auth-httplib2

---

## 🔐 Google連携設定

1. Google Cloud Consoleでサービスアカウントを作成
2. スプレッドシートを該当アカウントのメールアドレスに共有
3. 認証情報（`credentials.json`）をリポジトリの安全な場所に配置
4. `google_sheets_uploader.py` で読み込みパスを設定

---

## ⚡ 自動実行 (GitHub Actions)

`.github/workflows/main.yml` を用いて、毎営業日の決まった時間に実行。

```yaml
on:
  schedule:
    - cron: '0 8 * * *'   # UTC 8:00 = JST 17:00
  workflow_dispatch:
```

---

### ライセンス
MIT License

**Copyright (c) 2025 Takahiro Hirano**

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

---

## 🧾 Version History

| Version | Date | Notes |
|----------|------|-------|
| 1.0.0 | 2025-11-03 | 初回公開版（自動データ取得・シート出力・Discord通知対応） |
