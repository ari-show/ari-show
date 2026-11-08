# Security Policy

## 脆弱性の報告

このリポジトリに関するセキュリティ上の問題を見つけた場合は、公開 Issue ではなく
[Private vulnerability reporting](https://github.com/ari-show/ari-show/security/advisories/new)
から非公開で報告してください。

## このリポジトリで行っている対策

### 依存関係

| 対策 | 内容 |
|---|---|
| Dependabot alerts / security updates | 既知の脆弱性を検知し、修正 PR を自動作成 |
| Dependabot version updates | [`dependabot.yml`](dependabot.yml) で GitHub Actions と `scripts/` (uv) を毎週更新 |
| cooldown | 公開から 7 日未満のバージョンは提案しない (サプライチェーン攻撃対策。security updates は対象外) |
| lockfile | `scripts/uv.lock` を使い、CI では `uv sync --locked` でロックと一致しない場合に失敗させる |

### GitHub Actions

| 対策 | 内容 |
|---|---|
| SHA 固定 | すべての `uses:` をコミット SHA で固定し、`# vX.Y.Z` コメントでバージョンを併記する (タグの書き換え対策)。更新は Dependabot が行う |
| 使用可能なアクションを制限 | GitHub 製 (`actions/*` など) と、下記の許可リストにあるアクションのみ実行可能 |
| 最小権限の `GITHUB_TOKEN` | リポジトリのデフォルトは `read`。各ワークフローで `permissions:` を明示し、必要なものだけ付与する |
| 入力値の扱い | `workflow_dispatch` の入力は `run:` に直接埋め込まず、`env:` 経由で渡す (スクリプトインジェクション対策) |

許可しているサードパーティ製アクション:

| アクション | 用途 | 権限 |
|---|---|---|
| `astral-sh/setup-uv` | Python / uv のセットアップ | `contents: read` / `write` |
| `peter-evans/create-pull-request` | カンファレンス追加 PR の作成 | `contents: write`, `pull-requests: write` |
| `Platane/snk` | contribution snake の生成 (Docker イメージは digest 固定) | `contents: write` |
| `crazy-max/ghaction-github-pages` | snake SVG を `output` ブランチへ push | `contents: write` |

新しいアクションを使うときは次の手順を守ってください。

1. ソースを確認し、内部でさらに別のアクションを呼んでいないかを見る
2. コミット SHA で固定して追加する
3. Settings → Actions → General → "Allow ... actions" の許可リストに追加し、この表を更新する

### リポジトリ

| 対策 | 内容 |
|---|---|
| Secret scanning / push protection | シークレットの混入を検知し、push 時にブロック |
| `main` のルールセット (`protect-main`) | ブランチの削除と force push を禁止 |
