# 📈 Momentum Detector Dashboard

**東証33業種のモメンタム（資金流入の初動）を可視化し、セクターローテーションを迅速に検知するためのWebアプリケーションです。**

GitHub Actionsによる自動データ収集・集計と、Streamlitによるインタラクティブな分析ダッシュボードを提供します。

![Momentum Trends Heatmap](/Users/hiranotakahiro/.gemini/antigravity/brain/bf56c54a-9e04-41ce-a87a-309bdfe37a10/momentum_trends_heatmap_1768185423153.png)

---

## 🚀 主な機能

### 1. Momentum Trends (メイン画面)
資金流入のトレンドを時系列で可視化します。
- **ヒートマップ**: 「売買代金5日平均 / 20日平均比率」または「対TOPIX相対モメンタム」を色分け表示（赤＝強、青＝弱）。
- **インタラクティブチャート**: ヒートマップ上のセクターをクリックすると、詳細チャート（ローソク足 + SMA + 売買代金 + ベンチマーク比較）が表示されます。
- **個別銘柄リスト**: 選択したセクターに含まれる銘柄のリスト（騰落率、売買代金平均）を表示し、ソートやフィルタリングが可能です。

### 2. データ検証・管理
- **Data Verification**: セクター別およびモメンタム指標の集計済み生データを確認できます。
- **Data Management**: データの更新状況の確認、ログ閲覧、手動更新トリガーが可能です。

### 3. 自動運用 (Backend)
- 毎日17:00 (JST) にGitHub Actionsが起動し、最新の株価データを取得・集計・CSV保存します。

---

## 🛠 技術スタック

- **Frontend**: Streamlit, Altair (Visualization)
- **Backend (Data Pipeline)**: Python (Pandas, Requests)
- **Data Storage**: CSV (Local File System / Git LFS)
- **Automation**: GitHub Actions

---

## 📂 ディレクトリ構成

```
momentum-detector/
├── app.py                            # Streamlit Webアプリケーション
├── main.py                           # データ更新パイプラインの制御
├── 3-data_processor_v01.py           # データ集計・加工・モメンタム計算
├── ... (その他のスクリプト)
├── data/
│    ├─ raw/                          # 生データ (Git LFS)
│    └─ processed_data/               # アプリ用加工済みデータ
│        ├─ stock_list/               # 個別銘柄リスト (日次CSV)
│        ├─ momentum_summary/         # モメンタム時系列データ
│        └─ indices/                  # 合成セクター指数データ
└── .github/workflows/run.yml         # 自動実行定義
```

---

## 💻 セットアップと実行

### 必要条件
- Python 3.9+

### インストール

```bash
git clone https://github.com/ranohiro/Momentum-detection-web.git
cd Momentum-detection-web
pip install -r requirements.txt
```

### アプリケーションの起動

```bash
streamlit run app.py
```
ブラウザで `http://localhost:8501` が開きます。

---

## 🧾 Version History

| Version | Date | Notes |
|----------|------|-------|
| **2.0.0** | 2026-01-12 | **Web Dashboard (Streamlit) リリース**<br>- モメンタムヒートマップ<br>- インタラクティブチャート<br>- 個別銘柄リスト (Stock Detail)<br>- UI再構成 (Navigation) |
| 1.0.0 | 2025-11-03 | 初回公開版（自動データ取得・シート出力・Discord通知対応） |

---

### ライセンス
MIT License
Copyright (c) 2025 Takahiro Hirano
