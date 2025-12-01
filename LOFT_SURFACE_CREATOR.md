# Loft Surface Creator

## ツールの概要

スカートやベルトなど 複数のジョイントチェーンにより構成されている部分のウエイト転送元を作成するツール。

Curve/Surface Creator に似ているツールだがこちらのほうが少し複雑になる。

## 具体的な使用方法

- jointA1, jointA2, jointA3, ... と jointB1, jointB2, jointB3, ... とそれぞれジョイントチェーンがあった場合その二つのルートジョイントとなる jointA1 と jointB1 を選択し実行する。
その時、二つのジョイントチェーンにそれぞれカーブが作成され ( Curve/Surface Creator の Object が Curve を選択しているときの方法で) そのカーブが NurbsSurface か Polygon ( mesh ) でロフトされたオブジェクトが作成される。

- jointA1, jointB1, jointC1, jointD1... など複数のジョイントチェーンのルートを選択し実行する。そうすると jointA1, jointB1, jointC1, jointD1 とロフトされさらに Close オプションがオンの時、jointD1 と jointA1 間もロフトされ閉じられた（この場合スカートだったらシリンダーの形状になるように）オブジェクトが作成される。

- 上の仕様でサーフェースが作成され、Curve/Surface Creator と同じ方法で is_bind がオンの時スキンウエイトも自動で作成される。（相談）

## 必要なオプション

### Curve 作成時のオプション
※ 実際カーブは最後に削除されますが、工程として内部的には一度作成する必要があります。

基本的に、Curve/Surface Creator からコードを引用するか参照できます。
また、アルゴリズムもそちらを参考にしてください。

- Degree
- Center
- Divisions
- Skip

### Surface 作成時のオプション

- Close: ロフトを最終的に閉じるかどうか
- Divisions: サーフェースの間の分割数（ちょっと複雑なので ## Surface の Divisions についてを参照してください。）


### バインド時のオプション
基本的にCurve/Surface Creatorと同様ですが、各カーブ間のウエイトをどのように作成するか相談させてください。


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
