# まとめファイルを更新したときの流れ（配布する人向け）

まとめファイル（`chatgpt-bundle.txt`）の最新版は、**GitHub の公開リポジトリ**に置きます。利用者への知らせは、Notion のサンプルページの「お知らせ（更新情報）」に書きます。Notion に置いたファイルの入れ替えは、しません（複製した時点のコピーで、古くなることを前提にしています）。

## 手順
1. ファイルを直す（`AGENTS.md`・`scripts/`・`config/`・`template/` など、まとめファイルに入るもの）。
2. `VERSION` を上げ、`CHANGELOG.md` に書く（「Notion の移行」が要るかも書く）。
3. `python3 scripts/make_bundle.py` で、まとめファイルを作り直す。`--check` と `python3 -m pytest -q tests` を通す。
4. `python3 scripts/check_privacy.py` を通す（実データ・ID・認証情報が入っていないこと）。
5. GitHub に送る（`main`）。Actions の個人情報チェックが成功したことを確認する。
6. Notion のサンプルページの「お知らせ（更新情報）」を直す。
   - 「最新版」の版番号を新しくする。
   - 「更新の履歴」の先頭に 1 件足す（日付・版・何が変わったか・**入れ替えが必要か**）。
   - ダウンロードのリンクは、次の固定のもの。変えない。
     `https://github.com/Sabosabo457/creative-dashboard-template/blob/main/chatgpt-bundle.txt`
7. Notion のサンプルページの「ライセンス（MIT）」ページを、GitHub の `LICENSE` に合わせて書き直す（「最新の版」の番号と、ライセンス全文。変更がなくても、版番号は合わせる）。
8. 必要なら、`manual/10-chatgpt-guide.md` と Notion の使い方マニュアル 2-4 の説明を直す。

## 決まり
- お知らせには、**入れ替えが必要か**を必ず書く。不具合の修正は「入れ替えてください」、機能の追加は「任意」。
- Notion の移行（列や選択肢の変更）が要る更新は、手順を書く。
- 利用者のデータや、人が特定できる情報は、お知らせにもリポジトリにも書かない。
