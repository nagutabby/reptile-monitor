# reptile-monitor

ヒョウモントカゲモドキケージの温湿度可視化 + 異常値LINE通知アプリ。

## 構成

- `backend/`: FastAPI。M5Stack(`atoms3-reptile-cage`)からのレポートを受信し、Cloudflare D1に保存、異常値ならLINEに通知する。Renderにデプロイする。
- `frontend/`: Streamlit。FastAPIの`GET /api/readings`を叩いて温度・湿度の推移を可視化する。Streamlit Community Cloudにデプロイする。
- `schema.sql`: D1の初期スキーマ(`readings`, `alert_state`)。

データはCloudflare D1(SQLite互換のサーバーレスDB)に集約されるため、backend/frontendのどちらも状態を持たない(永続ディスク不要)。

## セットアップ

### 1. Cloudflare D1

```sh
npx wrangler login
npx wrangler d1 create reptile-monitor
npx wrangler d1 execute reptile-monitor --remote --file=schema.sql
```

作成後に表示される `database_id` と、Cloudflareダッシュボードで確認できる `account_id` を後述の`.env`に設定する。`CLOUDFLARE_API_TOKEN` はD1の編集権限を持つAPIトークンを [My Profile > API Tokens](https://dash.cloudflare.com/profile/api-tokens) で発行する。

### 2. LINE Messaging API

既存のMessaging APIチャンネルの「チャンネルアクセストークン(長期)」を発行し、通知先(自分のuserId、または作成したグループのgroupId)を確認しておく。

### 3. バックエンド (ローカル起動)

```sh
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # 値を入力する
uvicorn app.main:app --reload
```

動作確認:

```sh
curl -X POST http://localhost:8000/api/readings \
  -H "X-API-Key: <API_KEY>" -H "Content-Type: application/json" \
  -d '{"temp_c": 25.0, "humidity": 30}'

curl http://localhost:8000/api/readings -H "X-API-Key: <API_KEY>"
```

`backend/app/config.py` のしきい値(温度24-30℃、湿度40-90%)外の値を送ると、LINEに通知が届くことを確認する。異常値判定のしきい値は機密情報ではないため`.env`ではなく`config.py`の定数として管理している。

### 4. テスト (異常値判定・再通知抑制の回帰テスト)

```sh
cd backend
pip install -r requirements-dev.txt
pytest
```

D1・LINEへは実際に接続せず、`alerts.evaluate_and_notify`の状態遷移(正常→異常/異常継続時の再通知抑制/異常→正常)とAPIの認証をテストする。

### 5. フロントエンド (ローカル起動)

```sh
cd frontend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml  # 値を入力する
streamlit run app.py
```

### 6. デプロイ

- **Render**: Renderダッシュボードで「New > Blueprint」からこのリポジトリを接続し、`render.yaml`を検出させる。`sync: false`の環境変数(APIキー・Cloudflare・LINE関連)をダッシュボード上で入力する。
- **Streamlit Community Cloud**: [share.streamlit.io](https://share.streamlit.io) でリポジトリ・`frontend/app.py`を指定してデプロイする。Settings > Secrets に `secrets.toml.example` と同じ内容(実際の値)を貼り付ける。
- デプロイ後、Render側の公開URLを `atoms3-reptile-cage/include/wifi_config.h` の `API_ENDPOINT_URL` に設定し、ファームウェアを書き込む。
