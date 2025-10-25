---
title: Transform Connector
category: rig
description: トランスフォーム属性の接続とコピーツール
lang: ja
lang-ref: transform_connector
order: 10
---

## 起動方法

専用のメニューか、以下のコマンドでツールを起動します。

```python
import faketools.tools.rig.transform_connector_ui
faketools.tools.rig.transform_connector_ui.show_ui()
```

![image001](../../images/rig/transform_connector/image001.png)

## 使用方法

1. ツールで操作したいノードを選択します。トランスフォームタイプのノードのみが有効です。
2. それぞれ操作したいアトリビュートのチェックボックスを選択します。
3. それぞれ、Copy Value ( 値のコピー )、Connect Value ( 接続 )、Zero Reset ( ゼロリセット ) のボタンを押して操作を行います。
