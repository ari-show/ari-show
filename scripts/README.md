# scripts

`data/conferences.yml` を唯一の正として、README の Conferences セクションを生成・追加するスクリプト群です。
uv プロジェクトとして環境を固定しています (Python は `.python-version`、依存は `uv.lock`)。

## 使い方

```bash
cd scripts
uv sync                                  # 初回。.venv を作って依存を入れる

uv run add_conference.py                 # 対話形式で1件追加 (--pr で PR 作成まで)
uv run build_readme.py                   # YAML から README を再生成
uv run build_readme.py --check           # ずれていないか確認 (CI と同じ)
```

リポジトリルートから実行する場合は `uv run --project scripts scripts/build_readme.py` のように `--project scripts` を付けます。

## 開発

```bash
uv run ruff check . && uv run ruff format --check .   # lint / format
uv run pytest                                          # テスト
```

| ファイル | 役割 |
|---|---|
| `conferences_lib.py` | YAML の読み書き・検証、表の HTML 生成 |
| `build_readme.py` | README のマーカー区間を再生成する CLI |
| `add_conference.py` | 質問に答えて1件追加する CLI。`--yes` で非対話 (Actions が使う) |
| `tests/` | pytest |
