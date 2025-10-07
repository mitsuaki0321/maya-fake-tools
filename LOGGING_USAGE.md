# Logging Usage Guide

このガイドでは、FakeToolsパッケージでのロギングの使用方法を説明します。

## 基本的な使い方

### ツールやモジュールでロガーを取得する

```python
# 任意のモジュールで
import logging

logger = logging.getLogger(__name__)

# ログを出力
logger.debug("デバッグメッセージ")
logger.info("情報メッセージ")
logger.warning("警告メッセージ")
logger.error("エラーメッセージ")
logger.critical("重大なエラーメッセージ")
```

**重要**: `__name__` を使用することで、モジュールが `faketools` パッケージ内にあれば、自動的に `faketools` ルートロガーの子ロガーになります。

### ツールの例

```python
# tools/rig/my_tool/command.py
import logging
import maya.cmds as cmds

logger = logging.getLogger(__name__)  # "faketools.tools.rig.my_tool.command" というロガーになる

def execute_operation():
    """Execute the main operation."""
    logger.info("Starting operation")

    try:
        # Maya操作
        selection = cmds.ls(selection=True)
        logger.debug(f"Selected objects: {selection}")

        if not selection:
            logger.warning("No objects selected")
            return None

        # 処理
        result = process_selection(selection)
        logger.info(f"Operation completed: {result}")
        return result

    except Exception as e:
        logger.error(f"Operation failed: {e}", exc_info=True)
        raise
```

## ログレベルの変更

### Mayaのスクリプトエディタから

```python
import faketools
import logging

# DEBUGレベルに変更（すべてのログを表示）
faketools.set_log_level(logging.DEBUG)

# INFOレベルに変更（通常の情報を表示）
faketools.set_log_level(logging.INFO)

# WARNINGレベルに変更（警告とエラーのみ表示）
faketools.set_log_level(logging.WARNING)

# ERRORレベルに変更（エラーのみ表示）
faketools.set_log_level(logging.ERROR)
```

### 開発中のデバッグ

```python
# Maya起動時やツール開発中にDEBUGモードを有効化
import faketools
import logging

faketools.set_log_level(logging.DEBUG)

# メニューを再読み込み
import faketools.menu
faketools.menu.reload_menu()
```

## ログレベルの説明

| レベル | 数値 | 用途 |
|--------|------|------|
| DEBUG | 10 | 詳細な診断情報（開発中のみ） |
| INFO | 20 | 一般的な情報メッセージ（デフォルト） |
| WARNING | 30 | 警告メッセージ（問題の可能性） |
| ERROR | 40 | エラーメッセージ（機能の失敗） |
| CRITICAL | 50 | 重大なエラー（システムの失敗） |

## ロギングのベストプラクティス

### 1. 適切なログレベルを使用する

```python
# DEBUG: 開発中の診断情報
logger.debug(f"Variable value: {var}")
logger.debug(f"Entering function with args: {args}")

# INFO: 通常の動作の記録
logger.info("Tool initialized successfully")
logger.info(f"Processed {count} objects")

# WARNING: 問題の可能性があるが続行可能
logger.warning("Selection is empty, using default values")
logger.warning("Deprecated feature used")

# ERROR: 機能が失敗したが回復可能
logger.error(f"Failed to process object: {obj_name}")
logger.error("Configuration file not found", exc_info=True)

# CRITICAL: 重大なエラー、システムが続行不可能
logger.critical("Maya API initialization failed")
```

### 2. 例外情報を含める

```python
try:
    # 何か処理
    result = risky_operation()
except Exception as e:
    # exc_info=Trueでスタックトレースを含める
    logger.error(f"Operation failed: {e}", exc_info=True)
    raise
```

### 3. モジュール名を使用する

```python
# 常に __name__ を使用してモジュール名を取得
logger = get_logger(__name__)

# これにより、ログ出力で正確なモジュール名が表示される
# 例: [INFO] faketools.tools.rig.my_tool.command: Processing started
```

### 4. フォーマット文字列を使用する

```python
# 良い例: ログレベルが無効な場合、文字列結合を避ける
logger.debug(f"Processing {len(items)} items: {items}")

# 悪い例: 常に文字列を結合する
logger.debug("Processing " + str(len(items)) + " items: " + str(items))
```

## 詳細ログフォーマット

開発中により詳細な情報が必要な場合:

```python
import faketools
import logging

# 詳細フォーマットで再初期化
faketools.setup_logging(level=logging.DEBUG, detailed=True)

# 出力例:
# [DEBUG] 2024-01-15 10:30:45,123 - faketools.core.registry - registry.py:46 - Discovering tools in C:\maya-fake-tools\scripts\faketools\tools
```

## トラブルシューティング

### ログが表示されない場合

```python
import faketools
import logging

# ログレベルを確認
from faketools.logging_config import get_log_level
current_level = get_log_level()
print(f"Current log level: {logging.getLevelName(current_level)}")

# DEBUGに設定
faketools.set_log_level(logging.DEBUG)
```

### ログを完全にリセット

```python
import faketools
import logging

# ロガーを再初期化
faketools.setup_logging(level=logging.INFO)
```

## Maya起動時の自動設定

`userSetup.py`に以下を追加して、Maya起動時にログレベルを設定:

```python
# userSetup.py
import maya.cmds as cmds

def setup_faketools():
    """Setup FakeTools on Maya startup."""
    try:
        import faketools
        import logging

        # 開発中はDEBUGレベルを使用
        faketools.set_log_level(logging.DEBUG)

        # メニューを追加
        import faketools.menu
        faketools.menu.add_menu()

    except Exception as e:
        print(f"Failed to setup FakeTools: {e}")

# Maya起動後に実行
cmds.evalDeferred(setup_faketools)
```
