"""
tsuriboat scraper v0.1.0

boats.yaml に登録された船の釣果記事を取得し、Claude で構造化して
docs/data/catches.json に追記する。GitHub Actions から毎朝実行される想定。

使い方:
  ANTHROPIC_API_KEY=... python scraper/fetch.py
  python scraper/fetch.py --dry-run        # API を呼ばず記事一覧だけ確認
  python scraper/fetch.py --boat kazumimaru # 1隻だけ

環境変数:
  ANTHROPIC_API_KEY  必須（--dry-run 時は不要）
  MODEL              既定 claude-haiku-4-5-20251001
  LOOKBACK_DAYS      何日前までの記事を対象にするか。既定 14
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import feedparser
import requests
import yaml
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
BOATS_YAML = ROOT / "boats.yaml"
OUT_JSON = ROOT / "docs" / "data" / "catches.json"

JST = timezone(timedelta(hours=9))
UA = "tsuriboat/0.1 (+https://github.com/sanrai8/tsuriboat)"
MODEL = os.environ.get("MODEL", "claude-haiku-4-5-20251001")
LOOKBACK_DAYS = int(os.environ.get("LOOKBACK_DAYS", "14"))


# ---------------------------------------------------------------- utilities

def log(msg: str) -> None:
    print(f"[{datetime.now(JST):%H:%M:%S}] {msg}", flush=True)


def entry_id(url: str) -> str:
    return hashlib.sha1(url.encode()).hexdigest()[:12]


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html or "", "html.parser")
    for t in soup(["script", "style", "nav", "header", "footer", "aside"]):
        t.decompose()
    text = soup.get_text("\n")
    text = re.sub(r"[ \t\u3000]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def fetch_page_text(url: str) -> str:
    """RSS 本文が短い場合に記事ページ本体を取りに行く。"""
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=20)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        # 記事本文らしき領域を優先。無ければ全体。
        for sel in ["article", ".entry-content", ".skin-entryBody", ".entry_body",
                    "#entry_body", ".post-content", "main"]:
            node = soup.select_one(sel)
            if node and len(node.get_text(strip=True)) > 80:
                return html_to_text(str(node))
        return html_to_text(r.text)
    except Exception as e:  # noqa: BLE001
        log(f"  本文取得失敗 {url}: {e}")
        return ""


# ---------------------------------------------------------------- adapters
# 各アダプタは list[dict(title, link, published(datetime|None), content)] を返す

def _parse_feed(url: str) -> list[dict]:
    r = requests.get(url, headers={"User-Agent": UA}, timeout=20)
    if r.status_code == 404:
        raise FileNotFoundError(url)
    r.raise_for_status()
    fp = feedparser.parse(r.content)
    out = []
    for e in fp.entries:
        content = ""
        if getattr(e, "content", None):
            content = e.content[0].get("value", "")
        elif getattr(e, "summary", None):
            content = e.summary
        published = None
        for key in ("published_parsed", "updated_parsed"):
            if getattr(e, key, None):
                published = datetime(*getattr(e, key)[:6], tzinfo=timezone.utc).astimezone(JST)
                break
        out.append({
            "title": getattr(e, "title", "").strip(),
            "link": getattr(e, "link", ""),
            "published": published,
            "content": html_to_text(content),
        })
    return out


def adapter_ameba(boat: dict) -> list[dict]:
    return _parse_feed(f"https://rssblog.ameba.jp/{boat['ameba_id']}/rss20.xml")


def adapter_fc2(boat: dict) -> list[dict]:
    return _parse_feed(boat["feed"])


def adapter_wordpress(boat: dict) -> list[dict]:
    try:
        return _parse_feed(boat["feed"])
    except FileNotFoundError:
        if boat.get("feed_fallback"):
            log(f"  {boat['feed']} が404。fallback を使用")
            return _parse_feed(boat["feed_fallback"])
        raise


ADAPTERS = {
    "ameba": adapter_ameba,
    "fc2": adapter_fc2,
    "wordpress": adapter_wordpress,
    # "zekkouchou": adapter_zekkouchou,   # v0.2
    # "html": adapter_html,               # v0.2
}


# ---------------------------------------------------------------- extraction

EXTRACT_SYSTEM = """あなたは釣り船の釣果ブログ記事から構造化データを抜き出す係です。
若狭湾（敦賀・小浜・京都北部）のイカメタル・オモリグ・ティップラン等の記事が中心です。
出力は JSON のみ。前置き・説明・コードフェンスは一切付けないこと。

魚種名の正規化ルール:
- マイカ / 白イカ / シロイカ / ケンサキ / 大剣 → "ケンサキイカ"
- ムギイカ → "スルメイカ"
- 表記が無い・不明なフィールドは null
- 匹数は「〜杯」「〜ハイ」「〜パイ」「〜匹」を数値化。「5〜30杯」なら min=5 max=30。
  「トップ39ハイ」のように竿頭だけ書かれていれば max にその値、min は null。
- 「船中436ハイ」のような合計は total に入れる。
"""

EXTRACT_USER = """次の記事から釣果を抜き出してください。

船名: {boat_name}（エリア: {area}）
{sub_boat_note}
記事タイトル: {title}
記事URL: {link}
記事投稿日: {published}

--- 記事本文 ---
{content}
--- ここまで ---

以下のスキーマの JSON だけを返してください:
{{
  "is_catch_report": true or false,        // 釣果報告か（出船案内・お知らせ等なら false）
  "trip_date": "YYYY-MM-DD" or null,       // 釣行日。投稿日ではなく実際に釣った日。年が無ければ投稿日の年を使う
  "sub_boat": string or null,              // 複数船運用のとき、どの船か（該当なしなら null）
  "trip_type": string or null,             // 半夜便 / 深夜便 / オールナイト便 / 午前便 / 午後便 など
  "methods": [string],                     // イカメタル / オモリグ / ティップラン / バチコン / タイラバ など
  "species": [
    {{"name": string, "min": number or null, "max": number or null, "total": number or null, "size_note": string or null}}
  ],
  "top_count": number or null,             // 竿頭の匹数（主ターゲットのもの）
  "condition": string or null,             // 潮・風・サバ等の状況を20字以内で
  "summary": string                        // 釣況を40字以内で
}}"""


def extract(client, boat: dict, entry: dict) -> dict | None:
    sub_note = ""
    if boat.get("sub_boats"):
        names = " / ".join(f"{s['name']}（手掛かり: {', '.join(s['hints'])}）" for s in boat["sub_boats"])
        sub_note = f"この船は複数船運用です: {names}。記事から該当する船名を sub_boat に入れてください。"
    prompt = EXTRACT_USER.format(
        boat_name=boat["name"],
        area=boat["area"],
        sub_boat_note=sub_note,
        title=entry["title"],
        link=entry["link"],
        published=entry["published"].strftime("%Y-%m-%d") if entry["published"] else "不明",
        content=entry["content"][:6000],
    )
    for attempt in range(3):
        try:
            resp = client.messages.create(
                model=MODEL,
                max_tokens=800,
                system=EXTRACT_SYSTEM,
                messages=[{"role": "user", "content": prompt}],
            )
            text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
            text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
            return json.loads(text)
        except json.JSONDecodeError:
            log(f"  JSON パース失敗 (attempt {attempt+1}): {text[:120]!r}")
        except Exception as e:  # noqa: BLE001
            log(f"  API エラー (attempt {attempt+1}): {e}")
            time.sleep(2 * (attempt + 1))
    return None


def resolve_sub_boat(boat: dict, extracted: dict, title: str) -> tuple[str, str]:
    """sub_boat の名寄せ。返り値は (boat_key, display_name)。"""
    if not boat.get("sub_boats"):
        return boat["id"], boat["name"]
    cand = (extracted.get("sub_boat") or "") + " " + title
    for s in boat["sub_boats"]:
        if any(h.lower() in cand.lower() for h in s["hints"]):
            return s["id"], f"{boat['name']} {s['name']}" if s["id"] != f"{boat['id']}_main" else boat["name"]
    return boat["id"], boat["name"]


# ---------------------------------------------------------------- main

def load_existing() -> dict:
    if OUT_JSON.exists():
        d = json.loads(OUT_JSON.read_text(encoding="utf-8"))
        if not d.get("sample"):          # 初期サンプルデータは捨てて作り直す
            return d
    return {"schema_version": 1, "generated_at": None, "catches": [], "skipped_ids": []}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="API を呼ばず記事一覧だけ表示")
    ap.add_argument("--boat", help="この id の船だけ処理")
    args = ap.parse_args()

    cfg = yaml.safe_load(BOATS_YAML.read_text(encoding="utf-8"))
    boats = [b for b in cfg["boats"] if b.get("enabled", True)]
    if args.boat:
        boats = [b for b in boats if b["id"] == args.boat]

    data = load_existing()
    known = {c["id"] for c in data["catches"]} | set(data.get("skipped_ids", []))
    cutoff = datetime.now(JST) - timedelta(days=LOOKBACK_DAYS)

    client = None
    if not args.dry_run:
        import anthropic
        if not os.environ.get("ANTHROPIC_API_KEY"):
            log("ANTHROPIC_API_KEY が未設定です")
            return 2
        client = anthropic.Anthropic()

    added = 0
    for boat in boats:
        adapter = ADAPTERS.get(boat["source"])
        if adapter is None:
            log(f"{boat['name']}: source={boat['source']} は未実装、スキップ")
            continue
        log(f"{boat['name']} ({boat['source']}) 取得中")
        try:
            entries = adapter(boat)
        except Exception as e:  # noqa: BLE001
            log(f"  取得失敗: {e}")
            continue
        log(f"  {len(entries)} 件")

        for e in entries:
            if not e["link"]:
                continue
            eid = entry_id(e["link"])
            if eid in known:
                continue
            if e["published"] and e["published"] < cutoff:
                continue
            if args.dry_run:
                log(f"  [new] {e['published']:%m/%d} {e['title'][:40]}  ({len(e['content'])}字)")
                continue

            if len(e["content"]) < 120:
                e["content"] = fetch_page_text(e["link"]) or e["content"]

            log(f"  抽出: {e['title'][:40]}")
            ex = extract(client, boat, e)
            if ex is None:
                continue
            if not ex.get("is_catch_report"):
                data.setdefault("skipped_ids", []).append(eid)
                # 何を弾いたか後で確認できるようタイトルも残す（直近50件）
                data.setdefault("skipped", []).append(
                    {"id": eid, "boat": boat["name"], "title": e["title"][:60], "url": e["link"]})
                data["skipped"] = data["skipped"][-50:]
                known.add(eid)
                continue

            key, disp = resolve_sub_boat(boat, ex, e["title"])
            data["catches"].append({
                "id": eid,
                "boat_id": boat["id"],
                "boat_key": key,
                "boat_name": disp,
                "area": boat["area"],
                "trip_date": ex.get("trip_date"),
                "trip_type": ex.get("trip_type"),
                "methods": ex.get("methods") or [],
                "species": ex.get("species") or [],
                "top_count": ex.get("top_count"),
                "condition": ex.get("condition"),
                "summary": ex.get("summary") or "",
                "title": e["title"],
                "url": e["link"],
                "published": e["published"].isoformat() if e["published"] else None,
                "extracted_at": datetime.now(JST).isoformat(),
                "model": MODEL,
            })
            known.add(eid)
            added += 1

    if args.dry_run:
        return 0

    # 釣行日の降順、同日なら投稿日降順
    data["catches"].sort(key=lambda c: (c.get("trip_date") or "", c.get("published") or ""), reverse=True)
    data["generated_at"] = datetime.now(JST).isoformat()
    data["boats"] = [
        {"id": b["id"], "name": b["name"], "area": b["area"], "home": b.get("home"),
         "sub_boats": [{"id": s["id"], "name": s["name"]} for s in b.get("sub_boats", [])]}
        for b in cfg["boats"]
    ]
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"完了: {added} 件追加、合計 {len(data['catches'])} 件 → {OUT_JSON.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
