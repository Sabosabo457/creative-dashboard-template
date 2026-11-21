#!/usr/bin/env python3
"""個人情報・認証情報の混入チェック。見つかったら終了コード 1。標準ライブラリのみ。

検査内容:
1. Git に入ってはいけないファイル（.env / data/real / data/snapshot.json / out/ など）が追跡されていないか
2. ファイル内容に、トークン・UUID（Notion の ID）・Notion/Claude の URL・メールアドレス等が無いか
3. config/denylist.local.txt（自分の名前・作品名など、1 行 1 語。Git 管理外）の語が含まれていないか

使い方: python3 scripts/check_privacy.py        （全ファイルを検査）
        python3 scripts/check_privacy.py --staged （コミット予定の内容だけ検査。pre-commit 用）
"""
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SELF = "scripts/check_privacy.py"

FORBIDDEN_PATHS = [
    r"^\.env$", r"^\.env\.(?!example$)", r"^data/real/", r"^data/snapshot\.json$",
    r"^out/", r"^config/denylist\.local\.txt$", r"\.local\.(json|md|txt)$",
]
PATTERNS = {
    "Notion トークン": r"\b(ntn_|secret_)[A-Za-z0-9]{20,}",
    "API キー類": r"\b(sk-[A-Za-z0-9]{20,}|AIza[0-9A-Za-z_\-]{30,}|gh[pousr]_[A-Za-z0-9]{30,}|xox[baprs]-[A-Za-z0-9-]{10,})",
    "UUID（Notion の ID の可能性）": r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b",
    "32 桁の ID": r"\b[0-9a-f]{32}\b",
    "Notion の URL": r"https?://(www\.)?notion\.(so|site)/\S+",
    "Claude アーティファクトの URL": r"claude\.ai/(code/)?artifact/\S+",
    "メールアドレス": r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b",
    "秘密鍵": r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
}
SKIP_DIRS = {".git", "__pycache__", "node_modules"}
ALLOW_EMAIL = {"you@example.com", "user@example.com"}


def public_links():
    """config/public_links.txt（1 行 1 件）に書いた、公開してよいリンクの一覧。"""
    p = ROOT / "config" / "public_links.txt"
    if not p.is_file():
        return []
    return [l.strip() for l in p.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]


def git(*args):
    try:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    except Exception:
        return None


def candidate_files(staged):
    if staged:
        out = git("diff", "--cached", "--name-only", "--diff-filter=ACM")
        return [f for f in (out or "").splitlines() if f]
    # Git 管理下: 追跡中のファイル＋まだ追加していないが .gitignore 対象でないファイル
    # （.gitignore で除外された実データ・.env は、公開物ではないので検査しない）
    out = git("ls-files", "--cached", "--others", "--exclude-standard")
    if out is not None:
        return sorted(set(f for f in out.splitlines() if f))
    # Git 管理外（ZIP を配る場合など）: 全ファイルを見る。ただし、手元の実データ用ファイルは
    # 検査対象から外し、「公開物に含めないで」と注意だけ出す
    files = []
    for p in ROOT.rglob("*"):
        rel = p.relative_to(ROOT)
        if p.is_file() and not (set(rel.parts) & SKIP_DIRS):
            files.append(rel.as_posix())
    return files


def main():
    staged = "--staged" in sys.argv
    problems = []
    files = candidate_files(staged)
    in_git = git("rev-parse", "--is-inside-work-tree") is not None

    local_only = []
    for f in files:
        for pat in FORBIDDEN_PATHS:
            if re.search(pat, f):
                if in_git:
                    # 追跡中か（--cached に含まれるか）だけを問題にする。手元にあること自体は問題ない
                    tracked = git("ls-files", "--error-unmatch", f)
                    if tracked is not None:
                        problems.append("%s: 追跡してはいけないファイルです" % f)
                else:
                    local_only.append(f)
                break
    if local_only:
        files = [f for f in files if f not in local_only]
        print("注意: Git 管理外のフォルダです。次は自分用のファイルなので、配布物（ZIP など）に含めないでください:")
        for f in local_only:
            print("  -", f)

    deny = []
    dp = ROOT / "config/denylist.local.txt"
    if dp.exists():
        deny = [w.strip() for w in dp.read_text(encoding="utf-8").splitlines() if w.strip() and not w.startswith("#")]

    for f in files:
        if f == SELF:
            continue
        p = ROOT / f
        if not p.is_file():
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue  # バイナリは対象外（画像を入れない運用）
        for url in public_links():  # 配布元が公開を決めたリンクだけは、検査から外す
            text = text.replace(url, " " * len(url))
        for label, rx in PATTERNS.items():
            for m in re.finditer(rx, text):
                if label == "メールアドレス" and m.group(0) in ALLOW_EMAIL:
                    continue
                line = text.count("\n", 0, m.start()) + 1
                problems.append("%s:%d: %s の疑い" % (f, line, label))  # 値そのものは表示しない
        for w in deny:
            if w in text:
                problems.append("%s: denylist の語を含みます（%d 文字の語）" % (f, len(w)))

    if problems:
        print("個人情報・認証情報の混入の疑いがあります:")
        for x in problems:
            print(" -", x)
        print("\n公開・コミットの前に取り除いてください。")
        sys.exit(1)
    print("OK: 問題は見つかりませんでした（%d ファイルを検査%s）" % (len(files), "、denylist あり" if deny else ""))


if __name__ == "__main__":
    main()
