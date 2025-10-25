---
title: Transform Creator
category: rig
description: 選択オブジェクトに整列したトランスフォームノードを作成
lang: ja
lang-ref: transform_creator
order: 20
---

## 起動方法

専用のメニューか、以下のコマンドでツールを起動します。

```python
import faketools.tools.rig.transform_creator_ui
faketools.tools.rig.transform_creator_ui.show_ui()
```

![image001](../../images/rig/transform_creator/image001.png)

### 基本的な使用方法

1. 上部のドロップダウンメニューから、トランスフォームの作成方法を選択します。
2. シーン上のトランスフォームノードかコンポーネントを選択します。
3. それ以外のオプションを設定します。グレーアウトされていないオプションを設定可能です。
4. **[ Create ]** ボタンを押すことでトランスフォームノードが作成されます。

※ 選択可能なコンポーネントは、Vertex, Edge, Face, CurveCV, CurveEP, SurfaceCV です。

### オプション

- **ノードタイプ**
  - locator か transform のどちらかを選択します。
- **Divisions**
  - 作成方法が innerDivide の時のみ有効です。選択したノード間を何分割するかを設定します。
- **IncludeRotation**
  - 作成するトランスフォームノードに回転属性を含めるかを設定します。
- **回転をオフセットする値**
  - 作成されたトランスフォームノードに対して、回転をオフセットする値を設定します。
- **Tangent from Component**
  - Vertex, Edge の場合、そのコンポーネントに接続されているコンポーネントから接線ベクトルを取得し回転を設定します。
- **Reverse**
  - トランスフォームノードが複製作成された場合、その順番を逆にするかを設定します。
- **Chain**
  - トランスフォームノードが複製作成された場合、それらをチェーン状の階層構造にするかを設定します。

### 作成方法

- **GravityCenter**
  - 選択したノードの重心にトランスフォームノードを作成します。
- **BoundingBoxCenter**
  - 選択したノードのバウンディングボックスの中心にトランスフォームノードを作成します。
- **EachPositions**
  - 選択したノードの各ポジションにトランスフォームノードを作成します。
- **InnerDivide**
  - 選択したノード間を分割し、その間にトランスフォームノードを作成します。