"""変換処理の安全装置のテスト（標準ライブラリのみ）。実行: python3 -m unittest discover -s tests

確認すること: 列名のずれ・取得の途中打ち切り・件数の急減・全部未分類・制御文字を、黙って通さず止める／警告する。
"""
import contextlib
import copy
import io
import json
import pathlib
import shutil
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "scripts"))
import make_datasets  # noqa: E402

COLS = {
    "daily": {
        "名前": {"type": "title"}, "日付": {"type": "date"},
        "進捗": {"type": "select", "options": ["あり", "なし（お休み）"]},
        "種別": {"type": "multi_select", "options": ["ラフ", "ほか"]},
        "内容": {"type": "rich_text"}, "作品": {"type": "rich_text"},
    },
    "events": {
        "イベント名": {"type": "title"}, "開催日": {"type": "date"}, "申込開始日": {"type": "date"},
        "申込締切日": {"type": "date"}, "状態": {"type": "select", "options": ["申込予定"]},
        "区分": {"type": "multi_select", "options": ["漫画"]},
    },
    "tasks": {
        "名前": {"type": "title"}, "カテゴリ": {"type": "select", "options": []},
        "ステータス": {"type": "status", "options": ["未着手", "進行中", "完了"]},
        "優先度": {"type": "select", "options": []}, "期限": {"type": "date"},
        "イベント": {"type": "relation"}, "工程": {"type": "select", "options": ["入稿"]},
    },
}


def base_snapshot():
    return {
        "asof": "2026-10-30",
        "meta": {"source": "test", "complete": {"daily": True, "events": True, "tasks": True}},
        "columns": copy.deepcopy(COLS),
        "daily": [
            {"date": "2026-10-28", "state": "あり", "kind": ["ラフ"], "note": "a", "work": "", "page": ""},
            {"date": "2026-10-28", "state": "あり", "kind": ["ほか"], "note": "b", "work": "", "page": ""},
            {"date": "2026-10-29", "state": "なし（お休み）", "kind": [], "note": "", "work": "", "page": ""},
        ],
        "events": [{"id": "uuid-e", "name": "イベントA", "date": "2026-12-29", "date_end": "", "apply_open": "",
                    "apply_deadline": "2026-11-01", "status": "申込予定", "kind": ["漫画"], "page": ""}],
        "tasks": [{"id": "uuid-t", "name": "入稿", "status": "未着手", "due": "2026-11-05",
                   "event_id": "uuid-e", "step": "入稿", "category": "", "priority": "", "page": ""}],
    }


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        shutil.copytree(ROOT / "config", self.tmp / "config")
        (self.tmp / "data").mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_md(self, snap, argv=None, settings_local=None, schema_local=None):
        (self.tmp / "data/snapshot.json").write_text(json.dumps(snap, ensure_ascii=False), encoding="utf-8")
        if settings_local:
            (self.tmp / "config/settings.local.json").write_text(json.dumps(settings_local), encoding="utf-8")
        if schema_local:
            (self.tmp / "config/schema.local.json").write_text(json.dumps(schema_local, ensure_ascii=False), encoding="utf-8")
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                make_datasets.main(self.tmp, argv or ["x"])
            return None, buf.getvalue()
        except SystemExit as e:
            return str(e.code), buf.getvalue()

    def real(self, name):
        return json.loads((self.tmp / "data/real" / (name + ".json")).read_text(encoding="utf-8"))


class TestNormal(Base):
    def test_ok_counts_by_day(self):
        err, out = self.run_md(base_snapshot())
        self.assertIsNone(err, err)
        c = self.real("counts")
        self.assertEqual((c["daily_rows"], c["daily_days"], c["events"], c["tasks"]), (3, 2, 1, 1))
        self.assertIn("日次ログ: 3 件 / 記録のある日 2 日", out)
        self.assertEqual(self.real("ctx")["counts"], c)

    def test_ids_anonymized_and_text_off_by_default(self):
        self.run_md(base_snapshot())
        self.assertEqual(self.real("events")[0]["id"], "e1")
        self.assertEqual(self.real("tasks")[0]["event_id"], "e1")
        self.assertTrue(all(d["note"] == "" for d in self.real("daily")))
        self.assertNotIn("uuid", json.dumps(self.real("tasks")))


class TestColumns(Base):
    def test_required_column_renamed_stops_with_hint(self):
        s = base_snapshot()
        s["columns"]["daily"]["進捗状況"] = s["columns"]["daily"].pop("進捗")
        err, _ = self.run_md(s)
        self.assertIn("更新を止めました", err)
        self.assertIn("列「進捗」が Notion に見つかりません", err)
        self.assertIn("近い列名があります: 「進捗状況」", err)
        self.assertFalse((self.tmp / "data/real/daily.json").exists())

    def test_optional_column_typo_warns_and_continues(self):
        s = base_snapshot()
        s["columns"]["events"]["区分け"] = s["columns"]["events"].pop("区分")
        err, out = self.run_md(s)
        self.assertIsNone(err, err)
        self.assertIn("近い列名があります: 「区分け」", out)

    def test_schema_local_override_fixes_the_name(self):
        s = base_snapshot()
        s["columns"]["events"]["区分け"] = s["columns"]["events"].pop("区分")
        err, out = self.run_md(s, schema_local={"events": {"kind": "区分け"}})
        self.assertIsNone(err, err)
        self.assertNotIn("列「区分」", out)

    def test_wrong_type_stops(self):
        s = base_snapshot()
        s["columns"]["daily"]["日付"] = {"type": "rich_text"}
        err, _ = self.run_md(s)
        self.assertIn("列「日付」の種類が違います", err)

    def test_unmapped_option_warns(self):
        s = base_snapshot()
        s["columns"]["daily"]["進捗"]["options"].append("保留")
        err, out = self.run_md(s)
        self.assertIsNone(err, err)
        self.assertIn("「保留」は state_map に無い", out)

    def test_all_unclassified_stops(self):
        s = base_snapshot()
        for r in s["daily"]:
            r["state"] = "Yes"
        err, _ = self.run_md(s)
        self.assertIn("すべて『未分類』", err)

    def test_done_values_mismatch_warns(self):
        s = base_snapshot()
        s["columns"]["tasks"]["ステータス"]["options"] = ["Todo", "Doing", "Done"]
        err, out = self.run_md(s)
        self.assertIsNone(err, err)
        self.assertIn("done_values", out)

    def test_missing_columns_stops_unless_allowed(self):
        s = base_snapshot()
        del s["columns"]
        err, _ = self.run_md(s)
        self.assertIn("columns", err)
        err, out = self.run_md(s, argv=["x", "--allow-no-columns"])
        self.assertIsNone(err, err)
        self.assertIn("列の照合を省略", out)


class TestCompleteness(Base):
    def test_incomplete_stops(self):
        s = base_snapshot()
        s["meta"]["complete"]["daily"] = False
        err, _ = self.run_md(s)
        self.assertIn("日次ログ: 取得が最後まで終わっていません", err)

    def test_undated_daily_row_warns_and_is_not_counted(self):
        s = base_snapshot()
        s["daily"].append({"date": "", "state": "あり", "kind": [], "note": "", "work": "", "page": ""})
        err, out = self.run_md(s)
        self.assertIsNone(err, err)
        self.assertEqual(self.real("counts")["daily_rows"], 3)
        self.assertIn("日付が空の行が 1 件", out)

    def test_unknown_completeness_warns(self):
        s = base_snapshot()
        del s["meta"]
        err, out = self.run_md(s)
        self.assertIsNone(err, err)
        self.assertIn("meta.complete", out)

    def test_count_drop_vs_previous_warns(self):
        (self.tmp / "data/real").mkdir()
        (self.tmp / "data/real/counts.json").write_text(
            json.dumps({"daily_rows": 100, "events": 3, "tasks": 3}), encoding="utf-8")
        err, out = self.run_md(base_snapshot())
        self.assertIsNone(err, err)
        self.assertIn("日次ログ の件数が前回（100 件）より大きく減っています", out)


class TestTextSafety(Base):
    def test_control_chars_removed_and_truncated(self):
        s = base_snapshot()
        s["daily"][0]["note"] = "x\x00y z" + "あ" * 500
        s["events"][0]["name"] = "名\x07前"
        self.run_md(s, settings_local={"include_text": True, "max_text_length": 50})
        note = self.real("daily")[0]["note"]
        self.assertNotIn("\x00", note)
        self.assertNotIn(" ", note)
        self.assertEqual(len(note), 50)
        self.assertEqual(self.real("events")[0]["name"], "名前")

    def test_bad_shapes_stop_with_japanese_message(self):
        err, _ = self.run_md({"asof": "2026/10/30", "daily": [{"date": "2026-10-01"}], "events": [], "tasks": "x"})
        self.assertIn("形に問題があります", err)
        self.assertIn("state", err)


if __name__ == "__main__":
    unittest.main()
