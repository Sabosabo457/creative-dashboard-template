#!/usr/bin/env python3
"""ChatGPT に貼るための「まとめファイル」（chatgpt-bundle.txt）を作る。標準ライブラリのみ。

必要なファイルを 1 つの文章ファイルにまとめる。各ファイルは「=== FILE: パス ===」の行から始まる。
ファイルを変えたら、このスクリプトを実行して作り直す（tests/test_bundle.py が、古くなっていないか確かめる）。

使い方: python3 scripts/make_bundle.py          （chatgpt-bundle.txt を作り直す）
        python3 scripts/make_bundle.py --check  （古くなっていないかだけ確かめる）
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "chatgpt-bundle.txt"
FILES = [
    "AGENTS.md", "VERSION",
    "config/columns.json", "config/schema.json", "config/settings.json",
    "scripts/_cfg.py", "scripts/make_datasets.py", "scripts/build.py", "scripts/make_sample.py",
    "template/dashboard.html", "reference/snapshot-format.md",
]
HEADER = """# 創作ダッシュボード ChatGPT 用まとめファイル（版 %s）
これは、テンプレートの必要なファイルを 1 つにまとめた文章ファイルです。
各ファイルは、`=== FILE: パス ===` の行から始まり、次の `=== FILE:` の行（または `=== END ===`）の直前までが中身です。
ChatGPT に渡して、この区切りのとおりにファイルへ復元させます（中身は 1 文字も変えない）。
含まれないもの: .env、実データ、自分用の設定（*.local.*）、テスト。
"""


def build(root=None):
    root = pathlib.Path(root) if root else ROOT
    version = (root / "VERSION").read_text(encoding="utf-8").strip()
    parts = [HEADER % version]
    for rel in FILES:
        text = (root / rel).read_text(encoding="utf-8")
        if not text.endswith("\n"):
            text += "\n"
        parts.append("=== FILE: %s ===\n%s" % (rel, text))
    parts.append("=== END ===\n")
    return "".join(parts)


def main():
    text = build()
    if "--check" in sys.argv:
        ok = OUT.exists() and OUT.read_text(encoding="utf-8") == text
        print("OK: まとめファイルは最新です。" if ok else
              "まとめファイル（chatgpt-bundle.txt）が古くなっています。python3 scripts/make_bundle.py で作り直してください。")
        sys.exit(0 if ok else 1)
    OUT.write_text(text, encoding="utf-8")
    print("作成しました: chatgpt-bundle.txt（%d ファイル・%d 文字）" % (len(FILES), len(text)))


if __name__ == "__main__":
    main()
