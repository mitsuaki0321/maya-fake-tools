---
title: Mesh Importer
category: model
description: glTF/GLBおよびPLYファイルをMayaにインポート
lang: ja
lang-ref: mesh_importer
order: 40
---

## 概要

3DメッシュファイルをMayaにインポートするツールです。以下のフォーマットに対応しています：

- **glTF/GLB**: Blenderを使用してFBXに変換し、マテリアルとテクスチャ付きでインポート
- **PLY**: 頂点カラー対応で直接インポート（trimeshが必要）

## 必要条件

### glTF/GLBインポート

- **Blender** がインストールされている必要があります

### PLYインポート

- **trimesh** がインストールされている必要があります（FakeTools > Dependency Installerからインストール可能）

### Blenderパスの検知順序

Blenderは以下の順序で自動検出されます：

1. **環境変数 `BLENDER_PATH`**（優先度: 最高）
   - ユーザーが明示的に設定したパスを使用

2. **標準インストールディレクトリ**
   - **Windows**: `C:/Program Files/Blender Foundation/Blender X.X/blender.exe`
     - 複数バージョンがある場合、最新バージョンを優先
   - **macOS**: `/Applications/Blender.app/Contents/MacOS/Blender`
   - **Linux**: `/usr/bin/blender` または `/usr/local/bin/blender`

3. **システムPATH**（優先度: 最低）
   - `where blender`（Windows）または `which blender`（macOS/Linux）で検索

Steam版やポータブル版のBlenderは自動検出されない場合があります。その場合は `BLENDER_PATH` 環境変数を設定してください。

## 起動方法

専用メニューか以下のコマンドで起動します。

```python
import faketools.tools.model.mesh_importer.ui
faketools.tools.model.mesh_importer.ui.show_ui()
```

## インターフェース

### Input File

インポートするファイルを指定します。glTF (.gltf)、GLB (.glb)、PLY (.ply) 形式に対応しています。`...` ボタンをクリックしてファイルブラウザから選択できます。

### Output Directory

FBXファイルとテクスチャの出力先ディレクトリを指定します（glTF/GLBのみ）。空のままにすると、入力ファイルと同じディレクトリに出力されます。PLYファイルの場合、このオプションは無効になります。

### Shader Type

インポート時に使用するシェーダータイプを選択します（glTF/GLBのみ）。PLYファイルの場合、このオプションは無効になります。

| オプション | 説明 |
|-----------|------|
| Auto Detect | FBXに含まれるマテリアルをそのまま使用 |
| Arnold | Arnoldシェーダーに変換 |
| Stingray PBS | Stingray PBSシェーダーに変換 |
| Standard | Standardシェーダーに変換 |

### Import ボタン

設定に基づいてインポートを実行します。

## 処理フロー

### glTF/GLB

1. **GLB→FBX変換**: BlenderのヘッドレスモードでglTF/GLBファイルをFBXに変換
2. **FBXインポート**: 変換されたFBXファイルをMayaにインポート
3. **テクスチャ処理**: 埋め込みテクスチャを抽出し、パスを更新
4. **マテリアル変換**: 選択したシェーダータイプに応じてマテリアルを変換（Auto Detect以外の場合）

### PLY

1. **ファイル解析**: trimeshを使用してPLYファイルを読み込み
2. **メッシュ作成**: Maya APIを使用してポリゴンメッシュを作成
3. **頂点カラー**: PLYファイルに頂点カラーが含まれている場合、適用
4. **マテリアル割り当て**: デフォルトマテリアル（initialShadingGroup）を割り当て

## コマンドラインからの使用

UIを使用せずにスクリプトから直接インポートすることも可能です。

```python
from faketools.tools.model.mesh_importer import command

# 統合インポート（拡張子でフォーマットを自動判別）
imported_nodes = command.import_file(
    file_path="path/to/model.glb",
    shader_type="auto"
)

# glTF/GLB（出力ディレクトリを指定）
imported_nodes = command.import_gltf_file(
    file_path="path/to/model.glb",
    output_dir="path/to/output",
    shader_type="arnold"
)

# PLYインポート
imported_nodes = command.import_ply_file(
    file_path="path/to/scan.ply"
)
```

## 注意事項

- glTF/GLB変換中にBlenderがバックグラウンドで実行されます
- 大きなglTF/GLBファイルの場合、変換に時間がかかることがあります（タイムアウト: 5分）
- テクスチャは `{ファイル名}.fbm` ディレクトリに抽出されます
- PLYの頂点カラーはMayaの `colorSet` として適用され、ビューポートに表示されます
