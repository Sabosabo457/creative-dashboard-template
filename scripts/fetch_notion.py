#!/usr/bin/env python3
"""【動線 P】Notion の 3 つの DB を読み取り専用で取得し、data/snapshot.json に保存する。標準ライブラリのみ。

- 使う API は「DB の情報の取得（GET）」と「DB のクエリ（POST /query）」だけ。どちらも読み取りで、Notion への書き込みはしない。
- 通信先は api.notion.com に固定。トークンは .env / 環境変数から読み、出力には一切表示しない。
- 列の一覧（名前と種類）と、取得が最後まで終わったかの記録も snapshot に入れる（make_datasets.py が照合する）。
- 使い方: python3 scripts/fetch_notion.py            （本番）
          python3 scripts/fetch_notion.py --selftest （通信せず、変換処理だけを確認）
"""
import datetime
import json
import os
import pathlib
import re
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import _cfg  # noqa: E402

ROOT = _cfg.ROOT
API = "https://api.notion.com/v1/databases/"
VERSION = "2022-06-28"
HEX32 = re.compile(r"[0-9a-fA-F]{32}")


def load_env():
    p = ROOT / ".env"
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def norm_id(s):
    """DB の ID（32 文字）を取り出す。ダッシュ入りや、URL を貼ってしまった場合も受け付ける。"""
    m = HEX32.search((s or "").replace("-", ""))
    return m.group(0).lower() if m else ""


def pv(prop):
    """Notion のプロパティ値を、単純な Python の値にする。"""
    if not prop:
        return None
    t = prop.get("type")
    v = prop.get(t)
    if t in ("title", "rich_text"):
        return "".join(x.get("plain_text", "") for x in (v or []))
    if t == "date":
        return v or {}
    if t in ("select", "status"):
        return (v or {}).get("name", "")
    if t == "multi_select":
        return [x.get("name", "") for x in (v or [])]
    if t == "checkbox":
        return bool(v)
    if t == "relation":
        return [x.get("id", "") for x in (v or [])]
    return None


def day(d):
    return (d or {}).get("start", "")[:10] if d else ""


def end_day(d):
    return ((d or {}).get("end") or "")[:10] if d else ""


def parse_daily(page, sc):
    p = page.get("properties", {})
    return {
        "date": day(pv(p.get(sc["date"]))),
        "state": pv(p.get(sc["state"])) or "",
        "kind": pv(p.get(sc["kind"])) or [],
        "note": pv(p.get(sc["note"])) or "",
        "work": pv(p.get(sc["work"])) or "",
        "page": page.get("url", ""),
    }


def parse_event(page, sc):
    p = page.get("properties", {})
    d = pv(p.get(sc["date"])) or {}
    return {
        "id": page.get("id", ""),
        "name": pv(p.get(sc["title"])) or "",
        "date": day(d),
        "date_end": end_day(d),
        "apply_open": day(pv(p.get(sc["apply_open"]))),
        "apply_deadline": day(pv(p.get(sc["apply_deadline"]))),
        "status": pv(p.get(sc["status"])) or "",
        "kind": pv(p.get(sc["kind"])) or [],
        "page": page.get("url", ""),
    }


def parse_task(page, sc):
    p = page.get("properties", {})
    rel = pv(p.get(sc["event"])) or []
    return {
        "id": page.get("id", ""),
        "name": pv(p.get(sc["title"])) or "",
        "category": pv(p.get(sc["category"])) or "",
        "status": pv(p.get(sc["status"])) or "",
        "priority": pv(p.get(sc["priority"])) or "",
        "due": day(pv(p.get(sc["due"]))),
        "event_id": rel[0] if rel else "",
        "step": pv(p.get(sc["step"])) or "",
        "page": page.get("url", ""),
    }


def parse_columns(db):
    """DB の情報から、列の名前・種類・選択肢の名前を取り出す（行の内容は含まれない）。"""
    out = {}
    for name, p in (db.get("properties") or {}).items():
        t = p.get("type", "")
        item = {"type": t}
        if t in ("select", "multi_select", "status"):
            item["options"] = [o.get("name", "") for o in (p.get(t) or {}).get("options", [])]
        out[name] = item
    return out


def call(method, path, token, body=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        API + path, data=data, method=method,
        headers={"Authorization": "Bearer " + token, "Notion-Version": VERSION, "Content-Type": "application/json"},
    )
    for _ in range(5):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(int(e.headers.get("Retry-After", "3")))
                continue
            hint = {401: "トークンが正しくないようです。",
                    403: "このトークンに読み取りの権限がありません。",
                    404: "DB が見つからないか、DB がインテグレーションに共有されていません。"}.get(e.code, "")
            # エラーの本文は表示しない（状態コードと案内だけ）
            sys.exit("Notion への読み取りに失敗しました（HTTP %d）。%s" % (e.code, hint))
        except urllib.error.URLError:
            sys.exit("Notion に接続できませんでした。インターネット接続を確認してください。")
    sys.exit("Notion が混み合っています。しばらく待ってからやり直してください。")


def query_all(db_id, token):
    """最後のページまで取得する。途中で終わった場合はここまで到達しない（= complete=True は『最後まで取れた』の意味）。"""
    rows, cursor = [], None
    while True:
        body = {"page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        data = call("POST", db_id + "/query", token, body)
        rows.extend(data.get("results", []))
        if not data.get("has_more"):
            return rows
        cursor = data.get("next_cursor")
        time.sleep(0.4)  # 約 3 回/秒の制限の内側に収める


def today_jst():
    jst = datetime.timezone(datetime.timedelta(hours=9))
    return datetime.datetime.now(jst).strftime("%Y-%m-%d")


def build_snapshot(pages, schema, columns, complete):
    return {
        "asof": today_jst(),
        "meta": {"source": "fetch_notion.py", "complete": complete},
        "columns": columns,
        "daily": [parse_daily(x, schema["daily"]) for x in pages["daily"]],
        "events": [parse_event(x, schema["events"]) for x in pages["events"]],
        "tasks": [parse_task(x, schema["tasks"]) for x in pages["tasks"]],
    }


def selftest(schema):
    """ダミーの Notion 応答で、変換処理だけを確認する（通信しない）。"""
    d, e, t = schema["daily"], schema["events"], schema["tasks"]
    daily = {"id": "x", "url": "https://example.invalid/x", "properties": {
        d["date"]: {"type": "date", "date": {"start": "2026-01-02"}},
        d["state"]: {"type": "select", "select": {"name": "あり"}},
        d["kind"]: {"type": "multi_select", "multi_select": [{"name": "ラフ"}]},
        d["note"]: {"type": "rich_text", "rich_text": [{"plain_text": "テスト"}]},
        d["work"]: {"type": "rich_text", "rich_text": []}}}
    r = parse_daily(daily, d)
    assert r["date"] == "2026-01-02" and r["state"] == "あり" and r["kind"] == ["ラフ"], r
    ev = {"id": "e-1", "url": "", "properties": {
        e["title"]: {"type": "title", "title": [{"plain_text": "イベントA"}]},
        e["date"]: {"type": "date", "date": {"start": "2026-12-29", "end": "2026-12-30"}},
        e["apply_open"]: {"type": "date", "date": None},
        e["apply_deadline"]: {"type": "date", "date": {"start": "2026-10-20"}},
        e["status"]: {"type": "select", "select": {"name": "申込完了"}},
        e["kind"]: {"type": "multi_select", "multi_select": [{"name": "漫画"}]}}}
    r = parse_event(ev, e)
    assert r["name"] == "イベントA" and r["date_end"] == "2026-12-30" and r["apply_open"] == "", r
    tk = {"id": "t-1", "url": "", "properties": {
        t["title"]: {"type": "title", "title": [{"plain_text": "入稿"}]},
        t["status"]: {"type": "status", "status": {"name": "完了"}},
        t["due"]: {"type": "date", "date": {"start": "2026-11-05"}},
        t["event"]: {"type": "relation", "relation": [{"id": "e-1"}]},
        t["step"]: {"type": "select", "select": {"name": "入稿"}}}}
    r = parse_task(tk, t)
    assert r["status"] == "完了" and r["event_id"] == "e-1" and r["due"] == "2026-11-05", r
    cols = parse_columns({"properties": {
        "進捗": {"type": "select", "select": {"options": [{"name": "あり"}, {"name": "なし（お休み）"}]}},
        "日付": {"type": "date", "date": {}}}})
    assert cols["進捗"]["options"] == ["あり", "なし（お休み）"] and cols["日付"] == {"type": "date"}, cols
    assert norm_id("https://www." + "notion.so/abc/" + "a1" * 16 + "?v=" + "b2" * 16) == "a1" * 16
    print("selftest OK")


def main():
    schema = _cfg.load("schema")
    if "--selftest" in sys.argv:
        return selftest(schema)
    load_env()
    token = os.environ.get("NOTION_TOKEN", "")
    ids = {k: norm_id(os.environ.get("NOTION_DB_" + k.upper(), "")) for k in ("daily", "events", "tasks")}
    missing = [k for k, v in ids.items() if not v] + ([] if token else ["token"])
    if missing:
        sys.exit(".env に未設定、または形が正しくない項目があります: " + ", ".join(missing) +
                 "（DB の ID は 32 文字の英数字。.env.example を参照）")
    columns, pages, complete = {}, {}, {}
    for k, v in ids.items():
        columns[k] = parse_columns(call("GET", v, token))
        pages[k] = query_all(v, token)
        complete[k] = True
    snap = build_snapshot(pages, schema, columns, complete)
    out = ROOT / "data/snapshot.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(snap, ensure_ascii=False, indent=1), encoding="utf-8")
    print("保存しました:", {k: len(snap[k]) for k in ("daily", "events", "tasks")})


if __name__ == "__main__":
    main()
