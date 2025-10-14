# FakeTools ドキュメントシステム

Pandocベースの多言語対応ドキュメントシステム

## 必要な環境

- **Python 3.11以上**
- **Pandoc**: [公式サイト](https://pandoc.org/installing.html)からインストール

## ビルド方法

```bash
# docsディレクトリから実行
cd docs
python build.py
```

出力先: `docs/output/`

ブラウザで `docs/output/index.html` を直接開いて確認できます。

## ページの追加方法

### 1. マークダウンファイルを作成

```
docs/src/ja/{category}/{tool_name}.md     # 日本語版
docs/src/en/{category}/{tool_name}.md     # 英語版
```

カテゴリー: `rig`, `model`, `anim`, `common`

### 2. YAML Front Matterを記述

```markdown
---
title: ツール名
category: rig
description: ツールの説明
lang: ja
lang-ref: unique_tool_id
---

# ツール名

ここから本文...
```

**必須フィールド:**
- `title`: ページタイトル
- `lang`: 言語コード (`ja` または `en`)

**推奨フィールド:**
- `category`: カテゴリーID
- `description`: ページの説明
- `lang-ref`: 言語間リンク用のユニークID（対応する他言語ページと同じ値を設定）

### 3. 画像の配置（任意）

```
docs/src/ja/images/{category}/{tool_name}/image.png
```

マークダウンから参照:
```markdown
![説明](images/{category}/{tool_name}/image.png)
```

### 4. ビルドして確認

```bash
python docs/build.py
```

ブラウザで `docs/output/index.html` を開いて確認
