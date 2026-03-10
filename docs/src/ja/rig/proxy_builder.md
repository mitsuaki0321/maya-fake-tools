---
title: Proxy Builder
category: rig
description: レイアウトリグ用プロキシジオメトリの構築ツール
lang: ja
lang-ref: proxy_builder
order: 145
---

## 概要

Proxy Builder は、キャラクターモデルを骨単位のピースに分割し、各骨に追従するプロキシジオメトリを組み立てるツールです。　　
レイアウトリグやゲームエンジン向けの簡易ジオメトリ作成に使用します。

## 起動方法

専用のメニューか、以下のコマンドでツールを起動します。

```python
import faketools.tools.rig.proxy_builder.ui
faketools.tools.rig.proxy_builder.ui.show_ui()
```

![image](../../images/rig/proxy_builder/image001.png)


## ワークフロー

想定の基本的ワークフローです。

1. **モデルのカッティング** — メッシュをウェイト境界またはカッタープレーンで骨単位に切断
2. **モデルの各骨への割り当て** — 各ピースを骨に割り当て、parentConstraint 付きグループを生成
3. **モデルのファイナライズ** — 骨別グループ内のジオメトリをコンバインして最終形にする

### 1. モデルのカッティング

![image](../../images/rig/proxy_builder/image002-1.png)

メッシュをウェイト境界またはカッタープレーンで骨単位に切断します。

![image](../../images/rig/proxy_builder/image002-0.png)

1. ツールの `Cut` タブをアクティブにします。

2. `Source Meshes` にカットしたいモデルを登録します。

3. `Cut Method` で ウエイト境界でカットするか ( `By Weights` )、カットプレーンでカットするか ( `By Planes` ) を選択します。
    - `By Weights`: `Source Meshes` に登録しているメッシュに スキンウエイトが設定されている場合のみそのウエイトの境界でメッシュをカットします。
    - `By Planes`: モデルをカットプレーン ( メッシュか NURBSサーフェース ) で切断します。カットプレーンは `Plane` タブからも生成できます。

4. `Cut` ボタンをクリックしてモデルをカットします。 **piece_grp** の下にカットされたモデルが生成されます。\
    ※ 複製したモデルで処理を行いたい場合は、`Keep Original Mesh` のチェックボックスをオンにして `Cut` を実行してください。

    ![image](../../images/rig/proxy_builder/image002-2.png)



### 2. モデルの各骨への割り当て

![image](../../images/rig/proxy_builder/image003-1.png)

各ピースを骨に割り当て、parentConstraint 付きグループを生成します。\
目的は、問題なく各モデルがそのスケルトンに対応するようにカットされているかの確認です。

![image](../../images/rig/proxy_builder/image002-0.png)

1. ツールの `Assign` タブをアクティブにします。

2. 上部のリストにカットしたモデルをリストします。 モデルは `Piece Group` にセットされたグループから一括で `Load` することも可能です。

3. 次に、各スケルトンに対してカットしたモデルを振り分ける設定を行います。 `Assign Method` から方法を選択します。
    - `By Weights`: `Reference Mesh` に設定したジオメトリのスキンウエイトの範囲からモデルを振り分けます。
    - `By Bones`: 各ジオメトリと 骨（ボーンセグメント）との距離からモデルを振り分けます。

4. 振り分ける骨を `Joints` リストに登録します。`By Bones` の場合は必須です。`By Weights` の場合、リストが設定されていないと skinCluster ノードから自動的に骨を決定します。

5. `Assign & Create Groups` ボタンをクリックします。それぞれのモデルが各骨ごとにグループ化されます。

    ![image](../../images/rig/proxy_builder/image003-2.png)


### 3. モデルのファイナライズ

骨別グループ内のジオメトリをコンバインして最終形にします。

![image](../../images/rig/proxy_builder/image004-0.png)

1. ツールの `Finalize` タブをアクティブにします。

2. `Assign` タブで生成されたグループ ( proxy_grp ) を `Source Group` に設定して、`Load` します。

3. `Combine Mode` からその骨に該当するモデルのコンバイン方法を選択します。
    - `Single Mesh per Joint`: モデルをそのままコンバインして一つのメッシュにします。
    - `Per Shader (shape parent)`: 同じシェーダーがアサインされているモデルのみをコンバインし、ひとつのトランスフォームの下にそれぞれ別のシェーダーのシェイプをペアレントします。
    - ※ `Per Shader (shape parent)` では、同一シェル内で複数のシェーダーがアサインされている場合はエラーとなります。

4. `Finalize` ボタンをクリックするとそれぞれコンバインされたモデルが生成されます。

    ![image](../../images/rig/proxy_builder/image004-2.png)

## Plane タブについて

`Cut` タブの `By Planes` で使用するカッタープレーンを作成・ミラーするための補助ツールです。

![image](../../images/rig/proxy_builder/image005.png)


### Create Plane at Joint

ジョイントの位置にカッタープレーンを作成します。\
プレーン名はジョイント名から自動生成されます（例: `LeftArm_cut_plane`）。

各オプションを設定し、カットプレーンを作成したいジョイントを選択 ( 複数可 ) して、`Create Plane` を実行します。

![image](../../images/rig/proxy_builder/image006.png)


#### 基本設定

- **Target Mesh**: サイズ自動計算の参照メッシュを選択して `Set`（任意）します。 設定した後は、 `ON/OFF` で参照するかどうかを決定します。


#### Plane Type

| タイプ | 説明 |
|--------|------|
| **NURBS** | NURBS プレーンを作成 |
| **Poly** | ポリゴンプレーンを作成 |

※ ポリゴンの場合、一つのフェース単位で切断が発生するためできるだけ低解像度のポリゴンを採用してください。フェースが 5 より多いポリゴンはエラーとしています。


#### Axis

プレーンの法線方向の基準軸を選択します（X / Y / Z）。

#### Rotation Mode

プレーンの回転（法線方向）をどのように決定するかを選択します。

| モード | 動作 |
|--------|------|
| **Joint** | ジョイントのワールド回転をそのまま使用 |
| **Aim** | Aim Target の設定に基づいて法線方向を自動計算 |
| **Manual** | 手動で回転値を入力 |

#### Aim Target（Rotation Mode が Aim の場合）

| オプション | 動作 |
|-----------|------|
| **Auto** | 子ジョイントが 1 つなら子方向、なければ親から離れる方向 |
| **Parent** | 親ジョイントから離れる方向（ボーン進行方向） |
| **Parent > Child** | 親ジョイントから子ジョイントへの方向 |

- **Aim Joint**: 明示的に aim 先のジョイントを指定（任意）。設定すると Aim Target の選択は無視されます。

※ 子ジョイントを検索する際に `io` 属性が `True` のものは除外されます。

#### Size Scale

Target Mesh を設定した場合、レイキャストによるサイズ自動計算が行われます。Size Scale はその結果に対する倍率です。

### Mirror Plane

選択中のプレーンを指定軸でミラーコピーします。ミラー後の名前は左右パターン（共有設定の `mirror_patterns`）に基づいて自動生成されます。

- **Mirror Axis**: ミラーする軸（X / Y / Z）
- 対象のプレーンを選択して `Mirror` をクリック

## 設計原則

- **フレームワーク非依存**: Maya 標準操作のみ使用。特定のリグフレームワークの API や命名規則に依存しません
- **各ステップ間で確認可能**: 各ステップの結果を確認・調整してから次のステップに進めます
- **各ステップ間は疎結合**: ステップ間の依存関係を最小限にし、任意のステップから開始できます
- **ツール API に依存しない紐付け**: 骨とジオメトリの関係はシーン構造（命名 + parentConstraint）から読み取れます
