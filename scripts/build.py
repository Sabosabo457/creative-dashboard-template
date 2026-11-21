#!/usr/bin/env python3
"""template/dashboard.html にデータを埋め込み、1 枚の HTML（out/index.html）を作る。標準ライブラリのみ。

使い方: python3 scripts/build.py              （data/real を使う）
        python3 scripts/build.py --sample     （data/sample のダミーデータを使う）
出力された HTML は通信を一切しない（CSP で禁止）。ローカルで開くだけ。個人データが入るので共有しない。
"""
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def main():
    sample = "--sample" in sys.argv
    src = ROOT / ("data/sample" if sample else "data/real")
    if not (src / "ctx.json").exists():
        sys.exit("%s にデータがありません。先に fetch_notion.py と make_datasets.py を実行してください。" % src.relative_to(ROOT))
    data = {n: json.loads((src / (n + ".json")).read_text(encoding="utf-8")) for n in ("daily", "events", "tasks")}
    data["ctx"] = json.loads((src / "ctx.json").read_text(encoding="utf-8"))
    if isinstance(data["ctx"], list):
        data["ctx"] = data["ctx"][0]
    if not DATE.match(data["ctx"].get("asof", "")):
        sys.exit("ctx.json の asof が YYYY-MM-DD ではありません。")
    data["ctx"]["sample"] = sample
    data["settings"] = json.loads((ROOT / "config/settings.json").read_text(encoding="utf-8"))

    # </script> などで HTML が壊れない／注入されないよう、記号を無害化して埋め込む
    blob = (json.dumps(data, ensure_ascii=False)
            .replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
            .replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))
    tpl = (ROOT / "template/dashboard.html").read_text(encoding="utf-8")
    if '"__DATA__"' not in tpl:
        sys.exit("テンプレートに埋め込み位置がありません。")
    out = ROOT / "out/index.html"
    out.parent.mkdir(exist_ok=True)
    out.write_text(tpl.replace('"__DATA__"', blob, 1), encoding="utf-8")
    print("作成しました: out/index.html（%s）" % ("ダミーデータ" if sample else "実データ"))


if __name__ == "__main__":
    main()
