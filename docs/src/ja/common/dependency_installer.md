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
| Pillow | Snapshot Capture | Yes |
| aggdraw | Snapshot Capture | No |
| mss | Snapshot Capture | No |


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

各パッケージの状態が 4 列で表示されます。

| 列 | 説明 |
|----|------|
| Package | パッケージ名。未インストールの場合はチェックボックスが表示されます |
| Status | Installed（緑）/ Missing（必須: 赤、オプション: オレンジ） |
| Version | インストール済みの場合、バージョン番号 |
| Required By | このパッケージを必要とするツール |


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


## 注意事項

- Standard インストールでは管理者権限が必要な場合があります。Maya を管理者として実行してください。
- pip が利用できない場合は、`mayapy -m ensurepip` を実行してください。
- スタンドアロン起動時は `userSetup.py` で追加されたパスは検知されません。`.env` の `FAKETOOLS_SITE_PACKAGES` で指定されたパスは検知されます。
- インストールに失敗した場合、pip のエラーメッセージがステータスラベルとログに表示されます。
