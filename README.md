# 創作ダッシュボード テンプレート

Notion に書いた創作の進捗（小説・漫画・イラスト）と、即売会イベントの準備を、1 枚の HTML で見られるようにするテンプレートです。

- **継続を見る**: 今週・今月・今年の「進捗あり」日数、週別／月別グラフ、カレンダー
- **イベント準備を見る**: イベントごとの工程と期限、今後のタスク
- **まずは Notion だけで始める（基本・設定なし）**: Notion の「創作ダッシュボード（サンプル）」を複製するだけ。記録・タスク・イベントの入力と、カレンダー・ボード・週ごとのグラフでの閲覧は、Notion 上で行います（Notion の公式サンプルページにある「使い方マニュアル」が入口です。サンプルのリンク: https://malleable-azimuth-33d.notion.site/41f353dff09881cbb2eceafcd9bebfbc ）。スマホの Notion アプリでの見え方は未確認です
- **AI に頼むだけで使える（任意・メイン）**: Notion に接続できて、コードを実行できる AI に「ダッシュボードを更新して」と頼むだけ。ターミナルも設定ファイルの編集も不要です。主な対象は ChatGPT を使う人です。通しの確認は Claude で行い、ChatGPT はダミーデータで確認済みです（実験的。`manual/10-chatgpt-guide.md`）。ChatGPT の場合、画面（`index.html`）はダウンロードして開く形になります（専用リンクで置く機能は見つかっていません）。Gemini は未確認の参考扱いです（`manual/03-connectors.md`）。画面が Notion を直接読む、Claude 専用の上級ルートもあります（`manual/08-claude-live.md`）
- **ChatGPT と Notion だけで作る（実験的）**: 接続から画面を開くまでの手順は `manual/10-chatgpt-guide.md`。ダミーデータで 1 回だけ通し確認しています
- **PC だけでも動く（任意）**: AI を使わず、自分のパソコンで Python（標準ライブラリのみ）を実行する動線もあります
- **個人情報を守る設計**: 読み取り専用の接続、実データは Git 管理外、出力 HTML は通信禁止、非公開で使う運用、公開前の自動チェック（`manual/07-privacy.md`）

> ⚠️ 実際のデータで作った `out/index.html` は共有しないでください。共有・公開するのはこのテンプレートだけです。

> 📖 **はじめての方は `manual/01-manual.md`（マニュアル）から。** 準備の手順、画面の見方、全ファイルの説明、困ったときの対処をまとめています。

## まず試す（Notion なし・ダミーデータ）

AI に次のように頼みます（AI にこのフォルダを渡した状態で）。

```
AGENTS.md に従って、ダミーデータでダッシュボードを作って見せてください（build.py --sample）。
```
PC で自分で動かすなら `python3 scripts/build.py --sample` のあと、`out/index.html` をブラウザで開きます（Python 3.8 以上）。

## 自分の Notion で使う

### 動線 W: AI で完結（メイン）
1. **Notion を準備する** — `manual/02-notion-setup.md` の表のとおりに 3 つの DB を作る（列名は `config/schema.json` に合わせる）。
2. **AI に Notion を接続する** — 3 つの DB だけを共有し、権限は可能なら読み取りのみ。
3. **頼む** — `manual/04-ai-prompts.md` の「ダッシュボードを更新して見せる」をコピペ。画面は非公開のまま渡されます。

入力は Notion に 1 日 1 行（30 秒）。更新は「更新して」と頼むだけです。

### 動線 P: PC のスクリプト（任意・AI に実データを渡したくないとき）
1. `manual/02-notion-setup.md` で、DB と**読み取り専用のトークン**を用意する。
2. `.env.example` を `.env` にコピーし、トークンと DB の ID を入れる（**最初に触るファイルは `.env` だけ**）。
3. `python3 scripts/fetch_notion.py` → `python3 scripts/make_datasets.py` → `python3 scripts/build.py`
4. `out/index.html` をブラウザで開く。

## AI に手伝ってもらう
`manual/04-ai-prompts.md` にコピペ用のプロンプトがあります。最初に `AGENTS.md` を読ませてください。動線 W は Notion の中身が AI サービスを通ります。画面に本文を出す `include_text` は既定でオフです。Notion をはじめて使う人は `manual/02-notion-setup.md` の A、変えたいときは `manual/06-customize.md`、接続の権限は `manual/03-connectors.md`、Claude 専用で画面が Notion を直接読む上級ルートは `manual/08-claude-live.md`、人の目で確かめる項目は `manual/05-checklist.md`、雛形を配る人は `reference/release-checklist.md`、詳細は `manual/07-privacy.md` を見てください。

## GitHub で共有するとき

1. `config/denylist.local.txt` に自分の名前・作品名などを 1 行 1 語で書く（Git に入りません）。
2. `git config core.hooksPath .githooks` で、コミット時の自動チェックを有効にする。
3. `python3 scripts/check_privacy.py` が `OK` になることを確認する。
4. まず Private で作成し、中身を確認してから Public にする。

## フォルダ構成

```
├─ AGENTS.md / CLAUDE.md / GEMINI.md   AI への共通指示
├─ .env.example                        認証情報のひな形（本物の .env は Git 管理外）
├─ config/                             設定（settings / schema / columns。自分用は *.local.json）
├─ tests/                              自動テスト
├─ scripts/                            fetch_notion / make_datasets / build / check_privacy / make_sample / make_bundle
├─ chatgpt-bundle.txt                  ChatGPT に貼る「まとめファイル」（make_bundle.py で作る）
├─ template/dashboard.html             画面のひな形（通信しない）
├─ data/sample/                        ダミーデータ（これだけ公開してよい）
├─ manual/                             読むマニュアル（番号順。入口は manual/README.md）
├─ reference/                          通常は読まない資料（設計・形式の仕様・配布者用）
├─ CHANGELOG.md                        変更履歴と移行手順
├─ .githooks/ .github/workflows/       公開前の自動チェック
└─ out/ data/real/ data/snapshot.json  実データ（Git 管理外）
```

## 動作確認の状況
- ダミーデータでの画面生成、変換処理のテスト、個人情報チェックは作成時に確認済み。
- 自動テスト（`python3 -m unittest discover -s tests`、22 件）は通っています。
- **動線 W は、Claude とテスト用 Notion（ダミーデータ）で通し確認済み**です（件数の一致、列名のずれで警告／停止、Notion 内の指示文に従わないこと）。**ChatGPT は、ダミーデータで 1 回だけ通し確認**しました（`manual/09-chatgpt.md`。実験的）。**Gemini は未確認**です。
- **動線 P の本番通信（`fetch_notion.py` と実際のトークン）は未検証**です。初回は `--selftest` で変換部分を確認してください。
- 別ワークスペースでの雛形の複製確認、Notion の共有設定の確認は未実施です（`reference/release-checklist.md`）。
- 同じ日に複数ページがある場合の集計は、疑似データで確認済みです（画面は実ブラウザ未確認）。
- 別のアカウント・別の AI での通し確認は未実施です。

## ライセンス
MIT ライセンスです（`LICENSE`）。自由に使い、変更し、配ることができます。**無保証**です。著作権表示の名前を自分の名前や屋号にしたい人は、`LICENSE` の 3 行目を書き換えてください（個人名を出したくなければ、そのままで構いません）。
