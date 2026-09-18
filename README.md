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
* 本ドキュメント末尾の「開発のしやすさ（難易度表）」を参考に実装したいファイルの Issue を選び、右側メニューの **Assignees（担当者）** に自分を設定します（※すでに担当者がいる Issue は選べません）。

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

---

## 📊 開発のしやすさ（全29ファイル難易度表）

`src/` ディレクトリ配下の全29ファイルにおける実装難易度および依存関係に基づく一覧です。**上から順に着手しやすくなっています。** 担当する Issue の選定にご活用ください。

| 分類 | ファイル | 概要・役割 |
| :--- | :--- | :--- |
| **データ変換・定数** | `src/models.py` | 共通データモデル・Enum 定義（※作成済み） |
| | `src/client/endpoints.py` | Sakai API のエンドポイント URL 定数定義 |
| | `src/client/parsers/base.py` | 日時変換・HTML サニタイズ等の共通ユーティリティ |
| | `src/client/parsers/announcement_parser.py` | お知らせ API の JSON を `Announcement` に変換 |
| | `src/client/parsers/calendar_parser.py` | カレンダー API の JSON を `CalendarEvent` に変換 |
| | `src/client/parsers/favorite_parser.py` | ポータル HTML からお気に入り講義一覧を抽出 |
| | `src/client/parsers/course_parser.py` | 講義サイト一覧 API の JSON を `CourseSite` に変換 |
| | `src/client/parsers/assignment_parser.py` | 課題 API の JSON を `SakaiTask`（課題）に変換 |
| | `src/client/parsers/quiz_parser.py` | テスト・クイズ API の JSON を `SakaiTask`（クイズ）に変換 |
| | `src/client/parsers/content_parser.py` | 授業資料・リソース API の JSON を `CourseMaterial` に変換 |
| | `src/policy/policy_filter.py` | ポリシーに応じたデータのマスキング・除外処理 |
| **設定・データ連携** | `src/config.py` | 設定ファイルの永続化（JSON 入出力）およびポリシー管理 |
| | `src/gui/data_builder.py` | GUI 設定画面用の表示データ構築とソート処理 |
| | `src/auth/cookie_storage.py` | セッション Cookie の暗号化（keyring / Fernet）と保存 |
| | `src/auth/session_checker.py` | Sakai API へのセッション有効性確認リクエスト |
| | `src/client/sakai_client.py` | 各パーサーを統括し Sakai REST API と通信するクライアント |
| **パッケージ初期化**<br/>(Facade / 公開定義) | `src/__init__.py` | パッケージ初期化 |
| | `src/policy/__init__.py` | ポリシーモジュールの公開関数 export |
| | `src/client/parsers/__init__.py` | パーサー群の公開関数 export |
| | `src/client/__init__.py` | クライアントモジュールの公開クラス export |
| | `src/auth/__init__.py` | 認証モジュールの Facade export |
| | `src/gui/__init__.py` | GUI モジュールの公開関数 export |
| **GUI・HTML画面** | `src/gui/templates/initial_setup.html` | 初期セットアップ用 HTML 画面テンプレート |
| | `src/gui/templates/settings.html` | 講義別ポリシー設定用 HTML 画面テンプレート |
| | `src/gui/api.py` | GUI（WebView）と Python ロジック間の連携 API ブリッジ |
| | `src/gui/settings_window.py` | 設定ダイアログウィンドウの表示・制御 |
| **認証・システムコア** | `src/auth/webview_auth.py` | WebView2 による大学 SSO ログイン画面制御・Cookie 抽出 |
| | `src/auth/session_manager.py` | 認証セッション全体の調停・非同期排他制御（Lock） |
| | `src/server.py` | FastMCP サーバー本体。ツール公開と stdio 通信制御 |
