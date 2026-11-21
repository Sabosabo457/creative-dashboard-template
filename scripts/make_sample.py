#!/usr/bin/env python3
"""動作確認用のダミーデータ（data/sample/）を作る。実在の人物・作品・イベントとは無関係。"""
import datetime
import json
import pathlib
import random

ROOT = pathlib.Path(__file__).resolve().parent.parent
random.seed(7)
ASOF = datetime.date(2026, 10, 30)
KINDS = ["構想", "下書き", "制作", "仕上げ", "整理", "その他"]
WORKS = ["サンプル作品A", "サンプル作品B", ""]


def main():
    daily = []
    d = datetime.date(2026, 1, 1)
    while d < ASOF:
        x = random.random()
        if x < 0.5:
            k = random.sample(KINDS, random.choice([1, 1, 2]))
            daily.append({"date": d.isoformat(), "state": "進捗あり", "kind": ",".join(k),
                          "note": "サンプルの内容（%s）" % k[0], "work": random.choice(WORKS), "page": ""})
        elif x < 0.75:
            daily.append({"date": d.isoformat(), "state": "休み", "kind": "", "note": "", "work": "", "page": ""})
        d += datetime.timedelta(days=1)

    def prep(day_s):
        return (datetime.date.fromisoformat(day_s) - datetime.timedelta(days=15)).isoformat()

    events = [
        {"id": "e1", "name": "サンプルイベント A", "date": "2026-12-29", "date_end": "2026-12-30",
         "apply_open": "2026-09-01", "apply_deadline": "2026-10-20", "status": "申込完了", "kind": "漫画,イラスト", "page": ""},
        {"id": "e2", "name": "サンプルイベント B", "date": "2027-02-14", "date_end": "",
         "apply_open": "2026-11-20", "apply_deadline": "2026-12-25", "status": "申込予定", "kind": "小説", "page": ""},
    ]
    tasks, n = [], 0
    for e, steps in (("e1", ["構想", "下書き", "制作", "仕上げ", "申込", "提出"]),
                     ("e2", ["構想", "制作", "申込", "提出"])):
        ev = next(x for x in events if x["id"] == e)
        for s in steps:
            n += 1
            due = ev["apply_deadline"] if s == "申込" else prep(ev["date"])
            done = s == "申込" and e == "e1"
            tasks.append({"id": "t%d" % n, "name": s, "category": "イベント準備",
                          "status": "完了" if done else "未着手", "priority": "", "due": due,
                          "event_id": e, "step": s, "page": ""})
    for i, (nm, due) in enumerate([("サンプルのタスク（週内）", "2026-11-02"), ("サンプルのタスク（来週）", "2026-11-08")], 1):
        tasks.append({"id": "t%d" % (n + i), "name": nm, "category": "", "status": "進行中", "priority": "",
                      "due": due, "event_id": "", "step": "", "page": ""})

    out = ROOT / "data/sample"
    out.mkdir(parents=True, exist_ok=True)
    for name, val in (("daily", daily), ("events", events), ("tasks", tasks), ("ctx", {"asof": ASOF.isoformat(), "counts": {"daily_rows": len(daily), "daily_days": len({d["date"] for d in daily}), "events": len(events), "tasks": len(tasks)}})):
        (out / (name + ".json")).write_text(json.dumps(val, ensure_ascii=False, indent=1), encoding="utf-8")
    print("sample:", len(daily), len(events), len(tasks))


if __name__ == "__main__":
    main()
