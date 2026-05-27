---
title: ツールバー
hidden: true
parent: code_editor
parent_title: Code Editor
lang: ja
lang-ref: code_editor_toolbar
---

## 概要

ツールバーは、ファイルの作成や保存、コードの実行などの主要なアクションに素早くアクセスできます。


![image](../../images/common/code_editor/toolbar.png)

## 機能説明

**![image](../../images/common/code_editor/toggle_normal.svg) Toggle File Explorer**

- ファイルエクスプローラーの表示/非表示を切り替えます。

**![image](../../images/common/code_editor/refresh_normal.svg) Refresh File Explorer**

- ファイルエクスプローラーのツリーを手動で更新します。
- 別の Maya インスタンスや外部アプリケーションで作成・変更されたファイルを反映させたい場合に使用します。
- ファイルエクスプローラーが非表示の場合、このボタンは無効化されます。

**![image](../../images/common/code_editor/run_normal.svg) Run Code**

- 現在アクティブなエディタのコードを実行します。\
コードを選択している場合は、選択部分のみが実行されます。

**![image](../../images/common/code_editor/new_python_normal.svg) New Python File / ![image](../../images/common/code_editor/new_mel_normal.svg) New MEL File**

- 言語ごとに独立した新規ファイルアイコンが並びます。アイコンには言語の頭文字 (P / M) と、その言語のアクセントカラーが描かれています。
- クリックすると、ファイル名を入力するダイアログが表示され、対応する拡張子 (`.py` / `.mel`) のファイルが作成されます。

![image](../../images/common/code_editor/new-file.png)

- ファイル名を入力して「OK」をクリックすると、新しいファイルが作成され、タブが開きます。
- ショートカット **Ctrl+N** はデフォルト言語 ( Python ) のファイルを作成します。MEL ファイルはツールバーの専用ボタンか、ファイルエクスプローラーの右クリックメニューから作成してください。
- 新しい言語プロファイルが追加されると、ツールバーにも自動的にそのアイコンが追加される仕組みになっています。

**![image](../../images/common/code_editor/save_normal.svg) Save Current File**

- 現在アクティブなエディタの内容を保存します。\
保存されていない変更がある場合、タブにアスタリスク (*) が表示されます。

**![image](../../images/common/code_editor/saveall_normal.svg) Save All Files**

- すべての開いているエディタの内容を保存します。

**![image](../../images/common/code_editor/folder_normal.svg) Open Root Directory**

- ワークスペースのルートディレクトリを OS 標準のファイルエクスプローラーで開きます。

**![image](../../images/common/code_editor/clear_normal.svg) Clear Console**

- コンソールの内容をクリアします。

**![image](../../images/common/code_editor/echo_normal.svg) Toggle Echo All Commands**

- ターミナルのエコーモードの ON/OFF を切り替えます。
- アイコンが ![image](../../images/common/code_editor/echo_active_normal.svg) のとき、すべてのコマンドが Maya の Script Editor にエコーされます。

**![image](../../images/common/code_editor/shelf_normal.svg) Add to Shelf**

- 現在選択中のコードを、アクティブな Maya シェルフにシェルフボタンとして追加します。
- コードが選択されていない場合、選択を促すダイアログが表示されます。
- シェルフボタンの sourceType / ラベル / アイコンは、現在のタブの言語に従います ( Python: `python` / `Python` / `pythonFamily.png` 、MEL: `mel` / `MEL` / `commandButton.png` )。
- この機能はコードを選択した状態でコンテキストメニュー（右クリック）からも利用できます。

**![image](../../images/common/code_editor/wordwrap_normal.svg) Toggle Word Wrap**

- コードエディターの折り返し表示の ON/OFF を切り替えます。
- ON の場合、長い行がエディタの幅で折り返されます。OFF の場合、水平スクロールバーが表示されます。
- この設定はセッション間で保持されます。
- アイコンが ![image](../../images/common/code_editor/wordwrap_active_normal.svg) のとき、折り返し表示が有効になっています。

**![image](../../images/common/code_editor/foldall_normal.svg) Fold All**

- 現在のエディタの全ての折り畳み可能なコードブロックを折り畳みます。

**![image](../../images/common/code_editor/unfoldall_normal.svg) Unfold All**

- 現在のエディタの全ての折り畳まれたコードブロックを展開します。

**![image](../../images/common/code_editor/autocomplete_active_normal.svg) Toggle Autocomplete (Ctrl+Space)**

- オートコンプリート機能の ON/OFF を切り替えます。
- OFF 時は jedi への問い合わせが一切行われないため、タイピング時の遅延をゼロにできます (低スペック PC 向け)。
- この設定はセッション間で保持されます。
- jedi が未インストールの場合、このボタンは自動的に無効化されます。
- 動作の詳細は [コードエディターのオートコンプリート](code_editor_editor.html) を参照してください。
- アイコンが ![image](../../images/common/code_editor/autocomplete_normal.svg) のとき、オートコンプリートが無効になっています。

**![image](../../images/common/code_editor/terminal_normal.svg) Toggle Terminal Visibility**

- ターミナルの表示/非表示を切り替えます。
- 非表示時は、エディタがターミナル領域まで広がります。
- 非表示にする直前のターミナル高さが保存され、再表示時に復元されます。
- この設定はセッション間で保持されます。

**![image](../../images/common/code_editor/swap_normal.svg) Swap Editor/Terminal Position**

- コードエディタとターミナルの位置を上下に入れ替えます。

**![image](../../images/common/code_editor/insert_normal.svg) Insert ( 分割ボタン )**

ツールバーの右端に、他のボタンから少し離して配置された分割ボタンです。現在 Maya で選択しているノード名を、アクティブなエディタのカーソル位置に挿入します。

- **本体（アイコン）をクリック**: 現在選択中の挿入コマンドを実行します。
- **![image](../../images/common/code_editor/chevron_down.svg) ドロップダウン**: 挿入コマンドを切り替えます。ドロップダウンでの選択は「どのコマンドを現在のものにするか」を切り替えるだけで、**コマンドは実行されません** ( 実行は本体クリック、またはエディタの右クリックメニューから )。
- 挿入されるテキストは**現在のタブの言語に従って整形**されます。その言語に対応していないコマンドはドロップダウンで無効化され、対応コマンドが 1 つも無い場合はボタン全体が無効になります。
- 何も選択していない状態で実行すると、ターミナルに選択を促すメッセージが表示されます。
- どのコマンドが現在選択中かは、ボタンのツールチップで確認できます。
- 同じ機能はエディタの右クリックメニューの**先頭**からも利用できます ( [コードエディター](code_editor_editor.html) のコンテキストメニューを参照 )。

利用できる挿入コマンドは以下の通りです。

| コマンド | 動作 |
|---|---|
| Selected Node Name | 最初に選択しているノード名を 1 つの文字列として挿入 ( Python: `"pCube1"` ) |
| Selected Node Names ( List ) | 選択しているノード名すべてをリストとして挿入 ( Python: `["pCube1", "pCube2"]` ) |

## ショートカットキー

ツールバーの各アクションには、以下のショートカットキーが割り当てられています。

| アクション               | ショートカットキー      |
|------------------------|-----------------------|
| Create New File        | Ctrl+N                |
| Run Code               | Ctrl+Shift+Enter, Numpad Enter |
| Save Current File      | Ctrl+S                |
| Save All Files         | Ctrl+Shift+S          |
| Fold All               | Ctrl+Alt+[            |
| Unfold All             | Ctrl+Alt+]            |
| Toggle Autocomplete    | Ctrl+Space            |
