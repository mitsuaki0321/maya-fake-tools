---
title: Mesh Mirror
category: model
description: メッシュの頂点位置をミラー・フリップ
lang: ja
lang-ref: mesh_mirror
order: 65
---

## 概要

メッシュの頂点位置を X 軸（YZ 平面）を基準にミラーまたはフリップするツールです。

主な機能:

- **Mirror**: ソース側の頂点位置を反転コピーしてデスティネーション側に上書き
- **Flip**: 対称テーブルを使って左右ペアの頂点位置を交換（非対称な形状が左右入れ替わる）
- **単一メッシュモード**: 1 つのメッシュ内の左右対称を操作
- **2 メッシュモード**: 左右に分離したメッシュペア間で操作
- **複数ターゲット一括処理**: 同一テーブルで複数ターゲットを一度にミラー / フリップ
- **非対称メッシュ対応**: 対称テーブルでマッチしない頂点に対する 2 種類のフォールバック


## 起動方法

専用のメニューか、以下のコマンドでツールを起動します。

```python
import faketools.tools.model.mesh_mirror.ui
faketools.tools.model.mesh_mirror.ui.show_ui()
```

![image](../../images/model/mesh_mirror/image001.png)


## 使用方法

### 基本的な手順（Single Mesh モード）

![image](../../images/model/mesh_mirror/image002.png)

1. Maya のビューポートで対称なベースメッシュを選択し、`Base` の `Set` ボタンを押して登録します。

    ![image](../../images/model/mesh_mirror/image003.png)

2. ミラー / フリップしたいターゲットメッシュを選択し、`Target` の `Set` ボタンを押して登録します。複数のターゲットを同時に選択できます。

    ![image](../../images/model/mesh_mirror/image004.png)

3. Symmetry Check セクションで `Method` と `Threshold` を設定し、`Build Table & Check` ボタンを押して対称テーブルを構築します。

4. チェック結果を確認します。Failed や Asymmetric の頂点がある場合、`Select Failed Vertices` ボタンでベースメッシュ上の該当頂点を確認できます。

    ![image](../../images/model/mesh_mirror/image005.png)

5. Apply セクションで Direction と Fallback を設定し、`Mirror` または `Flip` ボタンを押して実行します。`Create Copy` のチェックボックスがオンの場合は、ターゲットメッシュを複製し結果を適用します。

    ![image](../../images/model/mesh_mirror/image006.png)

**Flip の結果**

![image](../../images/model/mesh_mirror/image007.png)

### 基本的な手順（Dual Mesh モード）

![image](../../images/model/mesh_mirror/image008.png)

1. Mode を `Dual Mesh` に切り替えます。

2. 対称なベースメッシュペアを `Base A` / `Base B` にそれぞれ登録します。

    ![image](../../images/model/mesh_mirror/image009.png)

3. ターゲットメッシュペアを `Target A` / `Target B` にそれぞれ登録します。`Target A` と `Target B` の数は同じにする必要があります。

    ![image](../../images/model/mesh_mirror/image010.png)

4. Symmetry Check セクションで `Method` を選択し、`Build Table & Check` ボタンを押してベースペアから対応テーブルを構築します。

5. Apply セクションで Direction と Fallback を設定し、`Mirror` または `Flip` ボタンを押して実行します。

**Flip の結果**

![image](../../images/model/mesh_mirror/image011.png)


## Mesh Input セクション

ベースメッシュとターゲットメッシュを登録するセクションです。

- **Base**: 対称テーブルの構築元となる対称なメッシュ。ビューポートでメッシュを選択し `Set` ボタンで登録します。
- **Target**: 操作対象のメッシュ。複数のメッシュを選択した状態で `Set` ボタンを押すと一括登録できます。1 つの場合はメッシュ名、複数の場合は「N meshes」と表示されます。

`Dual Mesh` モードでは `Base A` / `Base B`、`Target A` / `Target B` の 4 フィールドが表示されます。

※ ベースメッシュとターゲットメッシュは同一トポロジーである必要があります。トポロジーが異なる場合、Mirror / Flip 実行時にエラーが表示されます。


## Symmetry Check セクション

ベースメッシュから対称テーブルを構築し、テーブルの品質を確認するセクションです。

- **Method**: テーブル構築の方式を選択します（下記参照）。
- **Threshold**: 頂点マッチングの距離閾値を設定します。

`Build Table & Check` ボタンでテーブルを構築すると、以下の情報が表示されます:

| 項目 | 説明 |
|------|------|
| Matched | マッチしたペア数 |
| Center | 中心軸上の頂点数（`Single Mesh` のみ） |
| Failed | マッチしなかった頂点数 |
| Asymmetric | 位置が非対称なペア数 |

`Select Failed Vertices` ボタンで Failed および Asymmetric の頂点をベースメッシュ上で選択できます。問題箇所の確認に使用してください。

### マッチング方式

**Single Mesh モード:**

| 方式 | 説明 |
|------|------|
| `position` | KDTree による位置ベースマッチング。高速。きれいな対称メッシュ向き |
| `topology` | BFS によるフェース接続ベースのマッチング。多少ずれた対称メッシュにも対応 |

**Dual Mesh モード:**

| 方式 | 説明 |
|------|------|
| `position` | KDTree によるミラー位置マッチング。頂点順序が異なる L/R 向き |
| `topology` | BFS によるフェース接続マッチング。変形が大きいが構造は同一の L/R 向き |
| `index` | 頂点インデックスで直接対応（vtx[i] <-> vtx[i]）。同一メッシュから分割した L/R 向き |


## Apply セクション

ミラーまたはフリップを実行するセクションです。

- **Direction**: ミラー方向を選択します。
  - `Single Mesh`: `+X → -X`（+X 側を -X 側にコピー）/ `-X → +X`（逆方向）
  - `Dual Mesh`: `A → B`（A の形状をミラーして B に適用）/ `B → A`（逆方向）
- **Fallback**: Failed 頂点の処理方式を選択します（下記参照）。
- **Create Copy**: オンの場合、ターゲットメッシュを複製してから結果を適用します。元のターゲットは変更されません。

### Mirror と Flip の違い

`Mirror` はソース側の頂点位置をデスティネーション側に一方向でコピーします。ソース側は変更されません。

```
pair(neg=3, pos=58) で +X → -X の場合:
  vtx[3] = mirror_x(vtx[58])   -- -X側がソースで上書きされる
  vtx[58] は変更なし             -- +X側はそのまま
center 頂点: X = 0 にスナップ
```

`Flip` は左右ペアの頂点位置を交換します。両側が変更されます。非対称な形状が左右入れ替わります。

```
pair(neg=3, pos=58):
  new_vtx[3]  = mirror_x(old_vtx[58])  -- 互いの位置をX反転して交換
  new_vtx[58] = mirror_x(old_vtx[3])
center 頂点: X値に -1 を乗算
```

### フォールバック方式

対称テーブルでマッチしなかった頂点（Failed）に対する処理方式です。左右で頂点数が異なるメッシュなどで使用されます。

| 方式 | 説明 |
|------|------|
| `closest_point` | 頂点のミラー位置から元メッシュサーフェスの最近接点を取得して適用。精度が高いが、メッシュが折り返している領域で別のフェースを参照するリスクあり |
| `laplacian` | 近傍頂点の位置を反復平均して収束。トポロジー的に安全だが、曲率の再現は若干劣る |


## コマンドによる実行

UI を使用せずにスクリプトから直接実行できます。

### 基本的な実行

```python
from faketools.tools.model.mesh_mirror import command

# 1. 対称テーブルを構築
table = command.build_single_table("base_mesh", method="position", threshold=0.001)

# 2. ミラー実行
op = command.SingleMeshOperation(target="target_mesh", base="base_mesh", table=table)
op.mirror(direction="+x", fallback="closest_point")
```

### チェックの実行

```python
# ベースメッシュの対称性をチェック
result = command.get_check_result_single("base_mesh", table, threshold=0.001)
print(f"Matched: {result.matched_count}, Failed: {result.failed_count}, Asymmetric: {result.asymmetric_count}")

# Failed + Asymmetric 頂点を選択
command.select_failed_vertices("base_mesh", result.failed_indices + result.asymmetric_indices)
```

### 2 メッシュモードでの実行

```python
# 対応テーブルを構築
table = command.build_dual_table("base_L", "base_R", method="position", threshold=0.001)

# ミラー
op = command.DualMeshOperation(
    target_a="target_L", target_b="target_R",
    base_a="base_L", base_b="base_R",
    table=table,
)
op.mirror(direction="a_to_b", fallback="closest_point")

# フリップ
op.flip(fallback="laplacian")
```


## 注意事項

- すべての計算はオブジェクト空間で行われます。トランスフォームの位置・回転・スケールには影響されません。
- 対称軸は X 軸（YZ 平面）固定です。
- ベースメッシュとターゲットメッシュは同一トポロジーである必要があります。トポロジーが異なる場合、実行時にエラーが表示されます。
- 操作は Undo 可能です。複数ターゲットの一括処理も 1 回の Undo で元に戻せます。
- 頂点位置のみを変更します。法線、UV、その他のメッシュ属性には影響しません。
