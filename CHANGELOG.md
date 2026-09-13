# Changelog

このプロジェクトの変更履歴。形式は Keep a Changelog、バージョンは SemVer。

## [0.2.0] - 2026-09-13

### Added
- 第八十八大海丸を追加。`source: html` アダプタ（1ページに和暦見出しで羅列された釣果を `block_pattern` で分割）
- `link_only: true` の船をアプリ下部に外部リンクとして表示（高栄丸・春定丸）

### Changed
- 高栄丸・春定丸は zekkouchou.com が robots.txt で自動取得を禁止しているため、パーサ実装を取りやめリンクのみに変更

## [0.1.1] - 2026-09-13

### Changed
- GitHub Actions を checkout@v5 / setup-python@v6 に更新（Node.js 20 非推奨警告の解消）
- 釣果報告でないと判定してスキップした記事のタイトル・URLを `skipped` に記録（直近50件）。後から判定の妥当性を確認できるようにした

### Verified
- 初回本番実行：7隻すべて取得成功、55件抽出、9件スキップ。泰丸の3船分離が動作。小川さんの目視で釣果が元記事と一致

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
- 匹数推移グラフ → 0.3.0 予定
