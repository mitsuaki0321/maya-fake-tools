---
title: Dependency Installer
category: common
description: FakeTools のオプション依存パッケージをインストールするツール
lang: ja
lang-ref: dependency_installer
order: 90
---

## 概要

Dependency Installer は、FakeTools の一部ツールが必要とするオプションの Python パッケージを Maya 内から簡単にインストールするためのツールです。\
コマンドラインで `mayapy -m pip install` を実行する代わりに、GUI でパッケージの状態確認とインストールを行えます。

以下の起動方法に対応しています。

| 起動方法 | 説明 |
|----------|------|
| Maya 内メニュー | FakeTools > Common > Dependency Installer |
| スタンドアロン | リポジトリルートの `install_dependencies.bat` をダブルクリック |


## 対象パッケージ

| パッケージ | 使用ツール | 必須 |
|-----------|-----------|------|
| numpy | Bounding Box Creator, Mesh Retargeter | Yes |
| scipy | Bounding Box Creator, Mesh Retargeter | Yes |
| trimesh | Mesh Fitter, BlendShape Transfer | Yes |
| rtree | Mesh Fitter, BlendShape Transfer | Yes |
| fast-simplification | Mesh Fitter, BlendShape Transfer | Yes |
| Pillow | Snapshot Capture, VP Compositor | Yes |
| aggdraw | Snapshot Capture | No |
| mss | Snapshot Capture | No |
| robust-laplacian | Robust Weight Transfer | No |


## 起動方法

### Maya 内

専用のメニューか、以下のコマンドでツールを起動します。

```python
import faketools.tools.common.dependency_installer.ui
faketools.tools.common.dependency_installer.ui.show_ui()
```

![image](../../images/common/dependency_installer/image001.png)

### スタンドアロン

リポジトリルートにある `install_dependencies.bat` をダブルクリックします。\
インストール済みの Maya（2023〜2026）を自動検出し、最新バージョンの mayapy で UI を起動します。


## 使用方法

### 基本的な手順

1. **Maya Version** で対象の Maya バージョンを選択します。Maya 内起動時は現在のバージョンがデフォルトで選択されます。

2. **Install Location** でインストール先を選択します。

3. パッケージテーブルで各パッケージの状態を確認します。

4. 未インストールのパッケージにチェックを入れるか、`Select All Missing` ボタンで一括選択します。

5. `Install Selected` ボタンを押してインストールを実行します。

6. 完了後、テーブルが自動的にリフレッシュされます。


## Maya Version セクション

対象の Maya バージョンを選択します。`C:\Program Files\Autodesk\Maya*` をスキャンして検出されたバージョンが一覧表示されます。

- **Maya 内起動時**: 現在実行中の Maya バージョンがデフォルトで選択されます。パッケージのステータスは現在の Maya プロセスで確認されるため、`userSetup.py` で追加したパスも反映されます。
- **異なるバージョン選択時 / スタンドアロン**: 対象バージョンの mayapy を subprocess で起動してパッケージの状態を確認します。


## Install Location セクション

- **Standard (Maya site-packages)**: Maya 標準の site-packages にインストールします。管理者権限が必要な場合があります。
- **Custom path**: 任意のディレクトリにインストールします。実際のインストール先は `<指定パス>/<Mayaバージョン>/site-packages/` になります。

カスタムパスを使用する場合、FakeTools 起動時にそのパスを自動的に読み込むように `.env` ファイルの設定が必要です（後述）。


## Proxy Settings セクション

プロキシ環境でインストールする場合に使用します。チェックボックスで有効化し、HTTP_PROXY / HTTPS_PROXY を入力します。

- 入力例: `http://user:pass@proxy:3128`
- プロキシ設定は**セッション限り**で保存されません。


## パッケージテーブル

各パッケージの状態が 5 列で表示されます。

| 列 | 説明 |
|----|------|
| Package | パッケージ名。未インストールの場合はチェックボックスが表示されます |
| Status | Installed（緑）/ Missing（必須: 赤、オプション: オレンジ） |
| Version | インストール済みの場合、バージョン番号 |
| Required By | このパッケージを必要とするツール |
| Location | インストール済みの場合、インストール先ディレクトリ（site-packages パス） |


## ボタン

| ボタン | 説明 |
|--------|------|
| Select All Missing | 未インストールのパッケージを一括選択 |
| Install Selected | チェックされたパッケージをインストール |
| Refresh | パッケージ状態を再取得 |


## カスタムパスの自動読み込み

カスタムパスにインストールしたパッケージを Maya 起動時に読み込むには、以下のいずれかの方法でインストール先のパスを Python の検索パスに追加してください。

### 方法 1: .env ファイル（推奨）

リポジトリルートに `.env` ファイルを作成します。`.env.example` をコピーして `.env` にリネームし、パスを設定してください。

```
FAKETOOLS_SITE_PACKAGES=D:/my_packages
```

設定後、FakeTools パッケージの初期化時に `<FAKETOOLS_SITE_PACKAGES>/<Mayaバージョン>/site-packages/` が `sys.path` に自動追加されます。

> **Note**: `.env` ファイルは `.gitignore` に含まれているため、リポジトリにはコミットされません。

### 方法 2: userSetup.py で手動追加

Maya の `userSetup.py` でインストール先のパスを `sys.path` に直接追加することもできます。

```python
import sys
sys.path.insert(0, "D:/my_packages/2025/site-packages")
```

> **Note**: `userSetup.py` は Maya 起動時にのみ実行されるため、スタンドアロンモードのステータス表示には反映されません。


## パッケージレジストリ（versions）

対象パッケージの一覧は `versions/` ディレクトリの JSON ファイルで管理されています。

```
dependency_installer/versions/
├── common.json       # デフォルト（全 Maya バージョン共通）
└── maya2023.json     # Maya 2023 固有の設定
```

### 解決順序

選択した Maya バージョンに応じて、以下の順序でファイルが読み込まれます。

1. `versions/maya{バージョン}.json`（例: `maya2023.json`）が存在すればそれを使用
2. 存在しなければ `versions/common.json` にフォールバック

バージョン固有のファイルが見つかった場合、`common.json` とのマージは行われず、そのファイルの内容が**そのまま全体のレジストリ**として使用されます。

### JSON フォーマット

各エントリは以下のフィールドを持ちます。

```json
{
    "pip_name": "fast-simplification",
    "import_name": "fast_simplification",
    "required_by": ["Mesh Fitter", "BlendShape Transfer"],
    "optional": false,
    "version": "==0.1.12"
}
```

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| `pip_name` | string | Yes | pip パッケージ名（`pip install` に渡す名前） |
| `import_name` | string | Yes | Python import 名（`import xxx` の `xxx`） |
| `required_by` | string[] | Yes | このパッケージを使用するツールの一覧 |
| `optional` | bool | Yes | `false`: 必須（Missing 時に赤表示）、`true`: オプション（オレンジ表示） |
| `version` | string | No | PEP 440 バージョン制約。省略時はバージョン指定なし |

### version フィールド

`version` フィールドには PEP 440 形式のバージョン制約を指定します。先頭が `=`, `<`, `>`, `!`, `~` のいずれかで始まる値が有効です。

| 指定例 | pip コマンド | 説明 |
|--------|-------------|------|
| `"==0.1.12"` | `pip install fast-simplification==0.1.12` | 完全一致 |
| `">=1.0,<2.0"` | `pip install package>=1.0,<2.0` | 範囲指定 |
| `"~=1.4"` | `pip install package~=1.4` | 互換リリース（`>=1.4, <2.0`） |
| （省略） | `pip install package` | 最新版をインストール |

### バージョン固有ファイルの作成例

特定の Maya バージョンで異なるパッケージバージョンが必要な場合、`common.json` をコピーして `maya{バージョン}.json` を作成し、該当パッケージの `version` フィールドを変更します。

```bash
# 例: Maya 2024 用のレジストリを作成
cp versions/common.json versions/maya2024.json
# maya2024.json を編集して version を調整
```


## 注意事項

- Standard インストールでは管理者権限が必要な場合があります。Maya を管理者として実行してください。
- pip が利用できない場合は、`mayapy -m ensurepip` を実行してください。
- スタンドアロン起動時は `userSetup.py` で追加されたパスは検知されません。`.env` の `FAKETOOLS_SITE_PACKAGES` で指定されたパスは検知されます。
- インストールに失敗した場合、pip のエラーメッセージがステータスラベルに赤文字で表示されます。詳細はログにも出力されます。
- インストール実行時は外部コンソールウィンドウが開き、pip の進捗をリアルタイムで確認できます。
