# AGENTS.md - Sakai-Tasks-MCP プロジェクト概要 & ガイド

このドキュメントは、新しいチャットやAIエージェントが本プロジェクトの全体像・背景・アーキテクチャ・現在の進捗・開発手順を即座に把握し、スムーズに開発・改修を進められるようにまとめたものです。

---

## 1. プロジェクト概要

* **プロジェクト名**: `sakai-tasks-mcp` (旧称: `sakai-mcp`)
* **目的**: 大学等の教育機関で広く使われている LMS（Learning Management System）**「Sakai」** から、課題・小テスト・お知らせ等のタスク情報を取得し、AIモデル（Claude Desktop, Cursor, Antigravity, エージェント等）に **Model Context Protocol (MCP)** を通じて提供する。
* **配布形態**: **AIクライアントがサブプロセス（stdio）として直接起動できる単一の Windows 実行ファイル (`sakai-tasks-mcp.exe`)**
* **利用技術**: Python 3.12+, FastMCP (`mcp`), `httpx` / `requests`, `pywebview` (認証用), `PyInstaller` (配布用バイナリ化)

---

## 2. 背景とリファレンス (Comfortable Sakai)

京都大学等で学生向けに開発・運用されているブラウザ拡張機能 **[Comfortable Sakai (kyoto-u/comfortable-sakai)](https://github.com/kyoto-u/comfortable-sakai)** (MIT License) を参考に設計されています。

* **Fork ではなく新規リポジトリでの移植アプローチ**:
  元リポジトリはブラウザ拡張機能（TypeScript/React/WebExtensions）ですが、本プロジェクトは MCP サーバー（Python）を目指しているため、Sakai Direct REST API 呼び出しとデータパース処理ロジックのみを Python 側に再実装・移植しています。
* **ライセンス遵守**:
  コード利用・再実装の際は MIT ライセンスに則り、リファレンス元としてクレジットを明記します。

---

## 3. 全体アーキテクチャと設計方針

AI クライアント（Claude Desktop 等）が **サブプロセスとして `sakai-tasks-mcp.exe` を stdio で起動** します。常駐プロセスは不要で、AI からの呼び出し時にオンデマンドで動作します。

```mermaid
flowchart TD
    subgraph AIAssistant ["AI クライアント (Claude Desktop / Cursor / エージェント)"]
        AI["AI モデル"]
    end

    subgraph MCPProcess ["sakai-tasks-mcp.exe (AIがサブプロセスとして起動 / stdio)"]
        MCPServer["MCP サーバー (FastMCP: stdio)"]
        AuthUI["認証WebView画面 (pywebview / Edge WebView2)"]
        SessionMgr["セッション / Cookie 管理 (JSESSIONID保存)"]
        SakaiClient["Sakai API クライアント (REST通信)"]

        MCPServer -->|セッション確認・要求| SessionMgr
        SessionMgr -.->|セッション切れ/初回時| AuthUI
        SessionMgr -->|Cookie注入| SakaiClient
        SakaiClient -->|データ整形| MCPServer
    end

    subgraph SakaiSystem ["大学 Sakai LMS"]
        SSO["大学統合認証 (SSO / 2段階認証 / CAS)"]
        DirectAPI["Sakai Direct REST API (/direct/...)"]
    end

    AI <-->|stdio (MCP Protocol)| MCPServer
    AuthUI -.->|初回・期限切れ時にログイン画面表示| SSO
    SakaiClient <-->|GET JSON| DirectAPI
```

### 主要コンポーネントの設計

1. **プロセスライフサイクル (サブプロセス起動 & stdio)**:
   * AI クライアントの設定（`claude_desktop_config.json` 等）に `sakai-tasks-mcp.exe` を登録するだけで、AI クライアント起動時やツール呼び出し時に自動的にサブプロセスとして起動・stdio 接続されます。
   * トレイ常駐等の常時起動プロセスが不要なため、リソース消費がなく、ユーザー管理もシンプルです。
2. **認証 / セッション管理 (`pywebview`)**:
   * 初回実行時やセッション切れを検知したタイミングで、Windows 標準の Edge (WebView2) を使った軽量ログインウィンドウを一時的にポップアップします。
   * 大学の SSO (Shibboleth, CAS, Microsoft 365) や 2 要素認証をユーザーがブラウザ上で完了すると、Cookie (`JSESSIONID`) を自動抽出し、ローカル（ユーザーデータ領域）に安全に保存してウィンドウを閉じます。
3. **Sakai Direct REST API 連携**:
   * `GET /direct/site.json` : 履修・所属講義一覧
   * `GET /direct/assignment/my.json` (または `site/{siteId}.json`) : 課題一覧
   * `GET /direct/sam_pub/context/{siteId}.json` : テスト・クイズ一覧
   * `GET /direct/announcement/user.json` : お知らせ一覧
4. **スタンドアロン配布 (`PyInstaller`)**:
   * Python 環境を持たない学生ユーザーでも、単一の `sakai-tasks-mcp.exe` をダウンロードして Claude Desktop の設定にパスを書くだけで使えるようにパッケージングします。

---

## 4. MCP ツール設計 (予定 & 実装済)

| ツール名 | 状態 | 説明 / 引数 |
| :--- | :--- | :--- |
| `add_numbers` | 実装済 (デモ用) | 2つの数値を足し算する疎通確認用ツール |
| `get_mock_assignments` | 実装済 (モック) | モックデータによる課題一覧取得 (`status`: `'open'\|'submitted'\|'all'`) |
| `list_courses` | 計画中 | 履修中・所属している講義名と ID 一覧を取得 |
| `get_assignments` | 計画中 | 指定科目（または全科目）の課題一覧を取得 |
| `get_quizzes` | 計画中 | 指定科目のテスト・小テスト一覧を取得 |
| `get_upcoming_deadlines` | 計画中 | 直近 $N$ 日以内に締切のある課題・小テストを統合して締切順に取得 |
| `check_auth_status` | 計画中 | ログインセッションの有効性を確認し、必要に応じて再ログインをトリガー |

---

## 5. リポジトリ構成

```text
sakai-tasks-mcp/
├── .venv/               # Python 仮想環境
├── docs/
│   └── sakai_api_reference.md # Sakai Direct REST API 完全リファレンス
├── README.md            # プロジェクトの概要説明
├── AGENTS.md            # 本ファイル（AI・開発者向けコンテキスト共有）
├── requirements.txt     # Python 依存関係
├── server.py            # MCP サーバー本体（FastMCP: stdio）
└── test_server.py       # MCP サーバー単体テスト用スクリプト
```

---

## 6. 開発進捗 & ロードマップ

- [x] **Phase 1: MCP サーバー基礎プロトタイプ**
  - Python FastMCP 環境のセットアップ
  - モックデータを用いた `server.py` および `test_server.py` の動作検証 (stdio)
- [ ] **Phase 2: Sakai REST API クライアント実装**
  - Comfortable Sakai のパースロジックを移植した Python クライアントモジュール作成
  - 講義一覧・課題・テスト・お知らせの取得・データモデル化
- [ ] **Phase 3: 認証 & セッション管理の実装**
  - `pywebview` による大学 SSO ログイン画面のポップアップ
  - Cookie (`JSESSIONID`) の取得・保存・自動再ログイン判定
- [ ] **Phase 4: 本番 MCP ツールの実装**
  - 実 API と連携した MCP ツール群（`list_courses`, `get_assignments`, `get_upcoming_deadlines` 等）の配線
- [ ] **Phase 5: 単一 .exe ビルド & 配布**
  - `PyInstaller` による Windows 単一 `sakai-tasks-mcp.exe` ビルド
  - Claude Desktop / Cursor 等からのサブプロセス直接起動テスト

---

## 7. 開発・実行手順

### 環境の準備
```bash
# 仮想環境の有効化 (Windows PowerShell)
.venv\Scripts\Activate.ps1

# 依存パッケージのインストール
pip install -r requirements.txt
```

### MCP サーバーの単体テスト
```bash
python test_server.py
```

### Claude Desktop / MCP クライアントへの登録例

#### 開発時 (Python 直接実行)
`claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "sakai-tasks": {
      "command": "Z:\\home\\sy\\MyPrograms\\web\\sakai-tasks-mcp\\.venv\\Scripts\\python.exe",
      "args": [
        "Z:\\home\\sy\\MyPrograms\\web\\sakai-tasks-mcp\\server.py"
      ]
    }
  }
}
```

#### 配布後 (単一 exe 実行)
```json
{
  "mcpServers": {
    "sakai-tasks": {
      "command": "C:\\path\\to\\sakai-tasks-mcp.exe"
    }
  }
}
```

---

## 8. AI エージェントへの開発上の留意点

* **標準入出力 (stdio) の厳守**:
  * MCP サーバーは stdio をプロトコル通信に利用するため、通常の `print()` などの標準出力汚染を行わないこと（ログは `stderr` またはファイルに出力）。
* **ヘッドレス / UI ポップアップ時の挙動**:
  * AI クライアントからサブプロセスとして起動されるため、初回ログイン時のみ `pywebview` ウィンドウを表示し、ログイン完了後は速やかにウィンドウを閉じてバックグラウンド処理に戻ること。
* **Sakai API のデータ仕様**:
  * 課題 (`/direct/assignment/...`) と テスト・クイズ (`/direct/sam_pub/...`) は Sakai 内部で別ツールとして管理されており、レスポンスのフィールド名（`dueTime` / `dueDate` / `closeTime`）やミリ秒/秒のタイムスタンプ形式が異なるため、統合モデル化の際は型変換に注意すること。
* **セッションのライフタイム**:
  * Sakai セッションは一定時間の無操作で切断されるため、API レスポンスのステータスコード（401/403やログインページへのリダイレクトHTML）を検知してセッション切れを適切にハンドリングすること。
