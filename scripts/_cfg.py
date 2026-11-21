"""設定の読み込み（共通部品。直接は実行しない）。標準ライブラリのみ。

config/<名前>.json を読み、config/<名前>.local.json（Git 管理外・自分用の上書き）があれば重ねる。
→ テンプレートを更新しても、自分の列名や設定が上書きされない。
"""
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _merge(base, over):
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _merge(base[k], v)
        else:
            base[k] = v
    return base


def load(name, root=None):
    root = pathlib.Path(root) if root else ROOT
    base = json.loads((root / "config" / (name + ".json")).read_text(encoding="utf-8"))
    local = root / "config" / (name + ".local.json")
    if local.exists():
        try:
            _merge(base, json.loads(local.read_text(encoding="utf-8")))
        except ValueError:
            raise SystemExit("config/%s.local.json が正しい JSON ではありません。直すか、削除してください。" % name)
    return base
