---
title: Node Lister
category: rig
description: ノードをリスト・フィルタリングし、アトリビュートの管理を行うツール
lang: ja
lang-ref: node_lister
order: 90
---

## 概要

シーン上のノードを柔軟にリスト・フィルタリングし、アトリビュートの状態を変更するツールです。  
3段階のフィルタ（selectFilter → nodeFilter → matchFilter）により、目的のノードを素早く絞り込むことができます。

## 起動方法

専用のメニューか、以下のコマンドでツールを起動します。

```python
import faketools.tools.rig.node_lister.ui
faketools.tools.rig.node_lister.ui.show_ui()
```

![image](../../images/rig/node_lister/image001.png)

## UI構成

ウィンドウは上から順に以下の要素で構成されています。

- **selectFilter** (コンボボックス) + **Load** ボタン
- **nodeFilter** (ノードタイプフィルタ) + **inherited** トグル
- **matchFilter** (名前正規表現フィルタ) + **ignorecase** トグル
- **ノードリスト**
- **アトリビュートリスト**
- **アトリビュートフィルタ**
- **値フィールド**
- **Delete Attributes** ボタン

## 使用方法

### ノードのロードとフィルタリング

1. コンボボックスからノードの取得方法を選択します。
2. `Load` ボタンを押してノードをロードします。
3. 必要に応じて、nodeFilter や matchFilter でノードを絞り込みます。

### selectFilter の種類

![image](../../images/rig/node_lister/image002.png)

| フィルタ | 説明 |
|---------|------|
| All Nodes | シーン上のすべてのノード |
| Selected Nodes | 現在選択しているノード |
| Shapes of Selected | 選択ノードのシェイプノード |
| Hierarchy of Selected | 選択ノードとその全子孫 |
| History of Selected | 選択ノードのコンストラクションヒストリ |
| Future of Selected | 選択ノードのフューチャーヒストリ |
| Connections of Selected | 選択ノードに接続されているノード |
| DAG Nodes | シーン上のすべてのDAGノード |

### nodeFilter（ノードタイプフィルタ）

![image](../../images/rig/node_lister/image003.png)

テキストフィールドにノードタイプ（例: `transform`、`joint`、`mesh`）を入力すると、そのタイプのノードのみが表示されます。

右側の **i** トグルボタンを有効にすると、継承タイプも含めたマッチングになります。  
例えば `transform` を指定して inherited を有効にすると、`joint` なども表示されます。

### matchFilter（名前正規表現フィルタ）

![image](../../images/rig/node_lister/image004.png)

テキストフィールドに正規表現パターンを入力すると、名前がマッチするノードのみが表示されます。

右側の **i** トグルボタンを有効にすると、大文字小文字を区別しないマッチングになります。

### ノードリストの選択

![image](../../images/rig/node_lister/image005.png)

ノードリストでノードを選択すると、Mayaシーン上でもそのノードが選択されます。  
また、選択したノードの共通アトリビュートがアトリビュートリストに表示されます。

ノードの選択を切り替えた際、前回選択していたアトリビュートが存在する場合は同じアトリビュートが再選択されます。

![image](../../images/rig/node_lister/image006.png)

## アトリビュートの値を変更する

1. ノードリストからノードを選択します（複数選択可能）。
2. アトリビュートリストからアトリビュートを選択します（複数選択可能）。
3. 値フィールドに値を入力し、`Enter` キーを押すと値が変更されます。

### 値を変更できる状態について

値を変更できる場合は、フィールドが以下のように表示されます。

![image](../../images/rig/node_lister/image007.png)

値を変更できない場合は、フィールドの色たそれぞれ以下のように表示されます。

ロックされている場合  
![image](../../images/rig/node_lister/image008.png)  

接続がある場合  
![image](../../images/rig/node_lister/image009.png)  

選択されているアトリビュート間で、ノードの型が異なる場合  
![image](../../images/rig/node_lister/image010.png)  


## アトリビュートの状態を変更する

アトリビュートリスト上で右クリックすると、コンテキストメニューが表示されます。

![image](../../images/rig/node_lister/image012.png)

- **Lock** — 選択したアトリビュートをロックします。
- **Unlock** — 選択したアトリビュートのロックを解除します。
- **Keyable** — 選択したアトリビュートをチャンネルボックスに表示します。
- **Unkeyable** — 選択したアトリビュートをチャンネルボックスから非表示にします。

## アトリビュートの削除

`Delete Attributes` ボタンを押すと、選択しているノードの選択しているアトリビュートを削除します。

## ノードリストの操作

ノードリスト上で右クリックすると、コンテキストメニューが表示されます。

![image](../../images/rig/node_lister/image011.png)

- **Select All** — リスト内のすべてのノードを選択し、Mayaシーン上でも選択します。
