---
title: Offset Curve to Surface
category: rig
description: カーブをオフセットしてNURBSサーフェスを作成するツール
lang: ja
lang-ref: offset_curve_to_surface
order: 50
---

## 概要

選択した NURBS カーブの CV 位置を指定した方向にオフセットし、ロフトされた NURBS サーフェスを作成します。

オフセット方向として、任意のベクトル、カーブの法線・従法線、参照メッシュ・サーフェスの法線・従法線を選択できます。

## 起動方法

専用のメニューか、以下のコマンドでツールを起動します。

```python
import faketools.tools.rig.offset_curve_to_surface.ui
faketools.tools.rig.offset_curve_to_surface.ui.show_ui()
```

![image001](../../images/rig/offset_curve_to_surface/image001.png)

## 使用方法

1. NURBS カーブを選択します（複数選択可能）。
2. オフセット方向を `Axis` から選択します。
3. 必要に応じてオプションを設定します。
4. `Create` ボタンを押すことでサーフェスが作成されます。

![image002](../../images/rig/offset_curve_to_surface/image002.png)

## オプション

### Axis（オフセット方向）

![image003](../../images/rig/offset_curve_to_surface/image003.png)

サーフェスを作成する方向を指定します。

* **Vector**
  * 任意のベクトル方向にオフセットします。
  * `Vector` フィールドで X, Y, Z の方向を指定します。

* **Normal**
  * カーブの法線方向にオフセットします。
  * カーブの各 CV 位置における法線方向を使用します。

* **Binormal**
  * カーブの従法線方向にオフセットします。
  * カーブの各 CV 位置における従法線方向（法線と接線の外積）を使用します。

* **Mesh Normal**
  * 参照メッシュの法線方向にオフセットします。
  * `Reference` フィールドで参照するメッシュを指定する必要があります。
  * カーブの各 CV 位置から参照メッシュ上の最も近い点を探し、その位置の法線方向を使用します。

* **Mesh Binormal**
  * 参照メッシュの従法線方向にオフセットします。
  * `Reference` フィールドで参照するメッシュを指定する必要があります。
  * メッシュの法線方向とカーブの接線方向の外積を使用します。

* **Surface Normal**
  * 参照サーフェスの法線方向にオフセットします。
  * `Reference` フィールドで参照する NURBS サーフェスを指定する必要があります。
  * カーブの各 CV 位置から参照サーフェス上の最も近い点を探し、その位置の法線方向を使用します。

* **Surface Binormal**
  * 参照サーフェスの従法線方向にオフセットします。
  * `Reference` フィールドで参照する NURBS サーフェスを指定する必要があります。
  * サーフェスの法線方向とカーブの接線方向の外積を使用します。

### Vector（ベクトル方向）

![image004](../../images/rig/offset_curve_to_surface/image004.png)

`Axis` が `Vector` の場合のみ有効です。

* X, Y, Z の 3 つのスピンボックスでオフセット方向のベクトルを指定します。
* ベクトルは自動的に正規化されます。
* デフォルト値は (0.0, 1.0, 0.0) です。

### Reference（参照オブジェクト）

![image005](../../images/rig/offset_curve_to_surface/image005.png)

`Axis` が `Mesh Normal`, `Mesh Binormal`, `Surface Normal`, `Surface Binormal` の場合のみ有効です。

* 参照するメッシュまたは NURBS サーフェスを指定します。
* 参照オブジェクトを選択し、`<<` ボタンを押すことで設定できます。
* `Mesh Normal` / `Mesh Binormal` の場合は、メッシュを指定してください。
* `Surface Normal` / `Surface Binormal` の場合は、NURBS サーフェスを指定してください。

### Width（サーフェスの幅）

![image006](../../images/rig/offset_curve_to_surface/image006.png)

* **Width**
  * サーフェスの幅を指定します。
  * デフォルト値は 1.0 です。
  * 範囲：0.001 ～ 10000.0

* **Center**
  * サーフェースの作成方向に対して、この値を中心にサーフェースを作成します。
  * 0.5 でサーフェースはプラスマイナス同じ幅になります。
  * 例えば、Width が 10.0 で Center が 0.5 の場合、サーフェースは -5.0 から 5.0 までの幅になります。
  * デフォルト値は 0.5 です。
  * 範囲：0.0 ～ 1.0

画像８：Width と Center の値による結果の違い

## 注意事項

* カーブの次数は選択したカーブから自動的に取得されます。
* トランスフォームノードまたはシェイプノードを選択しても動作します。
* 複数のカーブを選択した場合、それぞれのカーブに対してサーフェスが作成されます。
* 作成されたサーフェスは自動的に選択されます。
* `Vector` が (0, 0, 0) の場合はエラーになります。
* 参照オブジェクトが必要な Axis を選択した場合、必ず適切なタイプのオブジェクトを `Reference` に設定してください。
