---
title: glTF Importer
category: common
description: Blender経由でglTF/GLBファイルをMayaにインポート
lang: ja
lang-ref: gltf_importer
order: 40
---

## 概要

glTF/GLBファイルをBlenderを使用してFBXに変換し、Mayaにインポートするツールです。

MayaはglTF形式を直接サポートしていませんが、このツールを使用することで、Blenderをバックエンドとして活用し、glTF/GLBファイルをシームレスにインポートできます。

## 必要条件

- **Blender** がインストールされている必要があります

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
import faketools.tools.common.gltf_importer.ui
faketools.tools.common.gltf_importer.ui.show_ui()
```

## インターフェース

### Input File

インポートするglTF/GLBファイルを指定します。`...` ボタンをクリックしてファイルブラウザから選択できます。

### Output Directory

FBXファイルとテクスチャの出力先ディレクトリを指定します。空のままにすると、入力ファイルと同じディレクトリに出力されます。

### Shader Type

インポート時に使用するシェーダータイプを選択します。

| オプション | 説明 |
|-----------|------|
| Auto Detect | FBXに含まれるマテリアルをそのまま使用 |
| Arnold | Arnoldシェーダーに変換 |
| Stingray PBS | Stingray PBSシェーダーに変換 |
| Standard | Standardシェーダーに変換 |

### Import ボタン

設定に基づいてインポートを実行します。

## 処理フロー

1. **GLB→FBX変換**: BlenderのヘッドレスモードでglTF/GLBファイルをFBXに変換
2. **FBXインポート**: 変換されたFBXファイルをMayaにインポート
3. **テクスチャ処理**: 埋め込みテクスチャを抽出し、パスを更新
4. **マテリアル変換**: 選択したシェーダータイプに応じてマテリアルを変換（Auto Detect以外の場合）

## コマンドラインからの使用

UIを使用せずにスクリプトから直接インポートすることも可能です。

```python
from faketools.tools.common.gltf_importer import command

# 基本的な使用方法
imported_nodes = command.import_gltf_file(
    file_path="path/to/model.glb",
    shader_type="auto"
)

# 出力ディレクトリを指定
imported_nodes = command.import_gltf_file(
    file_path="path/to/model.glb",
    output_dir="path/to/output",
    shader_type="arnold"
)
```

## 注意事項

- 変換中にBlenderがバックグラウンドで実行されます
- 大きなファイルの場合、変換に時間がかかることがあります（タイムアウト: 5分）
- テクスチャは `{ファイル名}.fbm` ディレクトリに抽出されます
