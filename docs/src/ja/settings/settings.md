---
title: Settings
description: FakeTools の共有設定ダイアログ
lang: ja
lang-ref: settings
order: 10
---

## 概要

**Settings** ダイアログでは、FakeTools の複数ツールで共有される設定を GUI から編集できます。

メニューから **FakeTools > Settings...** を選択して開きます。

## 設定項目

### Mirror Patterns

左右の名前置換に使用する正規表現パターンです。\
各パターンは **Regex Pattern**（検索）と **Replacement**（置換）のペアで構成され、Python の `re.sub()` に渡されます。

| フィールド | デフォルト | 説明 |
|-----------|-----------|------|
| Left to Right | `(.*)(L)` → `\g<1>R` | 左から右への名前変換 |
| Right to Left | `(.*)(R)` → `\g<1>L` | 右から左への名前変換 |
| Adjust Center | `(.*)(L$)` → `\g<1>R` | センターウエイト調整時のペア検索 |

以下のツールがこの設定を参照します：

- [Selecter](../common/selecter.html) - 名前を置換して選択（左右）
- [Skin Tools](../rig/skin_tools.html) - Mirror Self / Mirror Sub / Adjust Center Weights
- [Proxy Builder](../rig/proxy_builder.html) - ミラー時の名前変換

### Hotkeys

| フィールド | デフォルト | 説明 |
|-----------|-----------|------|
| Single Commands Popup | `Ctrl+Shift+Z` | Single Commands ポップアップメニューのホットキー |

ホットキーの変更は **Reload Menu** 後に反映されます。

## 操作

| ボタン | 動作 |
|--------|------|
| **Save** | 入力を検証して保存し、ダイアログを閉じる |
| **Reset to Defaults** | すべてのフィールドをデフォルト値に戻す（保存はされない） |
| **Cancel** | 変更を破棄してダイアログを閉じる |

Save 時に正規表現パターンが不正な場合、エラーダイアログが表示されます。

## カスタム例

### `_Left` / `_Right` の命名規則

| フィールド | Regex Pattern | Replacement |
|-----------|--------------|-------------|
| Left to Right | `(.*)(_Left)` | `\g<1>_Right` |
| Right to Left | `(.*)(_Right)` | `\g<1>_Left` |
| Adjust Center | `(.*)(_Left$)` | `\g<1>_Right` |

### `_L_` / `_R_` の命名規則（中間一致）

| フィールド | Regex Pattern | Replacement |
|-----------|--------------|-------------|
| Left to Right | `(.*)_L_(.*)` | `\g<1>_R_\g<2>` |
| Right to Left | `(.*)_R_(.*)` | `\g<1>_L_\g<2>` |
| Adjust Center | `(.*)_L_(.*)` | `\g<1>_R_\g<2>` |

## 設定ファイル

設定は JSON ファイルとして保存されます。\
Settings ダイアログを使わずに、JSON ファイルを直接編集することも可能です。

### 設定ファイルの場所

設定ファイルは、対象ツールを初めて起動した際、または Settings ダイアログで保存した際に自動的に作成されます。

- Windows: `%MAYA_APP_DIR%/faketools_workspace/shared/config/settings/default.json`
- Mac: `~/Library/Preferences/Autodesk/maya/faketools_workspace/shared/config/settings/default.json`
- Linux: `~/maya/faketools_workspace/shared/config/settings/default.json`

### JSON ファイルの例

```json
{
  "mirror_patterns": {
    "left_to_right": ["(.*)(L)", "\\g<1>R"],
    "right_to_left": ["(.*)(R)", "\\g<1>L"],
    "adjust_center_weight": ["(.*)(L$)", "\\g<1>R"]
  },
  "hotkeys": {
    "single_commands_popup": "Ctrl+Shift+Z"
  }
}
```

各値は `[検索パターン, 置換文字列]` の2要素のリストです。\
一部の設定のみを変更した場合、記載のないキーにはデフォルト値が使用されます。

### 設定のリセット

Settings ダイアログの **Reset to Defaults** → **Save** でリセットできます。\
または、`default.json` ファイルを削除してツールを再起動してください。
