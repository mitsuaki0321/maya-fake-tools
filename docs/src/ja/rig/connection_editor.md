---
title: Connection Editor
category: rig
description: 属性ツリーを左右に並べて接続・切断・値コピーを行う Connection Editor
lang: ja
lang-ref: connection_editor
order: 79
---

## 概要

Maya で属性の接続や値のコピーを行うためのサポートツールである **fake-connection-editor** を起動します。
属性ツリーを左右に並べ、ポート間のドラッグや選択ペアの操作で接続・切断・値コピーを行います。

主な特徴:

- 左右 2 ツリー + 中央オーバーレイによる接続線・ポートの可視化
- ポート間ドラッグで接続、空白へのドロップで切断、`Alt+Shift` 横断で一括切断
- 選択ペアの接続 / leaf 接続（子属性ごと）/ 値コピー（方向トグル準拠）
- 属性ロックを無視した接続（オプション）
- 型チップ・テキスト・表示オプションによる左右独立フィルタ
- マルチ属性のゴースト要素表示と接続時の実体化
- シーンの外部変更（接続・属性追加・ロック・Undo/Redo）へのライブ追従

    ![window](../../images/rig/connection_editor/window.png)

## 必要な追加インストール

このツールは外部パッケージ `fake_connection_editor` を別途必要とします。
未インストールの場合はログに警告が表示され、ツールは起動しません。

[fake-connection-editor リポジトリ](https://github.com/mitsuaki0321/fake-connection-editor)
からダウンロードし、`fake_connection_editor` フォルダを Maya のスクリプトパス
（例: `<ユーザー>/Documents/maya/scripts/`）に配置してください。

## 起動方法

専用のメニューか、以下のコマンドでツールを起動します。

```python
import faketools.tools.rig.connection_editor.ui
faketools.tools.rig.connection_editor.ui.show_ui()
```

外部ツールを直接起動する場合は以下のコマンドでも起動できます。

```python
import fake_connection_editor
fake_connection_editor.launch()
```

## 画面構成

ウィンドウは上から下へ、以下の領域で構成されます。各領域は左右独立で操作できます。

**メニューバー**

![menubar](../../images/rig/connection_editor/menubar-ui.png)

* `Options` : 強制接続 / 強制切断 / 接続先へのスクロールなどのオプションボックス（後述「メニュー」）。
* `Edit` : 属性の並び替え・属性名表示の切り替え（左右共通）。

**Load / Add ボタン**

![loadbutton](../../images/rig/connection_editor/loadbutton-ui.png)

* 左右それぞれにあり、選択ノードをそのツリーへ読み込みます。`Load` は置き換え、`Add` は追加です。

**フィルタ行**

![filter](../../images/rig/connection_editor/filter-ui.png)

* テキスト・型チップ・漏斗メニューで、表示する属性を左右独立に絞り込みます（後述「フィルタ」）。

**ノード名ヘッダ + 左右入替ボタン**

![header](../../images/rig/connection_editor/header-ui.png)

* 読み込み中のノード名を表示します。クリックするとその側のノードをシーンで選択します。中央の入替ボタンで左右をまるごと入れ替えます。

**左右ツリー + 中央接続レイヤー**

![tree](../../images/rig/connection_editor/tree-ui.png)

* 読み込まれたノードに対する属性の各ツリー情報と接続情報を描画します。
* 各属性の左または、右の丸型のアイコンは接続に使用するためののポートです。
* 各ポート間の矢印型の線がその属性同士の接続方向を示しています。

**アクションバー**

![actionbar](../../images/rig/connection_editor/actionbar-ui.png)

* 左右で選択した属性ペアに対して、方向トグルの向きで接続 / leaf 接続 / 値コピーを実行します（後述「アクションバー」）。

## 基本的な使い方

1. ノードを選択し、左右それぞれの `Load`（置き換え）/ `Add`（追加）ボタンで属性ツリーに読み込みます。

2. ポートからポートへドラッグして接続します。空白にドロップすると切断します。

3. 選択ペアをまとめて操作する場合は、左右で 1 つずつ属性を選び、アクションバーの方向トグルと `Connect` / `Connect Leaf` / `Copy Value` を使います。

4. 属性を右クリックすると、接続相手のノードの読み込みや現在値のクリップボードコピーができます（後述「右クリックメニュー」）。

シーンの外部変更には自動で追従します。


## 接続と切断

接続・切断はポートのドラッグ（直接操作）が基本です。選択状態とは無関係に、ポートそのものを掴んで操作します。

* **接続**
  * 出力側ポートから入力側ポートへドラッグします。ドラッグ中はカーソルに仮の線が追従し、接続できないポート / 属性はグレーアウトされます。

    ![connect](../../images/rig/connection_editor/connect.gif)
* **切断**
  * 入力側ポートを掴んで空白にドロップすると切断します。

    ![disconnect](../../images/rig/connection_editor/disconnect.gif)
* **つなぎ替え**
  * 既に接続されている入力ポートを掴むと、既存の線が外れてカーソルに付いてきます。別のポートに落とすと、その接続へつなぎ替わります。

    ![reconnect](../../images/rig/connection_editor/reconnect.gif)
* **横断切断**
  * `Alt+Shift` を押しながらドラッグすると、線を横切るように切る操作になり、横切った接続をまとめて切断します。

    ![cutter](../../images/rig/connection_editor/cutter.gif)

### ポートと接続線の見方

中央レイヤーのポート（丸）と接続線で、各属性の接続状態を表します。

![port-type](../../images/rig/connection_editor/port-type.png)

* **塗りつぶしのポート** : 接続済みの属性。
* **中空のポート** : 未接続の属性。
* **二重丸のポート** : 畳まれた親属性の中に、隠れた子の接続があることを示します。展開すると子の接続線が見えます。
* **ポートと線の色** : 属性のデータ型を表します（型チップの色と対応）。接続線は出力側の型色を引き継ぎます。

## アクションバー（選択ペアの操作）

ドラッグの代わりに、左右で選択した属性ペアをボタンで操作できます。属性が画面外にあるときや、子属性ごとの接続を行うときに使います。

![actionbar](../../images/rig/connection_editor/actionbar-ui.png)

1. 左ツリーと右ツリーで属性を 1 つずつ選択します。
2. 中央の方向トグル（`→` / `←`）で、どちらを出力（src）にするかを切り替えます。
3. 目的のボタンを押します。

* **Connect**
  * 選択ペアを方向トグルの向きで接続します。
* **Connect Leaf**
  * 親属性同士を選んで子属性ごとに接続します（例: `translate` → `translate` で `tx→tx, ty→ty, tz→tz`）。子の数が一致し、各子がスカラー型で互換である必要があります。
* **Copy Value**
  * 選択ペアの値を方向トグルの向きでコピーします。

選択が片側だけのときや接続できない組み合わせのときは、実行時に理由付きの警告が表示されます。

## 右クリックメニュー（コンテキストメニュー）

属性を右クリックすると、その属性（起点）を基点にした操作メニューが表示されます。アクションバーが左右の選択ペアを対象にするのに対し、こちらは**右クリックした 1 つの属性**を起点に動作します。各項目は条件を満たさないときグレーアウトされます。

![filter](../../images/rig/connection_editor/context.png)

* **Load Connected**
  * 起点属性の接続相手のノードを、反対側のツリーへ読み込みます（`Load` と同じく置き換え）。接続がある属性でのみ有効です。
* **Add Connected**
  * 起点属性の接続相手のノードを、反対側のツリーへ追加します（`Add` と同じく既存の読み込みに足す）。接続がある属性でのみ有効です。
* **Copy Attribute Value**
  * 起点属性の現在値をクリップボードへコピーします。数値（numeric）と行列（matrix）型でのみ有効です。

`Load Connected` / `Add Connected` は、接続をたどって相手ノードを手早く反対側に並べたいときに使います。例えば左ツリーで出力属性を右クリックして `Load Connected` を実行すると、その出力がつながっている先のノードが右ツリーに読み込まれます。

## フィルタ

各ツリーの表示属性を、左右独立に絞り込めます。フィルタ行はテキスト・型チップ・漏斗メニューの 3 つで構成されます。

![filter](../../images/rig/connection_editor/filter-ui.png)

* **テキストフィルタ**
  * 入力した文字列で属性名を絞り込みます。一致する属性の祖先は自動で展開されます。
* **型チップ（`N` / `B` / `M` / `C` / `D`）**
  * データ型で絞り込みます。チップの色は型の色（ポート色）と対応します。
    * `N` : numeric（数値・double3 等）
    * `B` : bool
    * `M` : matrix
    * `C` : color
    * `D` : data / compound
  * 通常クリックでその型のみ表示（再度クリックで全表示に戻る）、`Ctrl+クリック`で複数の型を個別にトグルします。
* **漏斗メニュー（表示オプション）**
  * `Show Non-Keyable` : キー設定不可の属性も表示します（既定オン）。
  * `Show Connected Only` : 接続済みの属性のみ表示します。
  * `Show Extra Attribute Only` : ユーザー定義（追加）属性のみ表示します。

## メニュー

### Options

接続・コピー・スクロールの動作を切り替えるトグルです。

![option](../../images/rig/connection_editor/option.png)

* **Force connect**
  * ロックされた属性のロックを一時的に解除し、既存の入力接続を置き換えて強制的に接続・上書きします（処理後に元のロック状態へ戻します）。
* **Force disconnect**
  * ロックされた入力属性のロックを一時的に解除して切断します。
* **Scroll to connected**
  * 属性を選択すると、反対側のツリーをその接続相手までスクロール・選択します。

### Edit

属性の並び・表示名を切り替えます（左右共通）。

![edit](../../images/rig/connection_editor/edit.png)

* **Sort Attributes**
  * `Scene Order`（シーン順）/ `Name (A→Z)` / `Name (Z→A)` から並び順を選びます。
* **Attribute Names**
  * `Long Name`（ロング名）/ `Short Name`（ショート名）を切り替えます。

## マルチアトリビュート（ゴースト要素）

マルチ（配列）属性では、実データには存在しない**空きインデックスの行を先回りして表示**します。歯抜けの空き番号と末尾の次の空き番号がゴースト要素として並び、通常の行と区別して描画されます。

![ghost](../../images/rig/connection_editor/ghost.png)

ゴースト要素に接続すると、その要素が実体化し、新しいゴースト要素が末尾に追加されます。Maya 標準では分かりにくい「次の空きインデックス」への接続を、番号を意識せずに行えます。

## ライブ追従

シーンの外部変更には自動で追従します。Connection Editor の外で接続・切断・属性追加・ロック変更・Undo / Redo を行うと、ツリーと接続線が即座に更新されます。
