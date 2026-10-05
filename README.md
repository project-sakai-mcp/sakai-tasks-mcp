# Sakai Tasks MCP

大学の Sakai LMS と AI をつなぐ MCP サーバ

![Sakai Tasks MCP の AI チャット連携の様子](docs/release/chat_full.png)

[Web サイト版ガイドはこちら](https://project-sakai-mcp.github.io/sakai-tasks-mcp/release/)

---

## 概要

**Sakai Tasks MCP** は、大学で利用されている Sakai LMS（京都大学 PandA、名古屋大学 TACT など）から、通知や課題の締め切り、講義資料などを取得し、Claude Desktop や Cursor などの AI アシスタントと連携するための MCP (Model Context Protocol) サーバーです。

「今週の課題の締切は？」「重要なお知らせはある？」「講義資料をダウンロードして」と AI に話しかけたら Sakai 上の情報を取得できるようにします。

---

## 機能

AI が呼び出せる MCP ツール一覧です。

| ツール名 | 説明 |
| :--- | :--- |
| `get_upcoming_deadlines` | 締切がある課題・小テストを取得し、期限順に整理して返します。 |
| `get_course_dashboard` | 指定した講義の状況（課題、小テスト、直近のお知らせ、授業資料）を取得します。 |
| `get_announcements` | 通知を取得します。 |
| `get_assignments` | 課題の一覧または詳細（提出期限、指示文、添付資料など）を取得します。 |
| `get_quizzes` | 小テスト・オンラインクイズの一覧や締切情報を取得します。 |
| `get_calendar_events` | カレンダーに登録されたスケジュールやイベント予定を取得します。 |
| `get_course_materials` | 講義の配布資料リンク・フォルダ一覧を取得します。 |
| `download_material` | 講義資料や添付ファイルを指定のローカルフォルダにダウンロードします。 |
| `list_courses` | 所属している講義一覧と講義IDを取得します。 |
| `open_settings` | 大学ドメインの変更や講義ごとの情報開示ポリシーなどを設定する GUI 画面を起動します。 |
| `check_auth_status` | 大学ポータルのログインセッションが有効かどうかを確認します。 |

---

## Windows インストール

[Windows 版 圧縮ファイルをダウンロード](https://github.com/project-sakai-mcp/sakai-tasks-mcp/releases/latest/download/sakai-tasks-mcp-windows.zip)

### セットアップ手順

1. ダウンロードした ZIP ファイルを任意のフォルダ（例: `C:\tools` など）に解凍します。
2. 解凍先フォルダ内の `run.bat` の絶対パスを確認します。
   - **パスの確認方法:** エクスプローラーで解凍先フォルダを開き、`run.bat` を **右クリック** して「**パスのコピー**」を選択すると、クリップボードに絶対パスがコピーされます。
3. お使いの AI アプリ（Claude Desktop, Cursor 等）の MCP 設定に登録します。
   - **設定 JSON の例:**
     ```json
     {
       "mcpServers": {
         "sakai-tasks": {
           "command": "cmd.exe",
           "args": [
             "/c",
             "<あなたが解凍したrun.batファイルのパス>"
           ]
         }
       }
     }
     ```
     ※ パス内のバックスラッシュ（`\`）は、JSON 内では `\\` のように重ねてエスケープしてください（例: `C:\\tools\\sakai-tasks-mcp-windows\\run.bat`）。
   - **AI に設定ファイルへの追記を依頼する場合のプロンプト例:**
     ```text
     あなたのMCP設定ファイルに、以下のMCPサーバーを追加してください。
     名前: sakai-tasks
     コマンド: cmd.exe
     引数: ["/c", "<あなたが解凍したrun.batファイルのパス>"]
     ```
4. AI アプリを再起動します。
5. AI のチャット欄で「**初期設定を開いて**」と指示します。
6. 設定画面が開いたら、所属大学のドメイン（例: `tact.ac.thers.ac.jp` や `panda.ecs.kyoto-u.ac.jp` 等）を登録し、「保存して閉じる」を押します。
7. 設定画面が閉じて少しあとにログイン画面が開くので、そこでログインを完了させてください。

---

## macOS インストール

[macOS 版 圧縮ファイルをダウンロード](https://github.com/project-sakai-mcp/sakai-tasks-mcp/releases/latest/download/sakai-tasks-mcp-macos.tar.gz)

### セットアップ手順

1. ダウンロードしたアーカイブ（`.tar.gz`）を任意のフォルダ（例: `/Users/username/tools` や `~/tools` など）に展開（解凍）します。
2. 解凍先フォルダ内の `run.sh` の絶対パスを確認します。
   - **パスの確認方法:** Finder で解凍先フォルダを開き、`run.sh` を **右クリック** して「**パス名をコピー**」を選択します。
3. お使いの AI アプリ（Claude Desktop, Cursor 等）の MCP 設定に登録します。
   - **設定 JSON の例:**
     ```json
     {
       "mcpServers": {
         "sakai-tasks": {
           "command": "<あなたが解凍したrun.shファイルのパス>",
           "args": []
         }
       }
     }
     ```
   - **AI に設定ファイルへの追記を依頼する場合のプロンプト例:**
     ```text
     あなたのMCP設定ファイルに、以下のMCPサーバーを追加してください。
     名前: sakai-tasks
     コマンド: <あなたが解凍したrun.shファイルのパス>
     ```
4. AI アプリを再起動します。
5. AI のチャット欄で「**初期設定を開いて**」と指示します。
6. 設定画面が開いたら、所属大学のドメイン（例: `tact.ac.thers.ac.jp` や `panda.ecs.kyoto-u.ac.jp` 等）を登録し、「保存して閉じる」を押します。
7. 設定画面が閉じて少しあとにログイン画面が開くので、そこでログインを完了させてください。

---

## 📚 ドキュメント & 開発者向け情報

- **[全体設計書 (`docs/architecture.md`)](docs/architecture.md)** / **[Web 版](https://project-sakai-mcp.github.io/sakai-tasks-mcp/)**
- **[開発者ガイド (`docs/guide.md`)](docs/guide.md)**
- **[Sakai API リファレンス (`docs/sakai_api_reference.md`)](docs/sakai_api_reference.md)**
- **[認証・セッション仕様書 (`docs/auth_and_session_spec.md`)](docs/auth_and_session_spec.md)**
