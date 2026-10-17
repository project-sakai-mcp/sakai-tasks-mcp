# Sakai Tasks MCP

Unofficial MCP server for Sakai LMS.

[日本語インストールページ](https://project-sakai-mcp.github.io/sakai-tasks-mcp/)

---

## Overview

**Sakai Tasks MCP** enables desktop AI assistants to access Sakai LMS instances via MCP.

It features per-course access control to customize information disclosure to AI, along with automatic session handling that pops up a WebView login window whenever authentication is required.

---

## Available MCP Tools

| Tool | Description |
| :--- | :--- |
| `get_upcoming_deadlines` | Retrieves pending assignments and quizzes, sorted by deadline. |
| `get_course_dashboard` | Fetches an overview of a specific course (deadlines, recent announcements, materials). |
| `get_announcements` | Fetches announcements from courses or system-wide. |
| `get_assignments` | Retrieves assignment lists or details (due dates, instructions, attachments). |
| `get_quizzes` | Retrieves online quizzes and submission deadlines. |
| `get_calendar_events` | Fetches calendar schedules and events. |
| `get_course_materials` | Lists folders and download links for course materials. |
| `download_material` | Downloads course materials or attachments to a local directory. |
| `get_unread_messages_and_forums` | Retrieves unread messages and forum discussion counts with direct links. |
| `list_courses` | Lists enrolled courses and their site IDs. |
| `open_settings` | Opens the configuration GUI (university domain, course disclosure policies). |
| `get_settings` | Gets current configuration settings (domain, per-course AI policies, limits). |
| `check_auth_status` | Checks whether the login session is currently active. |

---

## Download Pre-built Binaries

You can download ready-to-use packages from [GitHub Releases](https://github.com/project-sakai-mcp/sakai-tasks-mcp/releases/latest):
- **Windows**: [sakai-tasks-mcp-windows.zip](https://github.com/project-sakai-mcp/sakai-tasks-mcp/releases/latest/download/sakai-tasks-mcp-windows.zip)
- **macOS**: [sakai-tasks-mcp-macos.tar.gz](https://github.com/project-sakai-mcp/sakai-tasks-mcp/releases/latest/download/sakai-tasks-mcp-macos.tar.gz)

Extract the archive to any directory on your computer.

---

## Configuration Examples

Add `sakai-tasks` to your AI client's MCP configuration. Replace `<PATH_TO_EXTRACTED_FOLDER>` with the absolute path where you extracted the release package.

### 1. Claude Desktop

**Configuration File Location:**
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`

#### Windows
```json
{
  "mcpServers": {
    "sakai-tasks": {
      "command": "cmd.exe",
      "args": [
        "/c",
        "C:\\path\\to\\sakai-tasks-mcp\\run.bat"
      ]
    }
  }
}
```

#### macOS
```json
{
  "mcpServers": {
    "sakai-tasks": {
      "command": "/path/to/sakai-tasks-mcp/run.sh",
      "args": []
    }
  }
}
```

---

### 2. Cursor

**Configuration File Location:**
- **Project Scope**: `.cursor/mcp.json` in your workspace root
- **Global Scope**:
  - **Windows**: `%USERPROFILE%\.cursor\mcp.json`
  - **macOS / Linux**: `~/.cursor/mcp.json`

#### Windows
```json
{
  "mcpServers": {
    "sakai-tasks": {
      "command": "cmd.exe",
      "args": [
        "/c",
        "C:\\path\\to\\sakai-tasks-mcp\\run.bat"
      ]
    }
  }
}
```

#### macOS
```json
{
  "mcpServers": {
    "sakai-tasks": {
      "command": "/path/to/sakai-tasks-mcp/run.sh",
      "args": []
    }
  }
}
```

---

### 3. Google Antigravity

**Configuration File Location:**
- `~/.gemini/config/mcp_config.json` (or `plugins/<plugin_name>/mcp_config.json`)

```json
{
  "mcpServers": {
    "sakai-tasks": {
      "command": "cmd.exe",
      "args": [
        "/c",
        "C:\\path\\to\\sakai-tasks-mcp\\run.bat"
      ]
    }
  }
}
```
*(On macOS, use `"command": "/path/to/sakai-tasks-mcp/run.sh"` with `"args": []`)*

---

## Initial Setup & Authentication

1. Restart your AI client after saving the configuration.
2. In the AI chat prompt, type:
   > *"Open initial setup"* or *"Open settings"*
3. The configuration GUI will pop up. Enter your university's Sakai domain or select it from the suggestions list.
4. Changes are saved automatically. Close the configuration window.
5. Ask your AI assistant any Sakai-related question.
6. A login window will automatically pop up. Log in with your university account credentials.
7. Once logged in, the window closes automatically, your session cookies are securely stored in your OS keyring, and the AI will proceed to answer your request.

---

## Contributing & Bug Reports

Contributions and suggestions are warmly welcomed!
- For setup instructions, testing guidelines, and PR workflow, see [CONTRIBUTING.md](CONTRIBUTING.md).
- To report bugs or propose improvements, please submit an issue using our [Bug Report Template](https://github.com/project-sakai-mcp/sakai-tasks-mcp/issues/new?template=bug_report.yml).

---

## License

This project is licensed under the [Apache License 2.0](LICENSE).
