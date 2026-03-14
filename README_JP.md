# Maya Fake Tools

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

[English](README.md) | 日本語

Autodesk Maya向けのプロダクション対応ツール集です。リギング、モデリング、アニメーション用のユーティリティを提供します。

## 機能

**リギングツール**
- スキンウェイト管理（コピー/ペースト、インフルエンス間転送、インポート/エクスポート、ロバストウェイト転送）
- ジョイント位置でのプロキシジオメトリ生成
- トランスフォームの接続・作成・スナップ
- カーブに沿ったトランスフォーム作成
- カーブ/サーフェス作成（オフセットカーブ、ロフトサーフェス）
- リモートアトリビュートスライダーとドリブンキーツール
- コネクション・アトリビュートのリスト表示
- Component Tagメンバーシップ管理

**モデリングツール**
- ランドマーク対応の非剛体ICPメッシュフィッティング
- メッシュ間のブレンドシェイプ転送
- メッシュとトランスフォームのリターゲット
- バウンディングボックス作成
- コンポーネントの選択とフィルタリング
- テクスチャパスの再配置
- glTF/GLBメッシュインポーター（Blender経由）

**アニメーションツール**
- Sync Player：Mayaタイムラインと同期するビデオプレイヤー

**共通ツール**
- シンタックスハイライト付きPythonコードエディタ（Maya統合）
- 選択フィルタリング・階層選択・一括リネーム機能付きセレクター
- クイックアクセス用ノードストッカー
- シーンクリーンアップ用オプティマイザー
- ビューポートからのスナップショットキャプチャ
- オプションライブラリ用デペンデンシーインストーラー

**シングルコマンド** — スナップ、フリーズ、ジョイントミラー、ウェイトコピーなど、22の即実行コマンド

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

- Autodesk Maya 2023以降
- Python 3.9+（Mayaに同梱）

### サードパーティライブラリ依存

一部のツールは、Maya に標準で含まれていない追加ライブラリを必要とします。
必要なライブラリがインストールされていない場合、これらのツールは起動しません。

| ツール | カテゴリ | 必要なライブラリ |
|--------|----------|-----------------|
| Bounding Box Creator | Model | numpy, scipy |
| Retarget Mesh | Model | numpy, scipy |
| Retarget Transforms | Model | numpy |
| Mesh Fitter | Model | trimesh, rtree, fast-simplification |
| BlendShape Transfer | Model | trimesh, rtree, fast-simplification |
| Snapshot Capture | Common | Pillow |


これらのライブラリは、FakeTools に同梱されている **Dependency Installer**（FakeTools > Common > Dependency Installer）からインストールできます。Maya を起動せずにリポジトリルートの `install_dependencies.bat` を実行してインストールすることも可能です。

また一部のツールで追加ライブラリをインストールすると機能が向上するものがあります。

| ツール | カテゴリ | 追加ライブラリ | 効果 |
|--------|----------|----------------|------|
| Snapshot Capture | Common | aggdraw | アノテーションのアンチエイリアシングあり保存 |
| Snapshot Capture | Common | mss | 高速スクリーンショットキャプチャ |


## ライセンス

このプロジェクトはMITライセンスの下で公開されています。詳細は[LICENSE](LICENSE)ファイルを参照してください。
