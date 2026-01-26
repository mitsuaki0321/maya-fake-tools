---
title: ユーザー設定
hidden: true
parent: code_editor
parent_title: Code Editor
lang: ja
lang-ref: code_editor_settings
---

## 概要

このドキュメントでは、コードエディターのユーザー設定について説明します。

## 設定ファイルの場所

設定ファイルは、以下の場所に自動的に保存されます：

- Windows: `%MAYA_APP_DIR%/faketools_workspace/common/code_editor/config/user_settings.json`
- Mac: `~/Library/Preferences/Autodesk/maya/faketools_workspace/common/code_editor/config/user_settings.json`
- Linux: `~/maya/faketools_workspace/common/code_editor/config/user_settings.json`

※ 設定はエディタの設定画面から変更できます。直接JSONファイルを編集することも可能です。

## 設定項目

### エディタ設定 (editor)
コードエディタの表示と動作に関する設定です。

| 設定名 | デフォルト値 | 説明 |
|--------|------------|------|
| `font_family` | "Consolas" | エディタのフォント名 |
| `font_size` | 10 | エディタの文字サイズ |
| `tab_size` | 4 | タブキーを押したときの空白文字数 |
| `word_wrap` | true | 長い行を折り返して表示するか |
| `show_line_numbers` | true | 行番号を表示するか |
| `highlight_current_line` | true | カーソルがある行をハイライト表示するか |
| `auto_indent` | true | 改行時に自動でインデントを行うか |
| `theme` | "dark_modern" | カラーテーマ（dark_modern / dark_classic / light） |

### ターミナル設定 (terminal)
実行結果を表示するターミナルの設定です。

| 設定名 | デフォルト値 | 説明 |
|--------|------------|------|
| `font_family` | "Consolas" | ターミナルのフォント名 |
| `font_size` | 9 | ターミナルの文字サイズ |
| `max_lines` | 1000 | ターミナルに表示する最大行数 |
| `auto_scroll` | true | 新しい出力を自動でスクロールして表示するか |

### 検索設定 (search)
検索・置換機能の初期設定です。

| 設定名 | デフォルト値 | 説明 |
|--------|------------|------|
| `match_case` | false | 大文字・小文字を区別して検索するか |
| `whole_words` | false | 単語単位で検索するか |
| `use_regex` | false | 正規表現を使用して検索するか |
| `search_direction` | "down" | 検索方向（down: 下方向 / up: 上方向） |

### Maya連携設定 (maya)
Maya固有の機能に関する設定です。

#### ヘルプ設定 (maya.help)
コードエディターのコンテキストメニューより実行できる Maya コマンドのヘルプ表示に関する設定です。

| 設定名 | デフォルト値 | 説明 |
|--------|------------|------|
| `language` | "JPN" | Mayaヘルプの言語（JPN: 日本語 / ENU: 英語） |

### コマンドポート設定 (command_port)
外部ツールとの連携用の設定です。\
MCP Serverなどのツールと連携する場合に使用します。

| 設定名 | デフォルト値 | 説明 |
|--------|------------|------|
| `enabled` | false | コマンドポートを有効にするか |
| `port` | 7001 | 使用するポート番号 |

### 自動保存設定 (autosave)
作業内容の自動保存に関する設定です。

| 設定名 | デフォルト値 | 説明 |
|--------|------------|------|
| `enabled` | true | 自動保存を有効にするか |
| `interval_seconds` | 60 | 自動保存の間隔（秒） |
| `backup_on_change` | true | ファイル変更時にバックアップを作成するか |

### ファイル設定 (files)
ファイル管理に関する設定です。

| 設定名 | デフォルト値 | 説明 |
|--------|------------|------|
| `max_recent_files` | 20 | 最近使ったファイルの履歴の最大数 |

### レイアウト設定 (layout)
ウィンドウのレイアウトに関する設定です。

| 設定名 | デフォルト値 | 説明 |
|--------|------------|------|
| `terminal_at_bottom` | true | ターミナルの表示位置（true: 下 / false: 上） |

## 設定ファイルの例

```json
{
  "editor": {
    "font_family": "Consolas",
    "font_size": 12,
    "tab_size": 4,
    "word_wrap": true,
    "show_line_numbers": true,
    "highlight_current_line": true,
    "auto_indent": true,
    "theme": "dark_modern"
  },
  "terminal": {
    "font_family": "Consolas",
    "font_size": 10,
    "max_lines": 1000,
    "auto_scroll": true
  },
  "search": {
    "match_case": false,
    "whole_words": false,
    "use_regex": false,
    "search_direction": "down"
  },
  "maya": {
    "help": {
      "language": "JPN"
    }
  },
  "command_port": {
    "enabled": false,
    "port": 7001
  },
  "autosave": {
    "enabled": true,
    "interval_seconds": 60,
    "backup_on_change": true
  },
  "files": {
    "max_recent_files": 20
  },
  "layout": {
    "terminal_at_bottom": true
  }
}
```

## 設定の変更方法

### 方法1: エディタの設定画面から変更
1. コードエディターを開く
2. メニューから「設定」を選択
3. 各項目を変更して「保存」をクリック

### 方法2: JSONファイルを直接編集
1. 上記の設定ファイルの場所にあるJSONファイルをテキストエディタで開く
2. 値を変更して保存
3. コードエディターを再起動

## 設定のリセット

すべての設定をデフォルトに戻したい場合：
1. コードエディターを閉じる
2. `user_settings.json`ファイルを削除
3. コードエディターを再起動（自動的にデフォルト設定が作成されます）

## 設定のバックアップと復元

### バックアップ
現在の設定を別の場所に保存したい場合は、`user_settings.json`ファイルをコピーして保存してください。

### 復元
1. コードエディターを閉じる
2. バックアップしたJSONファイルを元の場所に上書きコピー
3. コードエディターを再起動

## トラブルシューティング

### 設定が反映されない場合
- Code Editor を完全に閉じて再起動してください
- JSONファイルの構文エラーがないか確認してください（カンマの位置、括弧の対応など）

### 設定ファイルが見つからない場合
- Code Editor を一度起動すると自動的に作成されます
- 手動で作成する場合は、上記の「設定ファイルの例」をコピーして使用してください

