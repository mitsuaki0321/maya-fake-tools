# DEVELOP.md

開発者向けガイド - FakeTools内部構造と使用方法

## 📁 ディレクトリ構造

```
maya-fake-tools/
├── plug-ins/                      # Mayaプラグイン
│   └── (空 - 今後追加予定)
│
├── scripts/faketools/
│   ├── __init__.py               # パッケージルート
│   ├── menu.py                   # ★ メニューシステム
│   │
│   ├── core/                     # ★ コアフレームワーク
│   │   ├── __init__.py
│   │   ├── registry.py          # ★ ツール自動登録システム
│   │   └── base/
│   │       ├── __init__.py
│   │       └── tool.py          # ★ BaseTool (オプション)
│   │
│   ├── lib/                      # グローバル共有ライブラリ
│   │   └── __init__.py          # (今後追加予定)
│   │
│   ├── lib_ui/                   # ★ UI関連ユーティリティ
│   │   ├── __init__.py
│   │   ├── qt_compat.py         # ★ Qt互換性レイヤー
│   │   ├── maya_ui.py           # ★ Mayaデコレーター
│   │   └── widgets/
│   │       └── __init__.py      # (今後追加予定)
│   │
│   └── tools/                    # ★ カテゴリ別ツール
│       ├── __init__.py
│       ├── rig/                  # リギングツール
│       ├── model/                # モデリングツール
│       ├── anim/                 # アニメーションツール
│       └── common/               # 共通ツール
│           └── example_tool/    # ★ サンプルツール
│               ├── __init__.py
│               ├── ui.py
│               └── command.py
│
├── faketools.mod                 # Mayaモジュール定義
├── CLAUDE.md                     # AI開発ガイド
├── DEVELOP.md                    # このファイル
└── pyproject.toml               # プロジェクト設定
```

## 🔧 コアファイルの説明

### 1. `menu.py` - メニューシステム

Mayaのメインメニューに「FakeTools」メニューを追加するシステム。

**主な機能:**
- ツールの自動検出と登録
- カテゴリ別メニュー生成
- メニューのリロード

**使用方法:**

```python
# Maya起動後、Pythonスクリプトエディタで実行
import faketools.menu
faketools.menu.add_menu()

# メニューを削除
faketools.menu.remove_menu()

# メニューを再読み込み
faketools.menu.reload_menu()
```

**内部動作:**
1. `get_registry()`でツールレジストリを取得
2. `registry.discover_tools()`でツールを検出
3. カテゴリ別にメニュー項目を生成
4. 各ツールの`show_ui()`関数を呼び出すコマンドを設定

**カスタマイズ:**
- `MENU_NAME`: メニューの内部名 (デフォルト: "FakeToolsMenu")
- `MENU_LABEL`: メニューの表示名 (デフォルト: "FakeTools")
- `CATEGORY_LABELS`: カテゴリの表示名マッピング

---

### 2. `core/registry.py` - ツール登録システム

ツールを自動的に検出・登録するシステム。

**主なクラス:**
- `ToolRegistry`: ツール管理クラス
- `get_registry()`: グローバルレジストリ取得

**主なメソッド:**

```python
from faketools.core.registry import get_registry

registry = get_registry()

# ツールを検出
registry.discover_tools()

# 登録されたカテゴリを取得
categories = registry.get_all_categories()
# 結果: ['rig', 'model', 'anim', 'common']

# カテゴリ内のツールを取得
tools = registry.get_tools_by_category('common')
# 結果: [{'id': 'common.example_tool', 'name': 'Example Tool', ...}]

# 特定のツールを取得
tool = registry.get_tool('common.example_tool')

# ツールインスタンスを作成
instance = registry.create_tool_instance('common.example_tool', parent=maya_window)

# メニュー構造を取得
menu_structure = registry.get_menu_structure()
```

**ツール検出の仕組み:**
1. `tools/`ディレクトリをスキャン
2. 各カテゴリディレクトリ内のツールディレクトリを検出
3. `__init__.py`に`TOOL_CONFIG`があれば登録
4. なければ`BaseTool`サブクラスを探して自動登録

---

### 3. `core/base/tool.py` - BaseTool (オプション)

ツールの基底クラス（継承は任意）。

**使用例:**

```python
from faketools.core.base.tool import BaseTool

class MyTool(BaseTool):
    TOOL_NAME = "My Tool"
    TOOL_VERSION = "1.0.0"
    TOOL_DESCRIPTION = "My custom tool"
    TOOL_CATEGORY = "rig"

    def setup_ui(self):
        # UIのセットアップ
        pass
```

**メリット:**
- 標準的なメタデータ管理
- `get_metadata()`の自動実装
- 一貫したツール構造

**注意:** BaseToolの継承は**オプション**です。TOOL_CONFIGを使う方が推奨されます。

---

### 4. `lib_ui/qt_compat.py` - Qt互換性レイヤー

PySide2/PySide6の自動切り替えを提供。

**使用方法:**

```python
# すべてのQtインポートをこのモジュールから行う
from faketools.lib_ui.qt_compat import (
    QWidget, QPushButton, QVBoxLayout,
    QLabel, QLineEdit, QMessageBox,
    Qt, Signal, Slot
)

# バージョン確認
from faketools.lib_ui.qt_compat import QT_VERSION, is_pyside2, is_pyside6

print(QT_VERSION)  # "PySide2" or "PySide6"
if is_pyside6():
    print("Maya 2023+")
```

**提供されるヘルパー関数:**

```python
from faketools.lib_ui.qt_compat import get_open_file_name, get_save_file_name

# PySide2/6の違いを吸収
filename, filter = get_open_file_name(
    parent=self,
    caption="Open File",
    directory="",
    filter="Python Files (*.py)"
)
```

**対応クラス:**
- すべての基本Widget (QWidget, QPushButton, QLabel等)
- レイアウト (QVBoxLayout, QHBoxLayout, QGridLayout等)
- ダイアログ (QFileDialog, QMessageBox, QInputDialog等)
- シグナル/スロット (Signal, Slot)

---

### 5. `lib_ui/maya_ui.py` - Mayaデコレーター

Maya UIのための便利なデコレーターとユーティリティ。

**デコレーター:**

#### `@error_handler`
UI内のエラーをキャッチしてダイアログ表示。

```python
from faketools.lib_ui.maya_ui import error_handler

class MyWindow(QWidget):
    @error_handler
    def on_button_clicked(self):
        # エラーが発生してもMayaがクラッシュしない
        raise ValueError("Something went wrong")
```

#### `@undo_chunk(name)`
複数の操作を1つのUndoにまとめる。

```python
from faketools.lib_ui.maya_ui import undo_chunk

class MyWindow(QWidget):
    @undo_chunk("Create Multiple Objects")
    def create_objects(self):
        cmds.polyCube()
        cmds.polySphere()
        cmds.polyCylinder()
        # すべて1回のUndoで元に戻せる
```

#### `@disable_undo`
クエリ操作など、Undoスタックに含めたくない操作用。

```python
from faketools.lib_ui.maya_ui import disable_undo

class MyWindow(QWidget):
    @disable_undo
    def refresh_list(self):
        # クエリ操作のみ、Undoには影響しない
        objects = cmds.ls(type='transform')
        self.update_ui(objects)
```

**ユーティリティ関数:**

```python
from faketools.lib_ui.maya_ui import (
    get_maya_window,
    show_error_dialog,
    show_warning_dialog,
    show_info_dialog,
    confirm_dialog
)

# Mayaメインウィンドウを親として取得
parent = get_maya_window()
my_window = MyWindow(parent)

# ダイアログ表示
show_error_dialog("Error", "Something went wrong")
show_warning_dialog("Warning", "This is a warning")
show_info_dialog("Info", "Operation completed")

if confirm_dialog("Confirm", "Are you sure?"):
    # Yesが押された
    pass
```

---

### 6. `tools/common/example_tool/` - サンプルツール

新しいツールを作成する際のテンプレート。

#### `__init__.py` - ツール設定

```python
from .ui import MainWindow, show_ui

# ツール設定（必須）
TOOL_CONFIG = {
    "name": "Example Tool",           # 表示名
    "version": "1.0.0",               # バージョン
    "description": "Example tool",    # 説明
    "menu_label": "Example Tool",     # メニュー表示名
    "requires_selection": False,      # 選択必須かどうか
    "author": "FakeTools",           # 作者
    "category": "common",            # カテゴリ
}

__all__ = ["MainWindow", "show_ui", "TOOL_CONFIG"]
```

#### `ui.py` - UIレイヤー

UIの実装とユーザーインタラクション。

```python
from ....lib_ui.maya_ui import error_handler, get_maya_window, undo_chunk
from ....lib_ui.qt_compat import QWidget, QPushButton, QVBoxLayout
from . import command

class MainWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        btn = QPushButton("Execute")
        btn.clicked.connect(self.on_execute)
        layout.addWidget(btn)

    @error_handler
    @undo_chunk("Tool Operation")
    def on_execute(self):
        # commandモジュールを呼び出す
        result = command.execute_example()
        print(result)

def show_ui():
    """ツールを表示（メニューから呼ばれる）"""
    global _instance
    parent = get_maya_window()
    _instance = MainWindow(parent)
    _instance.show()
    return _instance
```

**重要なポイント:**
- **デコレーターはUIレイヤーのみ**に使用
- `show_ui()`関数は必須（メニューから呼ばれる）
- シングルトンパターンを推奨

#### `command.py` - ビジネスロジック

純粋なMaya操作のみを記述。

```python
import maya.cmds as cmds

def execute_example() -> str:
    """
    実際の処理を実行。

    Returns:
        str: 結果メッセージ
    """
    selection = cmds.ls(selection=True)

    if not selection:
        return "No objects selected"

    # Maya操作
    result = f"Processed {len(selection)} objects"
    return result
```

**重要なポイント:**
- **デコレーターは使わない**（純粋関数）
- エラーハンドリングはUIレイヤーに任せる
- 戻り値で結果を返す

---

## 🚀 新しいツールの作り方

### ステップ1: ディレクトリ作成

```bash
# カテゴリを選択: rig, model, anim, common
mkdir -p scripts/faketools/tools/{category}/{tool_name}
```

### ステップ2: `__init__.py` 作成

```python
"""Tool description."""

from .ui import MainWindow, show_ui

TOOL_CONFIG = {
    "name": "My Tool",
    "version": "1.0.0",
    "description": "Description of my tool",
    "menu_label": "My Tool",
    "requires_selection": False,
    "author": "Your Name",
    "category": "rig",  # rig/model/anim/common
}

__all__ = ["MainWindow", "show_ui", "TOOL_CONFIG"]
```

### ステップ3: `ui.py` 作成

```python
"""My Tool UI."""

from ....lib_ui.maya_ui import error_handler, get_maya_window, undo_chunk
from ....lib_ui.qt_compat import QWidget, QPushButton, QVBoxLayout
from . import command

_instance = None

class MainWindow(QWidget):
    """Main window for My Tool."""

    def __init__(self, parent=None):
        """Initialize the window."""
        super().__init__(parent)
        self.setWindowTitle("My Tool")
        self.setup_ui()

    def setup_ui(self):
        """Setup UI."""
        layout = QVBoxLayout(self)

        btn = QPushButton("Execute")
        btn.clicked.connect(self.on_execute)
        layout.addWidget(btn)

    @error_handler
    @undo_chunk("My Tool Operation")
    def on_execute(self):
        """Handle button click."""
        result = command.do_something()
        print(f"Result: {result}")

def show_ui():
    """Show the tool UI."""
    global _instance

    if _instance is not None:
        try:
            _instance.close()
            _instance.deleteLater()
        except RuntimeError:
            pass

    parent = get_maya_window()
    _instance = MainWindow(parent)
    _instance.show()
    return _instance

__all__ = ["MainWindow", "show_ui"]
```

### ステップ4: `command.py` 作成

```python
"""My Tool commands."""

import maya.cmds as cmds

def do_something() -> str:
    """
    Execute the main operation.

    Returns:
        str: Result message
    """
    # Your Maya operations here
    selection = cmds.ls(selection=True)

    # Process...

    return f"Processed {len(selection)} items"

__all__ = ["do_something"]
```

### ステップ5: テスト

```python
# Maya上で
import faketools.menu
faketools.menu.reload_menu()

# メニューから "My Tool" を選択
```

---

## 📝 インポートパス規則

### 相対インポート

```python
# ツール内でのインポート
from . import command              # 同じツール内のcommand.py
from .ui import MainWindow         # 同じツール内のui.py
```

### グローバルライブラリ

```python
# lib_ui
from ....lib_ui.qt_compat import QWidget  # 4階層上のlib_ui
from ....lib_ui.maya_ui import error_handler

# lib (将来的に追加)
from ....lib import lib_mesh
```

### 階層の数え方

```
tools/rig/my_tool/ui.py から lib_ui へ
  ↑    ↑    ↑      ↑
  4    3    2      1  階層
```

---

## 🎨 開発のベストプラクティス

### 1. レイヤー分離

- **UIレイヤー** (`ui.py`): ユーザーインタラクション、デコレーター使用
- **コマンドレイヤー** (`command.py`): Maya操作、純粋関数

### 2. デコレーターの使用

✅ **正しい使い方:**
```python
# ui.py
@error_handler
@undo_chunk("Operation")
def on_button_clicked(self):
    result = command.do_something()
```

❌ **間違った使い方:**
```python
# command.py
@error_handler  # コマンドレイヤーでは使わない
def do_something():
    pass
```

### 3. Qt互換性

✅ **正しい使い方:**
```python
from ....lib_ui.qt_compat import QWidget, QPushButton
```

❌ **間違った使い方:**
```python
from PySide2.QtWidgets import QWidget  # 直接インポートしない
```

### 4. エラーハンドリング

```python
# ui.py - UIでエラーを処理
@error_handler
def on_execute(self):
    result = command.do_something()
    if not result:
        show_warning_dialog("Warning", "No result")

# command.py - 結果を返す
def do_something():
    if error_condition:
        return None  # エラーを例外ではなく戻り値で示す
    return result
```

---

## 🔍 デバッグとトラブルシューティング

### ツールがメニューに表示されない

1. ディレクトリ構造を確認
```python
# Maya上で
from pathlib import Path
tools_path = Path(__file__).parent.parent / "tools"
print(list(tools_path.rglob("__init__.py")))
```

2. TOOL_CONFIGを確認
```python
# Maya上で
import faketools.tools.common.example_tool as tool
print(tool.TOOL_CONFIG)
```

3. レジストリをデバッグ
```python
from faketools.core.registry import get_registry
registry = get_registry()
registry.discover_tools()
print(registry._tools)  # 登録されたツール一覧
```

### インポートエラー

相対インポートの階層を確認:
```python
# tools/category/tool_name/ui.py から
from ....lib_ui.qt_compat import QWidget  # 正しい
from ...lib_ui.qt_compat import QWidget   # 間違い (階層が足りない)
```

### メニューがリロードされない

```python
# 完全にリロード
import faketools.menu
import importlib
importlib.reload(faketools.menu)
faketools.menu.reload_menu()
```

---

## 📚 さらなる情報

- **コードスタイル**: CLAUDE.md参照
- **AI開発ガイド**: CLAUDE.md参照
- **Mayaモジュール**: faketools.mod参照

---

*このドキュメントは開発者向けです。ユーザー向けドキュメントはREADME.mdを参照してください。*
