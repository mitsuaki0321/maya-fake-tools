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
    - `By Planes`: モデルをポリゴンカットプレーンで切断します。カットプレーンは `Plane` タブからも生成できます。

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


※ カッターはポリゴンプレーンとして作成されます。フェース単位で切断が発生するため、できるだけ低解像度のポリゴンを採用してください。フェースが 5 より多い場合はエラーになります。


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

プレーンのサイズを決める値です。Target Mesh の設定状態によって意味が変わります。

- **Target Mesh が ON** のとき: レイキャストによるサイズ自動計算の結果に対する倍率として機能します。
- **Target Mesh が OFF または未設定** のとき: プレーンの辺長（ワールド単位）としてそのまま使用されます。例えば `10.0` なら 10×10 のプレーンが作成されます。

#### Size Ratio Limit

Target Mesh が ON の場合のみ有効です。\
レイキャストによるサイズ自動計算では、ジョイント位置から各軸の正負方向にレイを飛ばしてメッシュとの交点距離を計測します。このとき、片方のレイがメッシュ内部を貫通して反対側まで抜けてしまうと、プレーンが異常に大きくなります。

Size Ratio Limit は、正負方向のレイ距離の比率（長い側 ÷ 短い側）がこの値を超えた場合、長い側を異常値とみなして無視し、短い側の距離を対称的に使用します。デフォルト値は `3.0` です。

- 値を小さくするほど厳しく判定（小さめのプレーンに収まりやすい）
- 値を大きくするほど緩く判定（従来挙動に近い）

### Mirror Plane

選択中のプレーンを指定軸でミラーコピーします。ミラー後の名前は左右パターン（共有設定の `mirror_patterns`）に基づいて自動生成されます。

- **Mirror Axis**: ミラーする軸（X / Y / Z）
- 対象のプレーンを選択して `Mirror` をクリック

## コマンド API リファレンス

UI を介さずスクリプトから直接各ステップを実行できます。以下はワークフロー順のコード例です。

### Plane — カッタープレーンの作成

```python
from faketools.tools.rig.proxy_builder import plane_command

# ジョイントの位置にプレーンを作成（Target Mesh で自動サイズ計算）
plane = plane_command.create_plane_at_joint(
    joint="LeftArm",
    target_mesh="body_geo",           # レイキャストでサイズ自動計算
    axis=(0, 1, 0),                   # 法線軸
    rotation_mode="aim",              # "joint", "aim", or "manual"
    aim_target="auto",                # "auto", "parent", or "chain"
    size_scale=1.2,                   # 自動サイズへの倍率
    size_ratio_threshold=3.0,         # レイ距離の異常値検出閾値
)

# Target Mesh なしで固定サイズのプレーンを作成
plane = plane_command.create_plane_at_joint(
    joint="Spine",
    rotation_mode="joint",
    size_scale=15.0,                  # 辺長15のプレーン (Target Mesh 無し時)
)

# 明示的パラメータで直接作成
plane = plane_command.create_plane(
    position=(0, 100, 0),
    rotation=(0, 45, 0),
    size=(20.0, 10.0),
)

# ミラーコピー
mirrored = plane_command.mirror_plane(source=plane, axis="x")
```

### Cut — メッシュの切断

```python
from faketools.tools.rig.proxy_builder import cut_command

# ウェイト境界でカット（単一メッシュ）
pieces = cut_command.separate_by_weights(
    mesh="body_geo",
    joints=["Hips", "Spine", "LeftArm", "RightArm"],  # None で全インフルエンス
    duplicate=True,             # 元メッシュを保持
    merge_end_joints=False,     # 末端ジョイントのウェイトを親にマージ
)

# ウェイト境界でカット（複数メッシュ一括）
pieces = cut_command.separate_meshes_by_weights(
    meshes=["body_geo", "cloth_geo"],
    joints=None,
    duplicate=True,
    group="piece_grp",          # 結果の親グループ名
)

# カッタープレーンでカット（単一メッシュ）
pieces = cut_command.separate_by_planes(
    mesh="body_geo",
    cutters=["LeftArm_cut_plane", "RightArm_cut_plane"],
    duplicate=True,
)

# カッタープレーンでカット（複数メッシュ一括）
pieces = cut_command.separate_meshes_by_planes(
    meshes=["body_geo", "cloth_geo"],
    cutters=["LeftArm_cut_plane", "Spine_cut_plane"],
    duplicate=True,
    group="piece_grp",
)
```

### Assign — ピースの骨への割り当て

```python
from faketools.tools.rig.proxy_builder import assign_command

# ウェイトベースで自動アサイン
assignment = assign_command.auto_assign_pieces(
    pieces=pieces,                      # Cut ステップの結果
    reference_mesh="body_geo",          # スキンウェイト参照メッシュ
    joints=None,                        # None で全インフルエンス
)
# assignment = {"Hips": ["piece1", "piece2"], "Spine": ["piece3"], ...}

# ボーン距離ベースで自動アサイン (reference_mesh=None)
assignment = assign_command.auto_assign_pieces(
    pieces=pieces,
    reference_mesh=None,
    joints=["Hips", "Spine", "LeftArm", "RightArm"],  # 必須
)

# parentConstraint 付きプロキシグループを作成
groups = assign_command.create_proxy_groups(
    assignment=assignment,
    parent_group="proxy_grp",
)

# 個別ピースを別ジョイントに手動で再アサイン
assign_command.reassign_piece(
    piece="piece3",
    target_joint="Chest",
    parent_group="proxy_grp",
)

# シーン階層から現在のアサイン状態を読み取り
current = assign_command.get_proxy_group_assignment(parent_group="proxy_grp")
```

### Finalize — 最終メッシュの生成

```python
from faketools.tools.rig.proxy_builder import finalize_command

# 骨ごとに1メッシュにコンバイン
results = finalize_command.finalize_proxy_groups(
    parent_group="proxy_grp",
    combine_mode="single",              # "single" or "per_shader"
    output_group="proxy_final_grp",
)

# シェーダー別にコンバイン + シェイプペアレント
results = finalize_command.finalize_proxy_groups(
    parent_group="proxy_grp",
    combine_mode="per_shader",
    output_group="proxy_final_grp",
)
```

## 設計原則

- **フレームワーク非依存**: Maya 標準操作のみ使用。特定のリグフレームワークの API や命名規則に依存しません
- **各ステップ間で確認可能**: 各ステップの結果を確認・調整してから次のステップに進めます
- **各ステップ間は疎結合**: ステップ間の依存関係を最小限にし、任意のステップから開始できます
- **ツール API に依存しない紐付け**: 骨とジオメトリの関係はシーン構造（命名 + parentConstraint）から読み取れます
