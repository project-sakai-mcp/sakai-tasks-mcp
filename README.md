# 開発方法README
## Sakai-Tasks-MCP

大学の Sakai LMS から課題・小テスト・お知らせ・講義資料を安全に取得し、Claude Desktop や Cursor 等の AI アシスタントと連携する MCP (Model Context Protocol) サーバーです。

---

## 📚 ドキュメント一覧 (Documentation)

開発を始める前に、以下のドキュメントを参照してください。

* **[github pages版ドキュメント](https://sayt25606-rgb.github.io/sakai-tasks-mcp/)**
* **[全体設計書 (`docs/architecture.md`)](docs/architecture.md)**:
  * システム全体のアーキテクチャ、全共通データモデル（Pydantic）、各モジュール・関数の入出力型定義、および GUI 仕様。長いので全部は読まず、担当するコードの要件を確認するために使います。
* **[開発者ガイド (`docs/guide.md`)](docs/guide.md)**:
  * 本システムの動作イメージ、使用技術の選定理由、および講義別 AI 利用ポリシーの仕組み。
* **[Sakai API 完全リファレンス (`docs/sakai_api_reference.md`)](docs/sakai_api_reference.md)**:
  * Sakai Direct REST API のエンドポイント一覧、レスポンス JSON 構造、日時形式の注意点。
* **[認証・セッション仕様書 (`docs/auth_and_session_spec.md`)](docs/auth_and_session_spec.md)**:
  * 大学 SSO (Shibboleth / Microsoft 365) 認証、Cookie ライフサイクル、および WebView2 による自動素通り認証の仕様。

---

## 🛠️ 開発環境のセットアップ

```bash
# 1. 仮想環境の作成と有効化
python -m venv .venv
source .venv/bin/activate   # Windows: .\.venv\Scripts\activate

# 2. 依存パッケージのインストール
pip install -r requirements.txt
```

---

## 🚀 開発ワークフロー

本プロジェクトでは、1ファイルに対し 1つの Issue を用意しています。

1. **担当 Issue の選択 & Assignees 登録**:
   * 実装したいファイルの Issue を選び、右側メニューの **Assignees（担当者）** に自分を設定します。すでに担当者がいるissueは選べません。
2. **Issue からブランチを作成**:
   * GitHub の Issue 画面（Development セクションの「Create a branch」等）から作業ブランチを作成し、その中で作業をします。**Branch Sourceはdevを選択してください**
   * branch名は次のように決めます。issueタイトルが
   "[feat] issue名 #番号"
   になっているので、これを使ってブランチ名は
   feat/番号-issue名
   のようにします。例えば
   issueタイトルが "[feat] src-server #1" の場合、ブランチ名は次のようになります
   feat/1-src-server
3. **仕様の確認 & 実装**:
   * `docs/architecture.md` の **第 1〜3 章**（全体像・共通モデル）と **自分の担当ファイルのセクション** を確認し、コードを実装します。
4. **Pull Request (PR) の作成**:
   * 実装が完了したら、該当 Issue を関連付けて `dev` ブランチに向けて Pull Request を作成します。
5. **Code Owner によるレビュー & マージ**:
   * Code Owner がコードレビューおよび承認を行い、`dev` ブランチへマージされます。

---

## ⚠️ 実装時の重要ルール

* **stdio 汚染厳禁**:
  * 通常の `print()` 出力は MCP の標準入出力通信（JSON-RPC）を破壊します。デバッグやログ出力には必ず `logging` または `sys.stderr` を使用してください。
