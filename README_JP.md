# Maya Fake Tools

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

[English](README.md) | 日本語

Autodesk Maya向けのプロダクション対応ツール集です。リギング、モデリング、アニメーション用のユーティリティをプラグインベースのアーキテクチャで提供します。

## 機能

**リギングツール**
- スキンウェイト管理（コピー、ペースト、リラックス、ミラー）
- コンポーネント選択とメンバーシップツール
- トランスフォームの作成と操作
- リモートスライダーとドリブンキー

**モデリングツール**
- バウンディングボックス作成
- メッシュとトランスフォームのリターゲット

**共通ツール**
- クイックアクセス用ノードストッカー
- アトリビュート管理

## インストール

1. [Releases](https://github.com/mitsuaki0321/maya-fake-tools/releases)から最新版をダウンロード
2. `maya-fake-tools_vX.X.X.zip`を任意のディレクトリに展開（例：`C:/maya_tools/`）
3. 展開したディレクトリをMayaの`MAYA_MODULE_PATH`環境変数に追加：
   - **Windows**: `set MAYA_MODULE_PATH=C:/maya_tools;%MAYA_MODULE_PATH%`
   - **Linux/Mac**: `export MAYA_MODULE_PATH=/path/to/maya_tools:$MAYA_MODULE_PATH`
4. Mayaを再起動
5. Mayaのスクリプトエディタを開き、以下を実行：
   ```python
   import faketools.menu
   faketools.menu.add_menu()
   ```
6. Mayaのメインメニューバーに「FakeTools」メニューが表示されます

## ドキュメント

ブラウザで`docs/index.html`を開くと、スクリーンショットや使用例を含む詳細なドキュメントを参照できます。

対応言語：
- 日本語
- English

## 動作環境

- Autodesk Maya 2022以降
- Python 3.11+（Mayaに同梱）
- numpy（Maya 2022+に同梱）
- scipy（Maya 2022+に同梱）

**注意**: numpyとscipyはMaya 2022以降にデフォルトで含まれています。

## ライセンス

このプロジェクトはMITライセンスの下で公開されています。詳細は[LICENSE](LICENSE)ファイルを参照してください。
