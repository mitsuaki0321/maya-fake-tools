---
title: Skin Tools
category: rig
description: スキンウェイト管理のための包括的なツール
lang: ja
lang-ref: skin_tools
order: 110
---

## 注意点

このツールでの skinCluster の操作は、いくつかの前提条件に基づいています。
- skinCluster の method が Classic Linear であることを想定しており他の method には対応していません。
- maya2024 以降で導入された複数の skinCluster のサポートには対応していません。

## 使用方法

専用のメニューか、以下のコマンドでツールを起動します。

```python
import faketools.tools.rig.skin_tools.ui
faketools.tools.rig.skin_tools.ui.show_ui()
```

![image001](../../images/rig/skin_tools/image001.png)

## Edit メニュー

![image002](../../images/rig/skin_tools/image002.png)

- **Select Influences**
  - ジオメトリ及び頂点（複数オブジェクト選択可）を選択し実行すると、それに設定されている skinCluster のインフルエンスを選択します。
  - 頂点を選択した場合は、その頂点でウエイトが 0 以上のインフルエンスのみを選択します。
- **Rebind SkinCluster**
  - ジオメトリ及び頂点（複数オブジェクト選択可）を選択し実行すると、それに設定されている skinCluster をそのインフルエンスの位置で再バインドします。
- **Prune Small Weights**
  - ジオメトリを選択し実行すると、ウエイトが 0.005 未満のインフルエンスのウエイトを 0 に設定します。Maya の標準機能と違い、ロックされているインフルエンスを無視します。
- **Remove Unused Influences**
  - ジオメトリ（複数選択可）を選択し実行すると、ウエイトがすべて 0 のインフルエンスをその skinCluster から除外します。
- **Average Skin Weights**
  - 頂点を選択し実行すると、選択された頂点のウエイトを平均化します。
- **Average Skin Weights Shell**
  - ジオメトリを選択し実行すると、選択されたジオメトリのウエイトをシェルごとに平均化します。

## Skin Tools Bar

ウエイトのコピーとミラーリングを行います。\
適用先がバインドされていない場合、自動的に skinCluster を作成します。

![skinWeights_bar001](../../images/rig/skinWeights_bar/image001.png)

### Copy

ウエイトのコピーとミラーリングを行います。

ウエイトコピーを行います。

1. コピー元のジオメトリを選択します。
2. コピー先のジオメトリ（複数選択可）を選択します。
3. `COPY` ボタンを押して、コピー元のウエイトをコピー先にコピーします。この時 UV を参照する際は、`UV` チェックボックスをオンにしてください。

このツールは、コピー元のジオメトリに設定されているインフルエンスを強制的にコピー先ジオメトリの skinCluster に追加します。

### Mirror Self

ウエイトのミラーリングを行います。

1. ジオメトリを選択します。
2. `MIR SELF` ボタンを押して、選択したジオメトリのウエイトをミラーリングします。この時、ミラーリングする方向を矢印ボタンで選択してください。`<-` の場合は、X から -X に、`->` の場合は -X から X にミラーリングします。
   
このツールは、選択したジオメトリに設定されている左右のインフルエンスを検索し、見つかったインフルエンスと反対側のインフルエンスが存在する場合、そのインフルエンスを強制的に skinCluster に追加します。

### Mirror Sub

ウエイトのミラーリングを別ジオメトリに対して行います。

使用例：例えば、靴を履いているキャラクターの左右の靴のウエイトをミラーリングする場合などに使用します。

1. 左側の靴のジオメトリを選択します。
2. `MIR SUB` ボタンを押します。この時の実行される手順は以下の通りです。
   1. 左側の靴のジオメトリ名から右側の靴のジオメトリ名を生成します。
   2. 右側の靴のジオメトリが見つかった場合、左側の靴のジオメトリに設定されているインフルエンス名を左から右の名前に変換します。
   3. 右側の靴のジオメトリに変換されたインフルエンス名が存在する場合、そのインフルエンスを強制的に skinCluster に追加するか、新たに skinCluster を作成して追加します。
   4. 左側の靴のジオメトリに設定されているウエイトを右側の靴のジオメトリにコピーします。

※ 反対側のジオメトリやインフルエンスを検索する方法は、Mirror Self と同様です。


## Copy Skin Weights Custom

メッシュから別のシェイプへウエイトをコピーします。

![skinWeights_copy001](../../images/rig/skinWeights_copy_custom/image001.png)

### 使用方法

ウエイトをコピーするには、以下の手順を行います。

1. コピー元となるジオメトリを選択します。
2. コピー先となるジオメトリ（複数選択可）を選択します。
3. ウエイトのコピー方法を選択し、`Copy Skin Weights` ボタンを押します。

### オプション

- **Blend**
  - 指定した値の割合でウエイトをコピーします。
- **Use Only Unlocked Influences**
  - ロックされていないインフルエンスのみを使用してコピーします。
- **Reference Original Shape**
  - オリジナルシェイプ ( Intermediate Object ) を参照してコピーします。
- **Add Missing Influence**
  - コピー先に存在しないインフルエンスをコピー時に自動的に追加します。


## Skin Weights to Mesh

skinCluster が適用されたジオメトリを、ウエイト情報を保持した状態で別のメッシュに複製します。\
複製元のジオメトリは、メッシュまたは NURBS サーフェースである必要があります。

![skinWeights_to_mesh001](../../images/rig/skinWeights_to_mesh/image001.png)

![skinWeights_to_mesh002](../../images/rig/skinWeights_to_mesh/image002.png)![skinWeights_to_mesh003](../../images/rig/skinWeights_to_mesh/image003.png)

### 使用方法

複製するには、以下の手順を行います。

1. skinCluster が設定されたジオメトリを選択（複数選択可）します。
2. 選択しているジオメトリがメッシュの場合は、`Mesh Division` を NURBS サーフェースの場合は、`U Division` と `V Division` を設定します。
3. `Convert Skin Weights to Mesh` ボタンを押します。

`Create Template Mesh` ボタンを押すことにより、複製後のメッシュのプレビューとなるジオメトリが作成されます。プレビュー状態では、各ディビジョンの値をUI上から変更することができます。


## Adjust Center Skin Weights

ウエイトが適用されている頂点のウエイトを調整します。

![skinWeights_adjust_center001](../../images/rig/skinWeights_adjust_center/image001.png)

主に中央位置にある頂点のウエイトを調整します。ここで「中央位置」とは、ジオメトリの左右対称軸上に位置する頂点を指します。

「調整」とは、中心位置に対して左右の意味合いを持つインフルエンスのウエイト値を同じ値にすることを指します。例えば、spine と shoulder の左右のインフルエンスの三つのインフルエンスが中心の頂点に対してそれぞれ 0.4, 0.2, 0.4 のウエイトを持っている場合、このツールを使用することで、それぞれ 0.4, 0.3, 0.3 に調整されます。

### 使用方法

#### Auto Search が有効な場合

`Auto Search` が有効な場合、選択されている頂点のスキンクラスターから、ペアとなるインフルエンスを自動的に検索します。  
自動的な検索は、`settings.json` に記述された `ADJUST_CENTER_WEIGHT` より正規表現にて検索されます。

#### Auto Search が無効な場合

![skinWeights_adjust_center002](../../images/rig/skinWeights_adjust_center/image002.png)

1. `Source Influences` に左右どちらかのインフルエンス（複数可）を選択し `SET` ボタンを押します。
2. `Target Influences` に `Source Influences` とペアになるインフルエンスを選択し `SET` ボタンを押します。
3. `Adjust Center Weights` ボタンを押します。

`Static Influence` にインフルエンスが登録されていない場合、ソースインフルエンスとターゲットインフルエンスのペアの平均値が設定されます。

一方、`Static Influence` にインフルエンスが登録されている場合は、ソースインフルエンスのウエイト値がターゲットインフルエンスに適用されます。この結果、すべてのインフルエンスのウエイト値の合計が 1.0 を超える場合は、その差分が Static Influence から差し引かれます。

## Combine Skin Weights

ウエイトを複数のインフルエンスから一つのインフルエンスに統合します。

![skinWeights_combine001](../../images/rig/skinWeights_combine/image001.png)

### 使用方法

ウエイトを統合するには、以下の手順を行います。

1. `Source Influences` に統合元となるインフルエンス（複数可）を選択し `SET` ボタンを押します。
2. `Target Influence` に統合先のインフルエンスを選択し `SET` ボタンを押します。
3. `Combine Skin Weights` ボタンを押します。

## Relax Skin Weights

ウエイトをスムース、リラックスさせます。

![skinWeights_relax001](../../images/rig/skinWeights_relax/image001.png)

### 使用方法

ウエイトをスムース、リラックスさせるには、以下の手順を行います。

1. コンポーネントを選択します。
2. 上部のメニューからスムースの種類を選択します。
3. オプションを設定します。
4. `Relax Skin Weights` ボタンを押します。

### オプション

- **Iterations**
  - スムースの反復回数を設定します。反復回数が多いほど、ウエイトがスムースされます。
- **After Blend**
  - スムース後に、元のウエイトとスムース後のウエイトをブレンドする割合を設定します。0.0 で元のウエイト、1.0 でスムース後のウエイトになります。
- **Use Only Unlocked Influences**
  - ロックされていないインフルエンスのみを使用してスムースします。すこし実験的な機能です。


## Influence Exchange

既にバインドされているインフルエンスをバインドされていないインフルエンスに交換します。

![skinWeights_influence_exchange001](../../images/rig/influence_exchange/image001.png)

### 使用方法

インフルエンスを交換するには、以下の手順を行います。

1. `Target SkinClusters` に交換対象のスキンクラスタを選択し、`SET` ボタンを押します。
2. `Binding Influences` に交換元のインフルエンスを選択し、`SET` ボタンを押します。ここに設定されるインフルエンスはすべて、`Target SkinClusters` に設定されたスキンクラスタにバインドされている必要があります。
3. `Exchange Influences` に交換先のインフルエンスを選択し、`SET` ボタンを押します。ここに設定されるインフルエンスはすべて、`Target SkinClusters` に設定されたスキンクラスタにバインドされていない必要があります。
4. `Exchange Influences` ボタンを押します。



