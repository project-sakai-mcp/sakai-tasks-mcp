# 開発方法README
## Sakai-Tasks-MCP

大学の Sakai LMS から課題・小テスト・お知らせ・講義資料を安全に取得し、Claude Desktop や Cursor 等の AI アシスタントと連携する MCP (Model Context Protocol) サーバーです。

---

## 📚 ドキュメント一覧 (Documentation)

開発を始める場合、以下のドキュメントを参照してください。ドキュメントには使うツールや言語の詳しい使い方の説明を書いていないので、AIに聞きながら開発を進めてください。ご質問はissueのコメントにお書きください。

* **[開発者ガイド (`docs/guide.md`)](docs/guide.md)**:
  * 本プロジェクトの目的や仕組みをまとめて書いてあります。
* **[全体設計書 (`docs/architecture.md`)](docs/architecture.md) [github pages版](https://project-sakai-mcp.github.io/sakai-tasks-mcp/)**:
  * システム全体のアーキテクチャ、全共通データモデル（Pydantic）、各モジュール・関数の入出力型定義、および GUI 仕様。長いので全部は読まず、担当するコードの要件を確認するために使います。
* **[Sakai API 完全リファレンス (`docs/sakai_api_reference.md`)](docs/sakai_api_reference.md)**:
  * Sakai Direct REST API のエンドポイント一覧、レスポンス JSON 構造、日時形式の注意点。
* **[認証・セッション仕様書 (`docs/auth_and_session_spec.md`)](docs/auth_and_session_spec.md)**:
  * 大学 SSO (Shibboleth / Microsoft 365) 認証、Cookie ライフサイクル、および WebView2 による自動素通り認証の仕様。
* **[github pages版architecture.md](https://project-sakai-mcp.github.io/sakai-tasks-mcp/)**:
  * architecture.md をwebサイトとして表示したもの

---

## 🛠️ 開発環境のセットアップ

前提条件: **Python 3.10 以上**

```bash
# 1. リポジトリのクローンと移動
git clone https://github.com/project-sakai-mcp/sakai-tasks-mcp.git
cd sakai-tasks-mcp

# 2. 仮想環境の作成と有効化
python -m venv .venv
source .venv/bin/activate   # Windows (PowerShell): .\.venv\Scripts\Activate.ps1
                            # Windows (cmd): .\.venv\Scripts\activate.bat

# 3. 依存パッケージのインストール
pip install -r requirements.txt
```

---

## 🚀 開発ワークフロー

本プロジェクトでは、1ファイルに対し 1つの Issue を用意しています。

### 1. 担当 Issue の選択 & Assignees 登録
* 実装したいファイルの Issue を選び、右側メニューの **Assignees（担当者）** に自分を設定します（※すでに担当者がいる Issue は選べません）。

### 2. Issue からブランチを作成
* GitHub の Issue 画面（右側 Development セクションの「Create a branch」等）から作業ブランチを作成します。
  * **Branch source は必ず `dev` を選択してください**（デフォルトが `main` になっている場合は切り替えてください）。
  * ブランチ名は `<番号>-feat-<issue名>` とします。
    * 例: issueタイトルが `[feat] src-models #31` の場合 → `31-feat-src-models`

### 3. ローカルで作業ブランチに切り替え
* GitHub 上でブランチを作成したら、ローカル環境で最新情報を取得してブランチを切り替えます。
```bash
git fetch origin
git switch 31-feat-src-models   # または git checkout 31-feat-src-models
```

### 4. 仕様の確認 & 実装
* `docs/architecture.md`（[GitHub Pages版](https://project-sakai-mcp.github.io/sakai-tasks-mcp/)）の **第 1〜3 章**（全体像・共通モデル）と **自分の担当ファイルのセクション** を確認し、コードを実装します。

### 5. 変更のコミット & プッシュ
* 実装が完了したら、変更内容をコミットしてリモートにプッシュします。
```bash
git add <変更したファイル>
git commit -m "feat: <実装内容の簡潔な説明>"
git push origin 31-feat-src-models
```

### 6. Pull Request (PR) の作成
* GitHub のリポジトリ画面から Pull Request を作成します。
  * **重要**: PR の宛先（base ブランチ）が **`dev`** になっていることを必ず確認してください（`base: dev` ← `compare: 31-feat-src-models`）。
  * PR の説明欄に、対応した Issue 番号（例: `Closes #31`）を記載します。

### 7. レビュー & マージ
* リポジトリの管理人が内容を確認（レビュー）し、問題がなければ `dev` ブランチへマージします。

---

## ⚠️ 実装時の重要ルール

* **stdio 汚染厳禁**:
  * 通常の `print()` 出力は MCP の標準入出力通信（JSON-RPC）を破壊します。デバッグやログ出力には必ず `logging` または `sys.stderr` を使用してください。
