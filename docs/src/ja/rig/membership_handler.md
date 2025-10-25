---
title: Membership Handler
category: rig
description: デフォーマーのコンポーネントタグメンバーシップ管理ツール
lang: ja
lang-ref: membership_handler
order: 100
---

# 概要

デフォーマーのメンバーシップを編集します。コンポーネントタグ設定が有効な場合のみ利用可能です。

WeightGeometryFilter タイプのデフォーマーのみが対象です。

## 起動方法

専用のメニューか、以下のコマンドでツールを起動します。

```python
import faketools.tools.rig.membership_handler_ui
faketools.tools.rig.membership_handler_ui.show_ui()
```

![image001](../../images/rig/membership_handler/image001.png)

### 起動する条件

このツールは、コンポーネントタグが有効な場合のみ利用可能です。

以下の設定でコンポーネントタグを有効にします。

1. `Preferences` > `Settings` > `Animation` に移動する。
2. `Rigging` セクションの 以下三つの設定をそれぞれ設定する。
    - `Use component tags for deformation component subsets` にチェックを入れる。
    - `Create component tags on deformer creation` にチェックを入れる。
    - `Add tweak nodes on deformer creation` のチェックを外す。

## 使用方法

1. 編集対象のデフォーマーを選択し、![image002](../../images/rig/membership_handler/image002.png) ボタンを押します。  
![image006](../../images/rig/membership_handler/image006.png)  
※ 画像では、cluster デフォーマーのハンドルを選択していますが、実際はデフォーマー自体を選択してボタンを押してください。

1. 真ん中のフィールドに選択したデフォーマーの名前が表示されます。  
![image005](../../images/rig/membership_handler/image005.png)

1. ![image004](../../images/rig/membership_handler/image004.png) ボタンを押して、そのデフォーマーに登録されれているメンバーシップを選択します。  
![image007](../../images/rig/membership_handler/image007.png)

1. 更新したいコンポーネントを選択肢、![image001](../../images/rig/membership_handler/image003.png) ボタンを押すことで、メンバーシップが更新されます。  
![image008](../../images/rig/membership_handler/image008.png)



