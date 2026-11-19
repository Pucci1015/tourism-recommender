# 観光地推薦システム

旅行のコンセプト（例：「満天の星空をただ静かに眺めたい」）を入力すると、日本全国の観光エリアから合うものを推薦する Web アプリです。
**分散表現（SBERT）による類似度ランキング** と **LLM（Gemini）によるランキング** の 2 手法の結果を並べて表示し、アンケートで比較評価できます。

## 主な機能

- **コンセプト検索** — 自由入力、またはカテゴリ別のコンセプト一覧から選択
- **2 手法の比較表示**
  - SBERT：コンセプトとエリア概要文・スポット概要文のコサイン類似度でランキング
  - LLM：SBERT で絞り込んだ候補 20 件から、Gemini が上位 5 件と推薦理由を生成
- **アンケート** — 2 手法のどちらが良かったかを回答・集計（CSV 出力あり）
- **DB ブラウザ** — 都道府県 → エリア → スポットの順にデータを閲覧

## 推薦の仕組み

```
コンセプト
   │  SBERT でベクトル化
   ▼
全エリアのスコアを計算
   score = α × (エリア概要文との類似度) + (1 − α) × (上位 3 スポットの類似度平均)
   （α = 0.4、概要文は文単位でベクトル化し最大類似度を採用）
   │
   ├─▶ 上位 5 件 ─────────────▶ 分散表現の結果
   │
   └─▶ 上位 20 件を Gemini に渡す ─▶ LLM の結果（理由・おすすめスポット付き）
```

## 技術スタック

| 分類 | 使用技術 |
| --- | --- |
| 言語 | Python 3.12 |
| Web | Flask, Jinja2, HTML / CSS / JavaScript |
| 埋め込みモデル | [sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2) |
| LLM | Google Gemini（`google-genai`） |
| DB | SQLite |
| データ収集 | requests, BeautifulSoup |

## セットアップ

### 1. リポジトリの取得と依存パッケージのインストール

```bash
git clone https://github.com/<your-name>/<repo-name>.git
cd <repo-name>

python3.12 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. API キーの設定

```bash
cp .env.example .env
```

`.env` の `GEMINI_API_KEY` に [Google AI Studio](https://aistudio.google.com/) で取得したキーを設定してください。
管理者ページを使う場合は `ADMIN_USER` / `ADMIN_PASSWORD` も設定してください（下記「管理者ページ」参照）。

### 3. データベースの作成

データベース（`tourism.sqlite`）はリポジトリに含めていません。以下の手順で作成します。

```bash
python build_db.py         # 観光エリア・スポット情報を収集してベクトル化（areas / spots テーブル）
python load_concepts.py    # concepts.json からコンセプト一覧を登録（categories / concepts テーブル）
```

> **注意**
> - `build_db.py` は既存の `areas` / `spots` テーブルを削除してから作り直します。
> - 全 47 都道府県分の収集には長時間かかります（アクセスごとに 1 秒待機）。
> - 収集元サイトの利用規約を確認のうえ、負荷をかけないよう個人の研究・学習目的の範囲で利用してください。

### 4. 起動

```bash
flask --app app run
# または python app.py
```

ブラウザで http://127.0.0.1:5000 を開きます。初回起動時は SBERT モデルのダウンロードと全データの読み込みに時間がかかります。

## ページ一覧

| URL | 内容 |
| --- | --- |
| `/` | トップ（コンセプト入力） |
| `/categories` | カテゴリ一覧 |
| `/concepts?category_id=<id>` | カテゴリ内のコンセプト一覧 |
| `/result?concept=<text>` | 推薦結果（SBERT / LLM の比較） |
| `/survey` | アンケート |
| `/survey/result` | アンケート集計（管理者） |
| `/survey/result/csv` | アンケート回答の CSV ダウンロード（管理者） |
| `/db` | DB ブラウザ（管理者） |

### 管理者ページ

`/db`（DB ブラウザ、`/db/api/*` を含む）と `/survey/result`（アンケート集計・CSV）は管理者専用で、Basic 認証がかかっています。
`.env` の `ADMIN_USER`（省略時は `admin`）と `ADMIN_PASSWORD` でログインします。`ADMIN_PASSWORD` が未設定の場合は、誰もアクセスできません（403）。

> Basic 認証はパスワードを暗号化せずに送るため、外部に公開するサーバで動かす場合は HTTPS を使ってください。

## ディレクトリ構成

```
.
├── app.py              # Flask アプリ（ルーティング・管理者認証・アンケート保存/集計）
├── recommender.py      # 推薦処理のエントリポイント（SBERT → LLM）
├── areas.py            # DB 読み込みとエリア/スポットの類似度計算
├── sbert_ranking.py    # SBERT による類似度ランキング
├── llm_ranking.py      # Gemini によるランキング生成
├── sbert_model.py      # SBERT モデルの共通設定
├── build_db.py         # 観光データの収集・ベクトル化（DB 作成）
├── load_concepts.py    # コンセプト一覧の DB 登録
├── concepts.json       # カテゴリ別のコンセプト定義
├── templates/          # Jinja2 テンプレート
├── static/             # CSS / JavaScript
├── requirements.txt
└── .env.example
```

## 主なパラメータ

| ファイル | 定数 | 既定値 | 内容 |
| --- | --- | --- | --- |
| `areas.py` | `ALPHA` | 0.4 | エリアスコアにおけるエリア概要文の重み |
| `areas.py` | `TOP_K_SPOTS` | 3 | エリアスコア計算に使う上位スポット数 |
| `recommender.py` | `TOP_K_AREAS` | 5 | 表示する件数 |
| `recommender.py` | `CANDIDATE_K` | 20 | LLM に渡す候補エリア数 |
| `llm_ranking.py` | `LLM_MODEL` | `gemini-3.1-flash-lite` | 使用する Gemini モデル |
