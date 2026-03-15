# FakeTools インストールガイド

このガイドでは、FakeTools 本体のインストールから、外部ツール（ffmpeg、OpenRV）や Python ライブラリの導入までを順を追って説明します。

---

## 目次

1. [FakeTools 本体のインストール](#1-faketools-本体のインストール)
2. [Python ライブラリのインストール](#2-python-ライブラリのインストール)
3. [ffmpeg のインストール](#3-ffmpeg-のインストール)
4. [OpenRV の設定（任意）](#4-openrv-の設定任意)
5. [Maya 起動時に自動でメニューを読み込む](#5-maya-起動時に自動でメニューを読み込む)
6. [トラブルシューティング](#6-トラブルシューティング)

---

## 1. FakeTools 本体のインストール

### 1-1. ダウンロード

[Releases ページ](https://github.com/mitsuaki0321/maya-fake-tools/releases) から最新の `maya-fake-tools_vX.X.X.zip` をダウンロードします。

### 1-2. 展開

zip を任意のフォルダに展開します。

```
例: C:/maya_tools/maya-fake-tools/
```

展開後、以下のようなフォルダ構成になっていれば OK です。

```
C:/maya_tools/maya-fake-tools/
├── faketools.mod
├── .env.example
├── docs/           ← ブラウザで docs/index.html を開くとドキュメントが読めます
├── plug-ins/
└── scripts/
    └── faketools/
```

### 1-3. Maya にモジュールパスを登録する

Maya が FakeTools を認識できるように、展開したフォルダを `MAYA_MODULE_PATH` 環境変数に追加します。

#### 方法 A: Maya.env に書く（おすすめ）

Maya.env ファイルを開き、以下の行を追加します。

```
MAYA_MODULE_PATH = C:/maya_tools/maya-fake-tools
```

Maya.env の場所:

```
C:\Users\<ユーザー名>\Documents\maya\<バージョン>\Maya.env
```

> **ヒント**: Maya.env が存在しない場合は、新しくテキストファイルとして作成してください。

#### 方法 B: Windows のシステム環境変数に設定する

1. Windows の検索バーで「環境変数」と入力し、「システム環境変数の編集」を開く
2. 「環境変数」ボタンをクリック
3. ユーザー環境変数の「新規」をクリック
4. 変数名: `MAYA_MODULE_PATH`、値: `C:/maya_tools/maya-fake-tools` を入力
5. OK で閉じる

> **注意**: 既に `MAYA_MODULE_PATH` がある場合は、既存の値の末尾に `;C:/maya_tools/maya-fake-tools` を追加してください（セミコロンで区切る）。

### 1-4. メニューを表示する

Maya を起動（または再起動）して、スクリプトエディタで以下を実行します。

```python
import faketools.menu
faketools.menu.add_menu()
```

メニューバーに **FakeTools** メニューが表示されれば成功です。

> 起動時に自動でメニューを表示したい場合は「[5. Maya 起動時に自動でメニューを読み込む](#5-maya-起動時に自動でメニューを読み込む)」を参照してください。

---

## 2. Python ライブラリのインストール

一部のツールは追加の Python ライブラリを必要とします。FakeTools には **Dependency Installer** が同梱されており、Maya 内からライブラリをインストールできます。

### 2-1. 対象パッケージ一覧

| パッケージ | 使用ツール | 必須 |
|-----------|-----------|:----:|
| numpy | Bounding Box Creator, Mesh Retargeter | Yes |
| scipy | Bounding Box Creator, Mesh Retargeter | Yes |
| trimesh | Mesh Fitter, BlendShape Transfer | Yes |
| rtree | Mesh Fitter, BlendShape Transfer | Yes |
| fast-simplification | Mesh Fitter, BlendShape Transfer | Yes |
| Pillow | Snapshot Capture | Yes |
| aggdraw | Snapshot Capture | No |
| mss | Snapshot Capture | No |

> **補足**: 「必須: No」のパッケージは、なくてもツールは動作しますが、インストールすると機能が向上します（アンチエイリアスありの描画、高速スクリーンキャプチャなど）。

### 2-2. Dependency Installer の使い方

1. Maya メニューから **FakeTools > Common > Dependency Installer** を開く

2. **Maya Version** で対象のバージョンを確認する（現在起動中のバージョンが自動選択されます）

3. **Install Location** でインストール先を選択する
   - **Custom path（おすすめ）**: 任意の場所にインストールします。Maya 本体のフォルダを汚さないため、こちらを推奨します。管理者権限も不要です
   - **Standard (Maya site-packages)**: Maya 標準の場所にインストールします。管理者権限が必要な場合があります

4. **Select All Missing** ボタンで未インストールのパッケージを一括選択する

5. 社内ネットワークなどプロキシを経由する必要がある場合は、**Proxy Settings** セクションのチェックを有効にして、プロキシアドレスを入力してください（例: `http://proxy.example.com:8080`）。不要な場合はそのままで構いません

6. **Install Selected** ボタンを押してインストールを実行する

7. インストールが完了すると、パッケージ一覧が自動的に更新されます。Status が緑色の **Installed** になっていれば成功です

### 2-3. Custom path を使う場合の追加設定

Custom path にインストールした場合、FakeTools がそのパスを認識できるように設定が必要です。以下のいずれかの方法で設定してください。

#### 方法 A: .env ファイルで設定する（おすすめ）

FakeTools フォルダ内の `.env.example` をコピーして `.env` にリネームし、中身を編集してパスを設定します。

```
FAKETOOLS_SITE_PACKAGES=D:/my_packages
```

先頭の `#` を外して、パスを Dependency Installer で指定した場所に書き換えてください。FakeTools が次回読み込まれるときに、このパスが自動的に認識されます。

#### 方法 B: userSetup.py で設定する

「[5. Maya 起動時に自動でメニューを読み込む](#5-maya-起動時に自動でメニューを読み込む)」で紹介する `userSetup.py` に、以下のようにパスを追加する方法もあります。

```python
import sys
sys.path.insert(0, "D:/my_packages/2025/site-packages")
```

パスの `2025` の部分はお使いの Maya バージョンに合わせてください。実際のインストール先は Dependency Installer で Custom path を指定したときに `<指定したパス>/<Maya バージョン>/site-packages/` という構成で作成されます。

---

## 3. ffmpeg のインストール

一部のツール（VP Compositor、Snapshot Capture、Sync Player など）で動画の書き出しや再生に ffmpeg を使用します。これらの機能を使わない場合はインストール不要です。

### 3-1. 既に ffmpeg がインストールされている場合

ffmpeg が既に PC にインストールされている場合は、新たにダウンロードする必要はありません。`ffmpeg.exe` のあるフォルダのパスだけ確認して「[3-3. Maya から使えるようにする](#3-3-maya-から使えるようにする)」に進んでください。

コマンドプロンプトで以下を実行すると、インストール済みかどうかを確認できます。

```
where ffmpeg
```

パスが表示されればインストール済みです。

> **コマンドプロンプトの開き方**: キーボードの `Windows キー` を押して「cmd」と入力し、表示された「コマンドプロンプト」をクリックして開きます。

### 3-2. 新規にダウンロードする場合

1. [https://www.gyan.dev/ffmpeg/builds/](https://www.gyan.dev/ffmpeg/builds/) にアクセス
2. **release builds** セクションから `ffmpeg-release-essentials.zip` をダウンロード
3. zip を展開し、中のフォルダを分かりやすい場所に移動する

```
例: C:/tools/ffmpeg/
```

展開後の構成:

```
C:/tools/ffmpeg/
├── bin/
│   ├── ffmpeg.exe    ← これが必要
│   ├── ffplay.exe
│   └── ffprobe.exe
├── doc/
└── ...
```

### 3-3. Maya から使えるようにする

Maya が ffmpeg を見つけられるように、`ffmpeg.exe` があるフォルダを PATH に追加します。

#### 方法 A: Maya.env に書く（おすすめ）

Maya.env に以下の行を追加します。

```
PATH = C:/tools/ffmpeg/bin
```

Maya.env の場所:

```
C:\Users\<ユーザー名>\Documents\maya\<バージョン>\Maya.env
```

> **注意**: Maya.env の `PATH` は既存の PATH に追加される形で動作します。

#### 方法 B: Windows のシステム環境変数に設定する

1. Windows の検索バーで「環境変数」と入力し、「システム環境変数の編集」を開く
2. 「環境変数」ボタンをクリック
3. **ユーザー環境変数**の `Path` を選択して「編集」をクリック
4. 「新規」をクリックして `C:\tools\ffmpeg\bin` を追加
5. OK で閉じる

### 3-4. 動作確認

Maya を再起動し、スクリプトエディタで以下を実行します。

```python
import shutil
print(shutil.which("ffmpeg"))
```

ffmpeg.exe のパスが表示されれば成功です。`None` と表示される場合は PATH の設定を見直してください。

---

## 4. OpenRV の設定（任意）

**VP Compositor** のプレイブラストを外部プレイヤーで再生したい場合に利用できます。OpenRV がなくても、FakeTools 内蔵の Sync Player やシステムの既定プレイヤーで再生可能です。

> **注意**: OpenRV はインストーラーが配布されていないオープンソースプロジェクトです。利用するにはソースコードからビルドする必要があります。ビルド手順は [OpenRV の GitHub リポジトリ](https://github.com/AcademySoftwareFoundation/OpenRV) を参照してください。
>
> 以下の手順は、**既にビルド済みの OpenRV が手元にある場合**の設定方法です。

### 4-1. Maya から使えるようにする

FakeTools は `rvpush` コマンドを使って OpenRV と連携します。`rvpush.exe` があるフォルダを PATH に追加してください。

#### 方法 A: Maya.env に書く（おすすめ）

Maya.env に以下の行を追加します。ffmpeg も設定済みの場合は、セミコロン（`;`）でつないで 1 行にまとめます。

OpenRV のみの場合:

```
PATH = C:/OpenRV/bin
```

ffmpeg と両方ある場合:

```
PATH = C:/OpenRV/bin;C:/tools/ffmpeg/bin
```

#### 方法 B: Windows のシステム環境変数に設定する

ffmpeg と同じ手順で、`rvpush.exe` があるフォルダを Windows のユーザー環境変数 `Path` に追加します。

### 4-2. 動作確認

Maya を再起動し、スクリプトエディタで以下を実行します。

```python
import shutil
print(shutil.which("rvpush"))
```

パスが表示されれば FakeTools から OpenRV を利用できます。

---

## 5. Maya 起動時に自動でメニューを読み込む

毎回スクリプトエディタでコマンドを実行するのが手間な場合、`userSetup.py` を使って自動化できます。

### 5-1. userSetup.py を作成・編集する

以下の場所にある `userSetup.py` を開きます（存在しない場合は新規作成してください）。

```
C:\Users\<ユーザー名>\Documents\maya\<バージョン>\scripts\userSetup.py
```

以下の内容を追加します。

```python
import maya.cmds as cmds

def _load_faketools():
    import faketools.menu
    faketools.menu.add_menu()

cmds.evalDeferred(_load_faketools)
```

> **なぜ `evalDeferred` を使うのか**: Maya の起動処理が完了してからメニューを追加するためです。直接呼び出すとエラーになる場合があります。

### 5-2. Maya を再起動する

Maya を再起動すると、起動時に自動で FakeTools メニューが表示されるようになります。

---

## 6. トラブルシューティング

### FakeTools メニューが表示されない

- `MAYA_MODULE_PATH` が正しく設定されているか確認してください
- スクリプトエディタで以下を実行して、モジュールが認識されているか確認します:
  ```python
  import maya.cmds as cmds
  print(cmds.moduleInfo(listModules=True))
  ```
  `maya_fake_tools` が一覧に含まれていれば、モジュールパスは正しく設定されています

### Dependency Installer で「管理者権限が必要」と表示される

Standard (Maya site-packages) にインストールしようとすると、管理者権限が求められることがあります。Maya を管理者として起動するか、**Custom path** を使用してください（Custom path なら管理者権限は不要です）。

### ffmpeg / rvpush が見つからない

- Maya.env または Windows 環境変数で PATH を設定した後、**Maya を再起動**してください
- Maya のスクリプトエディタで以下を実行して確認できます:
  ```python
  import shutil
  print(shutil.which("ffmpeg"))
  print(shutil.which("rvpush"))
  ```
  パスが表示されれば認識されています。`None` の場合は PATH の設定を見直してください
- Maya.env で PATH を設定している場合、複数のパスはセミコロン（`;`）で区切ってください

### pip が使えない

Dependency Installer で「pip が見つからない」旨のエラーが出る場合は、pip のセットアップが必要です。以下の手順で行ってください。

1. コマンドプロンプトを開く（`Windows キー` → 「cmd」と入力 → 「コマンドプロンプト」をクリック）
2. 以下のコマンドをコピー＆ペーストして実行する（Maya のバージョン番号は実際のものに置き換えてください）:
   ```
   "C:\Program Files\Autodesk\Maya2025\bin\mayapy.exe" -m ensurepip
   ```
3. 「Successfully installed pip-...」のようなメッセージが表示されれば完了です
4. Maya を再起動して、もう一度 Dependency Installer を開いてください
