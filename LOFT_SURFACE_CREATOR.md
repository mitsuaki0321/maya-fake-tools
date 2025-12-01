# Loft Surface Creator

## ツールの概要

スカートやベルトなど 複数のジョイントチェーンにより構成されている部分のウエイト転送元を作成するツール。

Curve/Surface Creator に似ているツールだがこちらのほうが少し複雑になる。

---

## 実装進捗

### Phase 1: 基本機能 ✅ 完了

- [x] ジョイントチェーンからカーブ作成（degree=3固定）
- [x] カーブからNURBSサーフェスをロフト
- [x] カーブからメッシュをロフト（format=3, polygonType=1）
- [x] 基本的なスキンバインディング

### Phase 2: ウェイト計算 ✅ 完了

- [x] ジョイント方向（カーブ方向）のウェイト計算
- [x] チェーン方向（ロフト方向）のウェイト計算
- [x] メッシュの頂点インデックスからUV位置への変換
- [x] NURBSのCV座標系（U=カーブ方向、V=ロフト方向）対応
- [x] degree=3の中間CV用ウェイト調整（0.667/0.333）

### Phase 3: close=True対応 ✅ 完了

- [x] 3本以上のチェーン必須バリデーション（MIN_CHAINS_FOR_CLOSE=3）
- [x] メッシュ: 重複頂点行の処理（vtx[0]とvtx[12]が同位置）
- [x] NURBS: CVインデックスオフセット（v=0→最後のチェーン、v=1→最初のチェーン）

### Phase 4: 追加ウェイト処理 ✅ 完了

- [x] `weight_method="ease"` - イーズイン/アウト補間
- [x] `weight_method="step"` - ステップ補間（最も近いジョイント100%）
- [x] `smooth_iterations` - ウェイトスムージング（カーブ方向のみ）
- [x] `parent_influence_ratio` - 親ジョイントへの影響比率
- [x] `remove_end` - 末端ジョイントのウェイトを親にマージ
- [x] `loft_weight_method` - ロフト方向のウェイト分配方法（index/distance/projection）
- [x] `to_skin_cage` - スキンケージへの変換

### Phase 5: UI ✅ 完了

- [x] ui.py の作成
- [x] ジョイント選択UI（リスト + Add/Remove/Clear）
- [x] パラメータ設定UI
- [x] プリセット保存/読み込み（PresetMenuManager）

---

## ファイル構成

```
scripts/faketools/tools/rig/loft_surface_creator/
├── __init__.py              # TOOL_CONFIG定義
├── ui.py                    # UI（MainWindow, show_ui）
└── command/
    ├── __init__.py          # main() エントリーポイント
    ├── constants.py         # 定数定義
    ├── helpers.py           # ジョイントチェーン取得ヘルパー
    ├── create_loft.py       # CreateLoftSurface クラス
    └── weight_setting.py    # LoftWeightSetting クラス
```

---

## API

### main() 関数

ジョイントチェーンを直接受け取るメインエントリーポイント。

```python
from faketools.tools.rig.loft_surface_creator import command

result, skin = command.main(
    joint_chains: list[list[str]],    # ジョイントチェーンのリスト（2本以上必須、各3ジョイント以上）
    close: bool = False,              # 環状にするか（True時は3本以上必須）
    output_type: str = "nurbsSurface", # 出力タイプ: "nurbsSurface" | "mesh"
    surface_divisions: int = 0,       # カーブ間の追加分割数（0=追加分割なし）
    center: bool = False,             # カーブのCV位置を中央に調整
    curve_divisions: int = 0,         # ジョイント間に挿入するCV数
    is_bind: bool = False,            # スキンクラスターを作成するか
    weight_method: str = "linear",    # ウェイト計算方法: "linear" | "ease" | "step"
    smooth_iterations: int = 0,       # スムージング回数
    parent_influence_ratio: float = 0.0,  # 親ジョイントの影響比率
    remove_end: bool = False,         # 末端ジョイントのウェイトを親にマージ
    loft_weight_method: str = "index", # ロフト方向のウェイト分配方法: "index" | "distance" | "projection"
    to_skin_cage: bool = False,       # スキンケージに変換（nurbsSurface + is_bind=True時のみ）
    skin_cage_division_levels: int = 1, # スキンケージの分割レベル
) -> tuple[str, Optional[str]]        # (ジオメトリ名, スキンクラスター名)
```

### create_from_root_joints() 関数

ルートジョイントからジョイントチェーンを自動展開するラッパー関数。

```python
result, skin = command.create_from_root_joints(
    root_joints: list[str],           # ルートジョイントのリスト（2本以上必須）
    skip: int = 0,                    # スキップするジョイント数
    # ... その他のパラメータは main() と同じ
)
```

### create_from_parallel_joints() 関数

並列ジョイント行（同じ階層レベルのジョイント）を転置してチェーンを作成するラッパー関数。

```python
result, skin = command.create_from_parallel_joints(
    parallel_rows: list[list[str]],   # 並列ジョイント行のリスト
    # ... その他のパラメータは main() と同じ
)
```

### 使用例

```python
# 直接チェーンを指定（main関数）
result, skin = command.main(
    joint_chains=[
        ["jointA1", "jointA2", "jointA3"],
        ["jointB1", "jointB2", "jointB3"],
    ],
    output_type="mesh",
    is_bind=True,
)

# ルートジョイントから自動展開（create_from_root_joints）
result, skin = command.create_from_root_joints(
    root_joints=["jointA1", "jointB1"],
    output_type="mesh",
    is_bind=True,
)

# 環状メッシュ（スカート用）
result, skin = command.create_from_root_joints(
    root_joints=["jointA1", "jointB1", "jointC1"],
    close=True,
    output_type="mesh",
    is_bind=True,
)

# 環状NURBSサーフェス
result, skin = command.create_from_root_joints(
    root_joints=["jointA1", "jointB1", "jointC1"],
    close=True,
    output_type="nurbsSurface",
    is_bind=True,
)

# スキンケージに変換（nurbsSurface + is_bind=True時のみ）
result, skin = command.create_from_root_joints(
    root_joints=["jointA1", "jointB1"],
    output_type="nurbsSurface",
    is_bind=True,
    to_skin_cage=True,
    skin_cage_division_levels=2,
)

# 並列ジョイントからチェーンを作成（create_from_parallel_joints）
# Row 0: [jointAA, jointBA, jointCA] <- 同じ階層レベル（ルート）
# Row 1: [jointAB, jointBB, jointCB] <- 同じ階層レベル（子1）
# Row 2: [jointAC, jointBC, jointCC] <- 同じ階層レベル（子2）
result, skin = command.create_from_parallel_joints(
    parallel_rows=[
        ["jointAA", "jointBA", "jointCA"],
        ["jointAB", "jointBB", "jointCB"],
        ["jointAC", "jointBC", "jointCC"],
    ],
    close=True,
    is_bind=True,
)
```

---

## 具体的な使用方法

- jointA1, jointA2, jointA3, ... と jointB1, jointB2, jointB3, ... とそれぞれジョイントチェーンがあった場合その二つのルートジョイントとなる jointA1 と jointB1 を選択し実行する。
その時、二つのジョイントチェーンにそれぞれカーブが作成され ( Curve/Surface Creator の Object が Curve を選択しているときの方法で) そのカーブが NurbsSurface か Polygon ( mesh ) でロフトされたオブジェクトが作成される。

- jointA1, jointB1, jointC1, jointD1... など複数のジョイントチェーンのルートを選択し実行する。そうすると jointA1, jointB1, jointC1, jointD1 とロフトされさらに Close オプションがオンの時、jointD1 と jointA1 間もロフトされ閉じられた（この場合スカートだったらシリンダーの形状になるように）オブジェクトが作成される。

- 上の仕様でサーフェースが作成され、is_bind がオンの時スキンウエイトも自動で作成される。

---

## 技術的な詳細

### Maya loftコマンドの仕様

**NURBS出力時:**
- `cv[u][v]`: u=カーブ方向（ジョイント位置）、v=ロフト方向（チェーン位置）
- degree=3でロフト → 中間CVが生成される
- `close=True`時: CVインデックスが1つオフセット（v=0が最後のチェーン）
- `rsn=True` で法線を反転（外向きに）

**メッシュ出力時:**
- `format=3`（CV位置にテッセレート）を使用
- `polygonType=1`（クワッド）を使用
- `close=True`時: 最初と最後の頂点行が同じ位置（シームで重複）
- `rsn=False` で法線は反転しない

### ウェイト計算ロジック

1. CV/頂点のグリッド位置 (u, v) を取得
2. u位置からチェーンインデックスと補間係数を計算
3. v位置からジョイントインデックスと補間係数を計算
4. 4つのジョイント（2チェーン × 2ジョイント）に対してウェイト分配
5. 正規化して合計1.0にする

### degree=3の中間CV処理

B-spline基底関数の特性により、degree=3では中間CVのウェイトを調整:
- 最初のスパン: position_in_segment = 1/3 → (0.667, 0.333)
- 最後のスパン: position_in_segment = 2/3 → (0.333, 0.667)

### loft_weight_method の詳細

ロフト方向（チェーン間）のウェイト補間方法を制御します。

**index (デフォルト)**:
- インデックスベースの線形補間
- CV/頂点のグリッド位置から補間係数を計算
- 最も高速で、均等なCV配置に適している

**distance**:
- U=0のCV列に沿った累積距離に基づく補間
- 各CVの位置を取得し、実際の3D距離を計算
- CV間の距離が不均等な場合に有効

**projection**:
- 点Pを線分ABに投影して補間係数を計算
- A: 一方のチェーンに対応するCV位置
- B: 他方のチェーンに対応するCV位置
- P: 補間対象のCV位置
- T: PからABへの垂線の足
- AT:TB の比率でウェイトを分配
- ジオメトリの形状に基づいた自然な補間

---

## 必要なオプション（元の設計）

### Curve 作成時のオプション
※ 実際カーブは最後に削除されますが、工程として内部的には一度作成する必要があります。

- ~~Degree~~ → 削除（常にdegree=3を使用）
- Center
- Divisions (curve_divisions)
- Skip（create_from_root_joints のみ）

### Surface 作成時のオプション

- Close: ロフトを最終的に閉じるかどうか
- Divisions (surface_divisions): サーフェースの間の分割数

### バインド時のオプション

- weight_method: linear / ease / step
- smooth_iterations: スムージング回数
- parent_influence_ratio: 親ジョイントの影響比率
- remove_end: 末端ジョイントのウェイトを親にマージ

---

## Surface の Divisions について

Maya のカーブロフトのパターンを記載しておきます。

### Curve の Degree が 1 の場合

**各カーブ間の NURBS Surface の Divisions を指定する場合**

```py
divisions = 2
cmds.loft(["curve1", "curve2"], ch=False, u=True, c=False, ar=True, d=1, ss=divisions, rn=False, po=0, rsn=True)
```


**各カーブ間の Mesh の Divisions を指定する場合**

```py
divisions = 2
cmds.loft(["curve1", "curve2"], ch=False, u=True, c=False, ar=True, d=1, ss=divisions, rn=True, po=1, rsn=True)
```

### Curve の Degree が 3 の場合

**各カーブ間の NURBS Surface の Divisions を指定する場合**

ここが複雑です。Degree 3 のカーブをロフトしたときは、そのロフト方向も Degree 3 で設定する必要があります。
Degree3 の状態では、カーブのCVが（正確にはロフト方向であることに注意してください。）Degree+1 の数必要です。
それを踏まえての状況を説明します。これはウエイトを設定するときに気を付けなければいけないポイントです。

コマンドは divisions を変更しても同じものを使用します。
```py
divisions = 2
cmds.loft("curve1", "curve2", ch=True, u=True, c=False, ar=True, d=3, ss=divisions, rn=True, po=0, rsn=True)
# d=3 になることに注意
```

以下は、カーブ間の CV数を表しています。
- divisions が 1 の場合のロフト方向のCV数: 2
- divisions が 2 の場合のロフト方向のCV数: 3
- divisions が 3 の場合のロフト方向のCV数: 4


**各カーブ間の Mesh の Divisions を指定する場合**

Degree 3 の場合と変わらないです。

```py
divisions = 2
cmds.loft(["curve3", "curve4"], ch=False, u=True, c=False, ar=True, d=1, ss=divisions, rn=True, po=1, rsn=True)
```
