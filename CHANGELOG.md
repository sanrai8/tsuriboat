# Changelog

このプロジェクトの変更履歴。形式は Keep a Changelog、バージョンは SemVer。

## [0.1.0] - 2026-09-12

初版。RSS で取れる船だけで「取得 → Claude 抽出 → JSON → PWA 表示」を一気通貫で動かす骨組み。

### Added
- `boats.yaml`：船ごとの取得先設定（10隻登録、うち7隻を有効化）
- `scraper/fetch.py`：RSS アダプタ（Ameba / FC2 / WordPress）、Claude Haiku による釣果抽出、`docs/data/catches.json` への追記
  - 泰丸は「泰丸 / Second / Action's」の3船を記事から判別して分離
  - 雲丸は公式サイトではなく Ameba ブログ（fcloud）の RSS を使用
  - 釣果報告でない記事（出船案内等）は `skipped_ids` に記録して再抽出しない
  - `--dry-run`（API 未使用で新着確認）、`--boat <id>`（1隻だけ）オプション
- `.github/workflows/daily.yml`：毎朝 06:00 JST に実行し、変更があれば自動コミット
- `docs/`：PWA（エリア・魚種フィルタ、船ごとの最新、日別一覧、竿頭に比例した光柱表示）
- `docs/data/catches.json`：表示確認用サンプル（`"sample": true`。初回の本番実行で破棄される）

### Not yet
- zekkouchou（高栄丸・春定丸）、大海丸の HTML アダプタ → 0.2.0 予定
- 匹数推移グラフ → 0.2.0 予定
- RSS URL（泰丸の `/fishingpost/feed/`、Ameba の `rssblog.ameba.jp`）は初回実行で疎通確認が必要
