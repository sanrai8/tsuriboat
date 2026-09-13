# tsuriboat — 若狭釣果まとめ

福井（敦賀・小浜）と京都北部の釣り船の釣果ブログを毎朝まとめて取得し、
Claude で「釣行日・魚種・匹数」を抽出して一覧表示するスマホ向け PWA。

- 表示: GitHub Pages（`docs/`）
- 取得: GitHub Actions（毎朝 06:00 JST）→ `docs/data/catches.json` を更新

## 初回セットアップ

1. リポジトリ `sanrai8/tsuriboat` を作成し、このディレクトリの中身を push
2. **Settings → Secrets and variables → Actions** に `ANTHROPIC_API_KEY` を登録
3. **Settings → Pages** で Source を `main` / `/docs` に設定
4. **Actions → 釣果取得（毎朝） → Run workflow** で手動実行し、ログで各船の取得件数を確認
5. スマホで `https://sanrai8.github.io/tsuriboat/` を開き「ホーム画面に追加」

## ローカルで確認

```bash
pip install -r scraper/requirements.txt
python scraper/fetch.py --dry-run          # 新着記事の一覧だけ（API 不要）
ANTHROPIC_API_KEY=... python scraper/fetch.py --boat kazumimaru
cd docs && python -m http.server 8000      # http://localhost:8000
```

## 船を追加する

`boats.yaml` にブロックを追加するだけ。`source` は `ameba` / `fc2` / `wordpress` / `html`。自動取得しない船は `link_only: true` で登録するとリンクだけ表示される。

取得前にそのサイトの robots.txt を確認し、禁止されている場合は `link_only` にする。

## 構成

```
boats.yaml                  船の設定
scraper/fetch.py            取得・抽出
.github/workflows/daily.yml 定期実行
docs/                       PWA（Pages 公開）
docs/data/catches.json      抽出結果（bot がコミット）
CHANGELOG.md
```
