---
title: 共有設定
hidden: true
lang: ja
lang-ref: shared_config
---

## 概要

FakeTools の一部の機能は、ツール間で共通の設定ファイルを参照します。\
設定ファイルを編集することで、プロジェクトの命名規則に合わせた動作のカスタマイズが可能です。

## 設定ファイルの場所

設定ファイルは、対象ツールを初めて起動した際に自動的に作成されます。

- Windows: `%MAYA_APP_DIR%/faketools_workspace/shared/config/settings/default.json`
- Mac: `~/Library/Preferences/Autodesk/maya/faketools_workspace/shared/config/settings/default.json`
- Linux: `~/maya/faketools_workspace/shared/config/settings/default.json`

## 設定項目

### ミラーパターン (mirror_patterns)

左右の名前置換に使用する正規表現パターンです。\
以下のツールがこの設定を参照します。

- [Selecter](selecter.html) - 名前を置換して選択（左右）
- [Skin Tools](../rig/skin_tools.html) - Mirror Self / Mirror Sub / Adjust Center Weights

| 設定名 | デフォルト値 | 説明 |
|--------|------------|------|
| `left_to_right` | `["(.*)(L)", "\\g<1>R"]` | 左から右への名前変換パターン `[検索, 置換]` |
| `right_to_left` | `["(.*)(R)", "\\g<1>L"]` | 右から左への名前変換パターン `[検索, 置換]` |
| `adjust_center_weight` | `["(.*)(L$)", "\\g<1>R"]` | センターウエイト調整時のペア検索パターン `[検索, 置換]` |

各値は `[検索パターン, 置換文字列]` の2要素のリストで、Python の `re.sub()` に渡される正規表現です。

## 設定ファイルの例

### デフォルト設定

```json
{
  "mirror_patterns": {
    "left_to_right": ["(.*)(L)", "\\g<1>R"],
    "right_to_left": ["(.*)(R)", "\\g<1>L"],
    "adjust_center_weight": ["(.*)(L$)", "\\g<1>R"]
  }
}
```

### カスタム例: `_Left` / `_Right` の命名規則

```json
{
  "mirror_patterns": {
    "left_to_right": ["(.*)(_Left)", "\\g<1>_Right"],
    "right_to_left": ["(.*)(_Right)", "\\g<1>_Left"],
    "adjust_center_weight": ["(.*)(_Left$)", "\\g<1>_Right"]
  }
}
```

### カスタム例: `_L_` / `_R_` の命名規則（中間一致）

```json
{
  "mirror_patterns": {
    "left_to_right": ["(.*)_L_(.*)", "\\g<1>_R_\\g<2>"],
    "right_to_left": ["(.*)_R_(.*)", "\\g<1>_L_\\g<2>"],
    "adjust_center_weight": ["(.*)_L_(.*)", "\\g<1>_R_\\g<2>"]
  }
}
```

## 設定の変更方法

1. 対象ツールを一度起動して設定ファイルを自動生成する
2. 上記パスの `default.json` をテキストエディタで開く
3. 値を変更して保存する
4. ツールを再起動する（次回のコマンド実行時から反映されます）

※ 一部の設定のみを変更した場合、記載のないキーにはデフォルト値が使用されます。

## 設定のリセット

すべての設定をデフォルトに戻したい場合は、`default.json` ファイルを削除してツールを再起動してください。\
自動的にデフォルト設定のファイルが再作成されます。
