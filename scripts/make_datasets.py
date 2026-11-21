#!/usr/bin/env python3
"""data/snapshot.json → data/real/*.json（ダッシュボード用）。標準ライブラリのみ。

動線 P（fetch_notion.py）でも、動線 W（AI が snapshot.json を作る）でも、同じ検査を通す。
問題があれば【止めて】日本語で報告する（黙って 0 日の画面を作らない）。

検査:
1. snapshot.json の形（reference/snapshot-format.md）
2. Notion の列・種類が、config/columns.json（仕様）と config/schema.json（列名）に合っているか
3. 取得が最後まで終わったか（meta.complete）
4. 進捗の選択肢が state_map に対応しているか（全部「未分類」になる場合は止める）
5. 前回より件数が大きく減っていないか

個人情報を減らすための処理:
- anonymize_ids: Notion のページ ID（UUID）を e1, t1 … の連番に置き換える
- include_page_urls: false なら Notion のページ URL を出力しない
- include_text: false なら「内容」「作品」の本文を出力しない（既定）
- max_text_length: 本文の最大文字数。制御文字は取り除く
"""
import difflib
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import _cfg  # noqa: E402

DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\u2028\u2029]")
LABEL = {"daily": "日次ログ", "events": "イベント", "tasks": "Tasks"}
# AI のコネクタが返す種類名と、Notion の API の種類名の違いを吸収する
TYPE_ALIAS = {"text": "rich_text"}
REQUIRED = {
    "daily": ("date", "state"),
    "events": ("id", "name", "date", "status"),
    "tasks": ("id", "name", "status"),
}


def clean(s, limit=None):
    s = CTRL.sub("", str(s if s is not None else ""))
    return s[:limit] if limit else s


def validate(snap, need_columns=True):
    """snapshot.json の形を確認する。問題の説明（日本語）を返す。空なら問題なし。"""
    errs = []
    if not isinstance(snap, dict):
        return ["snapshot.json が JSON の連想配列（{...}）になっていません。"]
    if not DATE.match(str(snap.get("asof", ""))):
        errs.append("asof（基準日）が YYYY-MM-DD の形ではありません。")
    for key, req in REQUIRED.items():
        rows = snap.get(key)
        if not isinstance(rows, list):
            errs.append("%s が一覧（[...]）になっていません。" % key)
            continue
        for i, r in enumerate(rows[:5000]):
            if not isinstance(r, dict):
                errs.append("%s の %d 件目が {...} の形ではありません。" % (key, i + 1))
                break
            miss = [k for k in req if k not in r]
            if miss:
                errs.append("%s の %d 件目に必要な項目がありません: %s" % (key, i + 1, ", ".join(miss)))
                break
            bad = [k for k in ("date", "due", "date_end") if r.get(k) and not DATE.match(str(r[k]))]
            if bad:
                errs.append("%s の %d 件目の %s が YYYY-MM-DD の形ではありません。" % (key, i + 1, bad[0]))
                break
    if need_columns and not isinstance(snap.get("columns"), dict):
        errs.append("columns（Notion の列の一覧）がありません。DB の列名と種類を columns に入れてください"
                    "（どうしても取れない場合だけ --allow-no-columns）。")
    meta = snap.get("meta")
    if meta is not None and not (isinstance(meta, dict) and isinstance(meta.get("complete", {}), dict)):
        errs.append("meta の形が正しくありません（meta.complete は {daily: true, ...} の形）。")
    return errs


def check_columns(snap, sch, spec, cfg):
    """Notion の列と仕様を照合する。 (止める問題, 警告) を返す。"""
    errs, warns = [], []
    all_cols = snap.get("columns") or {}
    for db in ("daily", "events", "tasks"):
        cols = all_cols.get(db)
        if not isinstance(cols, dict):
            errs.append("columns に %s の列情報がありません。" % LABEL[db])
            continue
        for logical, rule in spec[db].items():
            name = sch[db].get(logical)
            if not isinstance(name, str):
                continue
            req = rule.get("required", False)
            sink = errs if req else warns
            tail = "" if req else "（任意の列のため続行します。この項目は空になります）"
            if name not in cols:
                near = difflib.get_close_matches(name, list(cols), n=1, cutoff=0.6)
                hint = ("。近い列名があります: 「%s」。Notion の列名を直すか、"
                        "config/schema.local.json に書いて対応づけてください" % near[0]) if near else ""
                sink.append("%s: 列「%s」が Notion に見つかりません%s%s" % (LABEL[db], name, hint, tail))
                continue
            t = TYPE_ALIAS.get(cols[name].get("type"), cols[name].get("type"))
            if t not in rule["types"]:
                sink.append("%s: 列「%s」の種類が違います（Notion: %s／必要: %s）%s"
                            % (LABEL[db], name, t, " または ".join(rule["types"]), tail))
    # 進捗の選択肢
    st = all_cols.get("daily", {}).get(sch["daily"]["state"], {})
    unmapped = [o for o in st.get("options", []) if o not in sch["daily"]["state_map"]]
    if unmapped:
        warns.append("日次ログの進捗の選択肢%sは state_map に無いため『未分類』として扱います"
                     "（進捗あり／休みには数えません）" % "、".join("「%s」" % o for o in unmapped))
    # 完了扱いのステータス
    ts = all_cols.get("tasks", {}).get(sch["tasks"]["status"], {})
    if ts.get("options") and not any(o in cfg["done_values"] for o in ts["options"]):
        warns.append("Tasks のステータス %s のどれも done_values に入っていないため、完了済みのタスクが"
                     "未完了として並びます（settings.json の done_values を確認）"
                     % "、".join("「%s」" % o for o in ts["options"]))
    return errs, warns


def check_complete(snap):
    errs, warns = [], []
    comp = (snap.get("meta") or {}).get("complete", {})
    for db in ("daily", "events", "tasks"):
        if comp.get(db) is False:
            errs.append("%s: 取得が最後まで終わっていません（続きがあります）。最後まで取得し直してください。" % LABEL[db])
        elif db not in comp:
            warns.append("%s: 最後まで取得できたかの記録（meta.complete）がありません。"
                         "件数が Notion の DB 画面の件数と合うか確認してください。" % LABEL[db])
    return errs, warns


def main(root=None, argv=None):
    root = pathlib.Path(root) if root else _cfg.ROOT
    argv = sys.argv if argv is None else argv
    p = root / "data/snapshot.json"
    if not p.exists():
        sys.exit("data/snapshot.json がありません。先に Notion のデータを取得してください"
                 "（動線 P: fetch_notion.py／動線 W: AI に更新を頼む）。")
    try:
        snap = json.loads(p.read_text(encoding="utf-8"))
    except ValueError:
        sys.exit("data/snapshot.json が正しい JSON ではありません。reference/snapshot-format.md の形か確認してください。")
    no_cols = "--allow-no-columns" in argv
    errs = validate(snap, need_columns=not no_cols)
    if errs:
        sys.exit("data/snapshot.json の形に問題があります:\n - " + "\n - ".join(errs[:10]) +
                 "\n（形式は reference/snapshot-format.md を参照）")

    cfg = _cfg.load("settings", root)
    sch = _cfg.load("schema", root)
    spec = _cfg.load("columns", root)
    smap, kmap = sch["daily"]["state_map"], sch["daily"]["kind_map"]
    anon, urls, text = cfg["anonymize_ids"], cfg["include_page_urls"], cfg["include_text"]
    limit = int(cfg.get("max_text_length", 300))

    errs, warns = [], []
    if no_cols:
        warns.append("列の照合を省略しました（--allow-no-columns）。列名のずれは検出できません。")
    else:
        e, w = check_columns(snap, sch, spec, cfg)
        errs += e
        warns += w
    e, w = check_complete(snap)
    errs += e
    warns += w

    # --- 日次ログ ---
    daily = []
    undated = 0
    for r in sorted(snap["daily"], key=lambda r: r.get("date") or ""):
        if not r.get("date"):
            undated += 1
            continue
        daily.append({
            "date": r["date"],
            "state": smap.get(r["state"], "未分類"),
            "kind": ",".join(clean(kmap.get(k, k)) for k in r.get("kind", [])),
            "note": clean(r.get("note", ""), limit) if text else "",
            "work": clean(r.get("work", ""), limit) if text else "",
            "page": r.get("page", "") if urls else "",
        })
    if undated:
        warns.append("日次ログに、日付が空の行が %d 件あります。日付がないため、数えていません（Notion で日付を入れてください）。"
                     "この件数は、Notion の表の下に出る件数に含まれています。" % undated)
    if daily and not any(d["state"] != "未分類" for d in daily):
        errs.append("日次ログの進捗が、すべて『未分類』になります（進捗の選択肢の名前が state_map と一致していません）。"
                    "config/schema.local.json の daily.state_map を Notion の選択肢の名前に合わせてください。")
    if errs:
        sys.exit("更新を止めました。次を直してください:\n - " + "\n - ".join(errs))

    # --- イベント・タスク ---
    ev_alias = {}
    for i, e in enumerate(sorted(snap["events"], key=lambda e: e.get("date", "")), 1):
        ev_alias[e["id"]] = "e%d" % i if anon else e["id"]
    events = [{
        "id": ev_alias[e["id"]], "name": clean(e["name"]), "date": e["date"], "date_end": e.get("date_end", ""),
        "apply_open": e.get("apply_open", ""), "apply_deadline": e.get("apply_deadline", ""),
        "status": clean(e["status"]), "kind": ",".join(clean(k) for k in e.get("kind", [])),
        "page": e.get("page", "") if urls else "",
    } for e in snap["events"]]
    tasks = []
    for i, t in enumerate(snap["tasks"], 1):
        if not t.get("name"):
            continue
        tasks.append({
            "id": "t%d" % i if anon else t["id"], "name": clean(t["name"]), "category": clean(t.get("category", "")),
            "status": clean(t.get("status", "")), "priority": clean(t.get("priority", "")), "due": t.get("due", ""),
            "event_id": ev_alias.get(t.get("event_id", ""), ""), "step": clean(t.get("step", "")),
            "page": t.get("page", "") if urls else "",
        })

    # --- 件数と前回との比較 ---
    days = sorted({d["date"] for d in daily})
    counts = {"daily_rows": len(daily), "daily_days": len(days), "events": len(events), "tasks": len(tasks)}
    out = root / "data/real"
    out.mkdir(parents=True, exist_ok=True)
    prev_p = out / "counts.json"
    if prev_p.exists():
        try:
            prev = json.loads(prev_p.read_text(encoding="utf-8"))
            for key, label in (("daily_rows", "日次ログ"), ("events", "イベント"), ("tasks", "Tasks")):
                if prev.get(key, 0) >= 10 and counts[key] < prev[key] * 0.9:
                    warns.append("%s の件数が前回（%d 件）より大きく減っています（今回 %d 件）。"
                                 "取得が途中で止まっていないか確認してください。" % (label, prev[key], counts[key]))
        except ValueError:
            pass

    ctx = {"asof": snap["asof"], "counts": counts}
    for name, val in (("daily", daily), ("events", events), ("tasks", tasks), ("ctx", ctx), ("counts", counts)):
        (out / (name + ".json")).write_text(json.dumps(val, ensure_ascii=False, indent=1), encoding="utf-8")

    print("取得結果（Notion の各 DB の下部に出る件数と一致するか確認してください）:")
    span = "（%s〜%s）" % (days[0], days[-1]) if days else ""
    print("  日次ログ: %d 件 / 記録のある日 %d 日%s" % (counts["daily_rows"], counts["daily_days"], span))
    print("  イベント: %d 件" % counts["events"])
    print("  Tasks   : %d 件" % counts["tasks"])
    print("  本文の出力: %s／URL の出力: %s" % ("あり" if text else "なし", "あり" if urls else "なし"))
    if warns:
        print("注意:")
        for w in warns:
            print("  -", w)
    return counts


if __name__ == "__main__":
    main()
