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

### 一般設定 (general)

| 設定名 | デフォルト値 | 説明 |
|--------|------------|------|
| `language` | "JPN" | UI 言語 (JPN: 日本語 / ENU: 英語 等) |

### エディタ設定 (editor)
コードエディタの表示と動作に関する設定です。

| 設定名 | デフォルト値 | 説明 |
|--------|------------|------|
| `font_size` | 10 | エディタの文字サイズ |
| `word_wrap` | true | エディタ幅での折り返し表示 |

※ フォントは "Cascadia Code" 固定（フォールバック: "Consolas" → "Courier New"）。行高は等幅フォントの自然行高の約 1.6 倍。タブサイズは 4 スペース。行番号は常に有効です。

### ターミナル設定 (terminal)
実行結果を表示するターミナルの設定です。

| 設定名 | デフォルト値 | 説明 |
|--------|------------|------|
| `font_size` | 9 | ターミナルの文字サイズ |

※ フォントは "Cascadia Code" 固定（フォールバック: "Consolas" → "Courier New"）。最大行数は 1000 行です。

### 検索設定 (search)
検索・置換機能の初期設定です。

| 設定名 | デフォルト値 | 説明 |
|--------|------------|------|
| `match_case` | false | 大文字・小文字を区別して検索するか |
| `whole_words` | false | 単語単位で検索するか |
| `use_regex` | false | 正規表現を使用して検索するか |
| `search_direction` | "down" | 検索方向（down: 下方向 / up: 上方向） |

### オートコンプリート設定 (autocomplete)
コードエディターのオートコンプリート機能に関する設定です。

| 設定名 | デフォルト値 | 説明 |
|--------|------------|------|
| `enabled` | true | オートコンプリートを有効にするか |
| `debounce_ms` | 100 | 識別子入力時の補完起動デバウンス時間 (ms)。 `.` 入力時のドット補完は即時で起動するため対象外 |

※ ツールバーの Toggle Autocomplete ボタンや Ctrl+Space からも切り替え可能です。jedi が未インストールの場合は自動的に無効化されます。MEL タブでは設定値に関わらず動作しません ( Python 専用 )。

### レイアウト設定 (layout)
ウィンドウのレイアウトに関する設定です。

| 設定名 | デフォルト値 | 説明 |
|--------|------------|------|
| `terminal_at_bottom` | true | ターミナルの表示位置（true: 下 / false: 上） |

## 設定ファイルの例

```json
{
  "general": {
    "language": "JPN"
  },
  "editor": {
    "font_size": 12,
    "word_wrap": true
  },
  "terminal": {
    "font_size": 10
  },
  "search": {
    "match_case": false,
    "whole_words": false,
    "use_regex": false,
    "search_direction": "down"
  },
  "autocomplete": {
    "enabled": true,
    "debounce_ms": 100
  },
  "layout": {
    "terminal_at_bottom": true
  }
}
```

## セッションとワークスペース

`user_settings.json` には UI 表示まわりの設定だけを保存し、以下の状態は別ファイルで管理されます。

| ファイル | 役割 |
|------|------|
| `session.json` | 開いていたタブ・カーソル位置・ドラフト本文・オートコンプリートの MRU 等の作業状態 |
| `workspace.json` | ワークスペースルート、エクスプローラーの展開状態などのプロジェクト寄り情報 |

これらは Code Editor の起動・終了時に自動で読み書きされ、ユーザー設定とは独立しています。\
過去のバージョンに存在した独立した自動保存 (`autosave`) や Maya ヘルプ言語、コマンドポート (`command_port`) の設定はユーザー設定からは廃止されており、未保存内容は `session.json` のドラフトメカニズムでカバーされます。

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
