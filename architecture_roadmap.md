# 🏗 Momentum Detector: Backend Migration Roadmap

現在の「ローカルCSV + Streamlit」構成から、Webアプリ（Next.jsなど）やiOSアプリに対応した「本格的なクライアント/サーバー構成」へ移行するためのロードマップです。

## 🎯 目指す全体像 (Future Architecture)

```mermaid
graph LR
    subgraph "Data Pipeline (Batch)"
        A[KABU+ Data Source] -->|Download| B[Python Batch Process]
        B -->|Insert/Update| C[(Cloud Database)]
    end

    subgraph "Backend API"
        C -->|Query| D[API Server (FastAPI)]
        D -->|JSON| E{Clients}
    end

    subgraph "Frontend Clients"
        E -->|HTTPS| F[Web App (React/Next.js)]
        E -->|HTTPS| G[iOS App (Swift)]
    end
```

---

## 📅 具体的なステップ

### Phase 1: データベース化 (Data Layer)
現在のCSVファイル管理から、リレーショナルデータベース（RDB）へ移行します。アプリからの検索やフィルタリングを高速化するためです。

1.  **DB選定**: **PostgreSQL** が推奨です（AWS RDS, Google Cloud SQL, Supabaseなど）。
2.  **スキーマ設計**:
    *   `stocks` テーブル (銘柄コード, 銘柄名, セクター...)
    *   `daily_prices` テーブル (銘柄コード, 日付, 始値, 高値, 安値, 終値, 売買代金...)
    *   `sector_momentum` テーブル (セクター名, 日付, モメンタムスコア...)
3.  **移行スクリプト作成**: 現在のCSVデータを読み込み、SQLへINSERTするPythonスクリプトを作成します。
4.  **バッチ処理の修正**: `processed_data/*.csv` を保存する代わりに、DBへ `UPSERT` (更新) するように変更します。

### Phase 2: APIサーバー構築 (Backend Layer)
データを配信するための窓口（API）を作成します。Python資産を活かせる **FastAPI** が最適です。

1.  **フレームワーク**: FastAPI (Python) を使用。
2.  **エンドポイント作成**:
    *   `GET /api/v1/sectors`: セクター一覧と現在のモメンタムを返す。
    *   `GET /api/v1/sectors/{sector_id}/history`: 特定セクターの時系列データを返す（チャート用）。
    *   `GET /api/v1/stocks?sector=ElectricAppliances`: 条件に合う個別銘柄リストを返す（ページネーション付き）。
3.  **レスポンス形式**: JSON形式で統一します。

### Phase 3: クラウドデプロイ (Infrastructure)
手動実行ではなく、常時稼働するサーバーに配置します。

*   **PaaS (推奨・簡単)**: **Render**, **Railway**, **Heroku** など。
    *   GitHubと連携し、Pushするだけでデプロイ可能。
    *   データベース（PostgreSQL）もセットで提供されていることが多い。
*   **IaaS (本格的)**: AWS (EC2/RDS), GCP (Cloud Run/Cloud SQL)。
    *   拡張性は高いが設定が複雑。まずはPaaSから始めるのが近道です。

### Phase 4: フロントエンド開発 (Client Layer)
APIができれば、どんなアプリでも作れるようになります。

*   **Web**: Next.js (React) + Tailwind CSS
*   **iOS**: SwiftUI (AlamofireなどでAPIを叩く)

---

## 🛠 推奨構成セット (Start Small)

まずは小さく始めるための推奨セットです。

| レイヤー | 技術 | 理由 |
|Data| **Supabase** (PostgreSQL) | 無料枠が大きく、管理画面が使いやすい。APIも自動生成される機能があるが、カスタムロジック用に自作APIを推奨。 |
|Backend| **FastAPI** on **Render** | Pythonの高速なAPIフレームワーク。Renderは無料/安価にホスティング可能。 |
|Batch| **GitHub Actions** | 現在のまま利用可能。接続先をCSV保存から「APIを叩く」または「DBへ直接接続」に変更。 |

## 📝 Next Action

まずは **「Phase 1: データベース化」** から始めるのが良いでしょう。
現在の `data_processor.py` の出力を、ローカルのCSVではなく、ローカルに立てたPostgreSQLに保存するところから実験してみますか？
