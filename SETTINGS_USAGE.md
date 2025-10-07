# Settings Usage Guide

このガイドでは、FakeToolsパッケージでの設定管理システムの使用方法を説明します。

## 概要

FakeToolsは3つの独立した設定管理システムを提供します：

1. **グローバル設定** (`config.py`): FakeTools全体の設定（JSONファイル）
2. **ツール設定** (`lib_ui/optionvar.py`): ツールごとのUI設定（Maya optionVar）
3. **ツールデータ** (`lib_ui/tool_data.py`): ツールごとのデータファイル管理（ファイルシステム）

---

## 1. グローバル設定 (GlobalConfig)

FakeTools全体で共有される設定を管理します。

### 基本的な使い方

```python
from faketools.config import get_global_config

# グローバル設定を取得
config = get_global_config()

# データルートディレクトリを取得
data_root = config.get_data_root_dir()
print(data_root)  # ~/Documents/maya/faketools_workspace

# ログレベルを取得
log_level = config.get_log_level()
print(log_level)  # INFO
```

### 設定の変更

```python
from faketools.config import get_global_config
from pathlib import Path

config = get_global_config()

# データルートディレクトリを変更
config.set_data_root_dir("D:/MyProject/maya_data")

# ログレベルを変更
config.set_log_level("DEBUG")

# 変更を保存
config.save()
```

### 設定のリセット

```python
from faketools.config import get_global_config

config = get_global_config()

# デフォルト設定にリセット
config.reset_to_defaults()
```

### 設定ファイルの場所

- **Windowsの場合**: `C:\Users\<ユーザー名>\Documents\maya\faketools\config.json`
- **macOS/Linuxの場合**: `~/Documents/maya/faketools/config.json`

### デフォルト設定

`data_root_dir` は `MAYA_APP_DIR` 環境変数から自動的に決定されます：
- `$MAYA_APP_DIR/faketools_workspace`

**重要**: FakeToolsはMaya環境内で実行する必要があります。`MAYA_APP_DIR`環境変数が設定されていない場合、初期化時に`RuntimeError`が発生します。

```json
{
    "data_root_dir": "$MAYA_APP_DIR/faketools_workspace",
    "log_level": "INFO",
    "version": "1.0.0"
}
```

---

## 2. ツール設定 (ToolOptionSettings)

各ツールのUI設定（ウィンドウサイズ、チェックボックス状態など）を管理します。
設定はMayaの `optionVar` に保存され、Maya再起動後も保持されます。

### 基本的な使い方

```python
from faketools.lib_ui.optionvar import ToolOptionSettings

# ToolOptionSettings インスタンスを作成
settings = ToolOptionSettings(__name__)

# 設定を読み込み
window_size = settings.read("window_size", [400, 300])
print(window_size)  # [400, 300]

# 設定を書き込み
settings.write("window_size", [800, 600])

# 設定を削除
settings.delete("old_setting")

# 設定の存在確認
if settings.exists("window_size"):
    print("Window size setting exists")
```

### ウィンドウジオメトリの保存

```python
from faketools.lib_ui.optionvar import ToolOptionSettings

class MainWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = ToolOptionSettings(__name__)

        # ウィンドウジオメトリを復元
        geometry = self.settings.get_window_geometry()
        if geometry:
            self.resize(*geometry["size"])
            if "position" in geometry:
                self.move(*geometry["position"])

    def closeEvent(self, event):
        # ウィンドウジオメトリを保存
        self.settings.set_window_geometry(
            size=[self.width(), self.height()],
            position=[self.x(), self.y()]
        )
        super().closeEvent(event)
```

### チェックボックス状態の保存

```python
from faketools.lib_ui.optionvar import ToolOptionSettings

class MyToolWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = ToolOptionSettings(__name__)

        # チェックボックスを作成
        self.checkbox_a = QCheckBox("Option A")
        self.checkbox_b = QCheckBox("Option B")

        # 保存された状態を復元
        checkbox_states = self.settings.read("checkbox_states", {})
        self.checkbox_a.setChecked(checkbox_states.get("a", False))
        self.checkbox_b.setChecked(checkbox_states.get("b", False))

    def closeEvent(self, event):
        # チェックボックス状態を保存
        checkbox_states = {
            "a": self.checkbox_a.isChecked(),
            "b": self.checkbox_b.isChecked()
        }
        self.settings.write("checkbox_states", checkbox_states)
        super().closeEvent(event)
```

### ツール設定の保存先

ツール設定はMayaの `optionVar` に保存されます（ファイルとしては見えません）。
各設定キーは `{tool_name}.{key}` の形式でネームスペース化されるため、ツール間で設定が競合しません。

---

## 3. ツールデータ管理 (ToolDataManager)

各ツールのデータファイル（スキンウェイト、アニメーションカーブなど）の保存先を管理します。

### 基本的な使い方

```python
from faketools.lib_ui.tool_data import ToolDataManager

# ToolDataManager インスタンスを作成
manager = ToolDataManager("skin_weights", "rig")

# データディレクトリを取得
data_dir = manager.get_data_dir()
print(data_dir)
# ~/Documents/maya/faketools_workspace/rig/skin_weights

# データディレクトリを作成
manager.ensure_data_dir()

# データファイルのパスを取得
weights_file = manager.get_data_path("character_a.json")
print(weights_file)
# ~/Documents/maya/faketools_workspace/rig/skin_weights/character_a.json
```

### カスタムデータディレクトリの設定

```python
from faketools.lib_ui.tool_data import ToolDataManager

manager = ToolDataManager("skin_weights", "rig")

# カスタムデータディレクトリを設定
manager.set_custom_data_dir("D:/MyProject/skin_data")

# 以降はカスタムディレクトリが使用される
data_dir = manager.get_data_dir()
print(data_dir)  # D:/MyProject/skin_data
```

### データファイルの一覧取得

```python
from faketools.lib_ui.tool_data import ToolDataManager

manager = ToolDataManager("skin_weights", "rig")

# すべてのJSONファイルを取得
json_files = manager.list_data_files("*.json")
for file in json_files:
    print(file.name)

# すべてのファイルを取得
all_files = manager.list_data_files()
```

### 古いファイルのクリーンアップ

```python
from faketools.lib_ui.tool_data import ToolDataManager

manager = ToolDataManager("skin_weights", "rig")

# 30日以上古いバックアップファイルを削除
deleted = manager.cleanup_old_files(days=30, pattern="*.backup")
print(f"削除されたファイル: {deleted}件")
```

### ディレクトリ構造

```
~/Documents/maya/faketools_workspace/          # データルート
├── rig/                                  # カテゴリ
│   ├── transform_connector/              # ツール
│   │   └── presets.json
│   └── skin_weights/
│       ├── character_a_weights.json
│       └── character_b_weights.json
├── model/
│   └── mesh_exporter/
│       └── templates/
└── anim/
    └── curve_library/
        └── walks/
```

---

## 実用例: スキンウェイトツール

```python
from faketools.lib_ui.optionvar import ToolOptionSettings
from faketools.lib_ui.tool_data import ToolDataManager
from ....lib_ui.qt_compat import QWidget, QPushButton, QVBoxLayout
import maya.cmds as cmds
import json

class SkinWeightTool(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        # ツール設定
        self.settings = ToolOptionSettings(__name__)

        # データ管理
        self.data_manager = ToolDataManager("skin_weights", "rig")
        self.data_manager.ensure_data_dir()

        self.setup_ui()

        # ウィンドウサイズを復元
        geometry = self.settings.get_window_geometry()
        if geometry:
            self.resize(*geometry["size"])

    def setup_ui(self):
        layout = QVBoxLayout(self)

        export_btn = QPushButton("Export Weights")
        export_btn.clicked.connect(self.export_weights)
        layout.addWidget(export_btn)

        import_btn = QPushButton("Import Weights")
        import_btn.clicked.connect(self.import_weights)
        layout.addWidget(import_btn)

    def export_weights(self):
        # 選択されたメッシュを取得
        selection = cmds.ls(selection=True, type="transform")
        if not selection:
            cmds.warning("メッシュを選択してください")
            return

        mesh_name = selection[0]

        # スキンウェイトデータを取得（簡略化）
        weights_data = {"mesh": mesh_name, "weights": []}

        # データファイルパスを取得
        file_path = self.data_manager.get_data_path(f"{mesh_name}_weights.json")

        # JSONファイルに保存
        with open(file_path, "w") as f:
            json.dump(weights_data, f, indent=4)

        print(f"Weights exported to: {file_path}")

    def import_weights(self):
        # データファイル一覧を取得
        weight_files = self.data_manager.list_data_files("*_weights.json")

        if not weight_files:
            cmds.warning("保存されたウェイトファイルがありません")
            return

        # 最初のファイルを読み込み（簡略化）
        file_path = weight_files[0]

        with open(file_path) as f:
            weights_data = json.load(f)

        print(f"Weights imported from: {file_path}")

    def closeEvent(self, event):
        # ウィンドウサイズを保存
        self.settings.set_window_geometry(
            size=[self.width(), self.height()],
            position=[self.x(), self.y()]
        )
        super().closeEvent(event)
```

---

## 設定の階層と使い分け

| システム | 保存場所 | 用途 | 例 |
|---------|---------|------|---|
| **ToolOptionSettings** | Maya optionVar | ツールごとのUI設定 | ウィンドウサイズ、チェックボックス状態 |
| **GlobalConfig** | JSONファイル | FakeTools全体の設定 | データルートパス、ログレベル |
| **ToolDataManager** | ファイルシステム | ツールが扱うデータ | スキンウェイト、プリセット、テンプレート |

### 特徴の比較

1. **optionVar** (Maya内部)
   - Mayaセッション間で永続化
   - ユーザー個人の好み
   - JSON自動シリアライズ対応
   - ツール名でネームスペース化

2. **JSONファイル** (ファイルシステム)
   - チーム間で共有可能
   - バージョン管理可能
   - FakeTools全体の動作を制御

3. **データファイル** (ファイルシステム)
   - バックアップ・共有が必要
   - プロジェクトごとに管理
   - ツールが生成・消費するデータ

---

## トラブルシューティング

### 設定が保存されない

```python
from faketools.config import get_global_config

config = get_global_config()
# 変更後に必ず save() を呼ぶ
config.set_log_level("DEBUG")
config.save()  # これを忘れずに！
```

### データディレクトリが見つからない

```python
from faketools.lib_ui.tool_data import ToolDataManager

manager = ToolDataManager("my_tool", "rig")

# ディレクトリが存在するか確認
if not manager.exists():
    # ディレクトリを作成
    manager.ensure_data_dir()
```

### 設定をリセットしたい

```python
# グローバル設定のリセット
from faketools.config import get_global_config
config = get_global_config()
config.reset_to_defaults()

# ツール設定のリセット（個別削除）
from faketools.lib_ui.optionvar import ToolOptionSettings
settings = ToolOptionSettings("my_tool")
settings.delete("window_size")
settings.delete("checkbox_states")
```

---

*このガイドは開発者向けです。ツールの使い方については各ツールのドキュメントを参照してください。*
