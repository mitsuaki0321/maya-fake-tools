# Code Editor 多言語化 / MEL 対応 実装計画 & 進捗

> このドキュメントは、`scripts/faketools/tools/common/code_editor/` を Python 専用から多言語対応（まずは MEL）へ拡張するための計画と進捗を保持する作業用ファイルです。
> **新しい会話セッションで再開するときは、このファイルだけ読めば全体像と現在地が分かる** ことを目的としています。

---

## 0. 再開用クイックスタート（コンテキスト切れ時）

新しいセッションで作業を継続するときは、この順で読む:

1. このファイル全体
2. `scripts/faketools/tools/common/code_editor/__init__.py`
3. `scripts/faketools/tools/common/code_editor/ui/code_editor.py`（中核クラス）
4. `scripts/faketools/tools/common/code_editor/command/execution.py`（実行ブリッジ）
5. 本ファイル下部 §6「進捗チェックリスト」で **次の未着手タスク** を確認
6. §7「決定ログ」と §8「未解決事項」を確認
7. CLAUDE.md の「Git Commit Rules」（**勝手にコミットしない**）

実装を再開する前に、**ユーザーに「`MEL_SUPPORT_PLAN.md` の進捗を確認しました。次は X から進めますがよろしいですか？」と確認** すること。

---

## 1. 背景と目的

- 現在エディタは Python 専用設計
- ユーザーから `.ipynb` 対応の打診あり → 前段として MEL 対応を入れることで「多言語化基盤」を実証する戦略を採用
- Python ハードコードは **約 15 ファイル / 1,800 行**に分散しており、無計画に手を入れると差分が爆発する
- そこで `LanguageProfile` データクラスを導入し、言語固有定数を 1 箇所に集約する **中規模リファクタリング** を選択

## 1.5 設計原則（重要）

### 1.5.1 言語ごとの機能セットは opt-in
**Python の全機能を他言語に強制しない**。各言語は必要な機能だけを `LanguageProfile` で提供し、提供しない機能は `None` のままにする。

例:
- MEL は autocomplete を含めなくてよい（`completion_engine_factory=None`）
- MEL は docstring レンダリングを含めなくてよい（`structured` パスを使わない）
- 将来 `.ipynb` を追加する場合も同様、必要な機能だけ実装

### 1.5.2 グレースフル・デグラデーション
消費側のコード（`PythonEditor`、`ExecutionManager`、コンテキストメニュービルダー等）は、profile が機能を提供しない場合に **機能を無効化 / スキップ** する設計にする。エラーや空挙動でなく、UI 上もその機能ボタンを表示しない / グレーアウトする。

具体例:
- `language.completion_engine_factory is None` なら autocomplete 関連のキーバインドと UI を無効化
- `language.context_menu_extender is None` ならその言語固有メニュー項目を出さない
- `language.highlighter_factory is None` ならハイライトなしのプレーンテキスト表示

### 1.5.3 機能採否の最終決定タイミング
**各言語を「本格的に」追加するタイミングで、含める機能と含めない機能を再確認する**。Phase 1 で MEL プロファイル骨格を作る際の機能リストは暫定で、実装着手時にユーザーと再相談する。

### 1.5.4 UI/UX は別途
タブヘッダーの言語表示、ツールバーの状態切替、新規ファイルダイアログのフォーマット、設定 UI 等は **後でまとめて相談する**。`MEL_SUPPORT_PLAN.md` には決まった時点で追記する。

## 2. 全体ロードマップ

| Phase | 内容 | 状態 |
|---|---|---|
| **0** | `LanguageProfile` 導入、`PythonEditor` → `CodeEditor` リネーム、Python 定数の集約。挙動は変えない | 未着手 |
| 1 | `MEL` プロファイル追加。実行・保存・コメント・シェルフ・新規ファイルを分岐 | 未着手 |
| 2 | `mel_highlighter.py`（正規表現ステートマシン）+ `syntax_colors.json` キー追加 | 未着手 |
| 3 | ブレース折りたたみ戦略追加、`auto_indent` の汎用化 | 未着手 |
| 4 | `MelCompletionEngine`（`cmds.help` 経由）、`global proc` 静的パース | 未着手 |
| 5 | `MayaHelpDetector` の MEL パターン追加 | 未着手 |

## 3. 調査結果サマリ（Python ハードコード分布）

> 詳細は本ファイル末尾の §10「詳細調査メモ」参照。

| 領域 | 主なファイル | 行数感 |
|---|---|---|
| 拡張子 `.py` | `file_ops.py`, `file_operations_controller.py`, `editor_tab_widget.py`, `file_explorer.py`, `session_manager.py`, `workspace_manager.py` | 散在 |
| シンタックスハイライト | `python_highlighter.py`（stdlib `tokenize` 完全依存） | 510 |
| オートコンプリート | `command/autocomplete/engine.py`（jedi）, `ui/autocomplete/*` | 700+ |
| オートインデント | `auto_indent.py` | 165 |
| コード折りたたみ | `code_folding.py` | 450 |
| コメントトグル | `shortcut_handler.py:319-460` | 150 |
| ブラケットマッチ | `bracket_match_highlighter.py` | — |
| 実行ブリッジ | `execution.py`（`sourceType="python"` 固定） | 190 |
| Maya ヘルプ検出 | `utils/maya_help_detector.py` | — |
| シェルフ追加 | `command/maya_shelf.py:38` | — |
| エディタクラス名 | `PythonEditor` を 11 ファイル / 29 箇所で参照 | — |
| **コンテキストメニュー** | `ui/editor_context_menu.py` — Inspect Object (`dir`)、Inspect Help (`help`)、Reload Module (`importlib.reload`) はすべて Python 専用 | 190 |
| **Inspect コード生成** | `ui/execution_manager.py:144-203` — `handle_object_inspection` は `dir(X)` / `help(X)` の Python スニペットをハードコード | 60 |
| **ヘルプポップアップ レンダラ**（autocomplete の一部） | `ui/help/renderer/syntax.py`（Pygments `PythonLexer`）, `structured.py`（`docstring_parser` で numpydoc/Google/RST）, `detect.py:32`（`SIGNATURE_RE` が Python 前提）。Maya help 分岐（`cmds.help` 出力）は言語非依存で MEL でも動く | 7 ファイル |

## 4. Phase 0 詳細設計

### 4.1 新規モジュール構成

```
code_editor/
└── languages/
    ├── __init__.py        # 再エクスポート + ALL_PROFILES, DEFAULT_PROFILE, get_profile_for_path()
    ├── _types.py          # LanguageProfile, ShelfConfig（型定義のみ、循環インポート回避のため分離）
    └── python.py          # PYTHON profile の定義
```

### 4.2 `LanguageProfile` / `ShelfConfig` データクラス

設計原則（§1.5）に基づき、必須フィールドは最小限、それ以外はすべて `Optional` で `None` がデフォルト。
`None` のフィールドが提供する機能は、消費側で **無効化 / UI 非表示 / グレーアウト** する（グレースフル・デグラデーション）。

```python
# languages/__init__.py
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass(frozen=True)
class ShelfConfig:
    """Maya シェルフボタン設定。シェルフ追加非対応の言語では LanguageProfile.shelf_config = None。"""
    source_type: str   # "python" / "mel" — cmdScrollFieldExecuter / shelfButton -stp
    label: str         # ボタンラベル
    icon: str          # アイコンリソース名（例: "pythonFamily.png"）


@dataclass(frozen=True)
class LanguageProfile:
    # ===== 必須（4 項目）=====
    id: str
    display_name: str
    extensions: tuple[str, ...]
    default_extension: str

    # ===== コメント =====
    line_comment: Optional[str] = None
    """行コメント記号。None ならコメントトグルキーバインド無効。"""
    block_comment: Optional[tuple[str, str]] = None
    """ブロックコメント開始/終了。None ならブロックコメント機能無効。"""

    # ===== オートインデント =====
    extra_indent_trigger: Optional[Callable[[str], bool]] = None
    """現在行の cursor 直前テキスト（strip 済み）を受け取り、追加インデント要否を返す述語。

    多くの言語では None でよい（ブラケット系のブロックは hanging indent 規則で処理される）。
    Python: `lambda s: s.endswith(":") and not s.startswith("#")`
    MEL:    None（`{` はブラケットなので hanging indent で完全処理）

    将来コメント除去やトークン解析が必要なら、述語内で実装する。
    """

    # ===== 実行 =====
    source_type: Optional[str] = None
    """cmdScrollFieldExecuter の sourceType ("python" / "mel")。None なら Run 系すべて無効。"""

    # ===== シェルフ =====
    shelf_config: Optional[ShelfConfig] = None
    """シェルフ追加設定。None なら "Add to Shelf" メニュー項目を出さない。"""

    # ===== コンテキストメニュー =====
    context_menu_extender: Optional[Callable] = None
    """選択中 identifier に対し言語固有メニュー項目を追加。
    引数: (menu, editor, selected_identifier)。None なら追加項目なし。
    Python: Inspect Object / Inspect Help / Reload Module
    MEL:    whatIs / Source File（採用するかは Phase 1 着手時に再相談）"""

    identifier_validator: Optional[Callable[[str], bool]] = None
    """その言語の識別子として valid か判定。Python は英数+`_`、MEL は先頭 `$` を許容など。
    None なら identifier ベースのメニュー項目（Inspect 等）を出さない。"""

    inspection_snippets: Optional[Callable] = None
    """inspection_type ('dir' | 'help') → 実行コード文字列を返す関数。
    None なら Inspect Object / Help を提供しない。"""

    # ===== 拡張ポイント =====
    highlighter_factory: Optional[Callable] = None
    """QSyntaxHighlighter インスタンスを返す factory。None ならプレーンテキスト表示。"""

    completion_engine_factory: Optional[Callable] = None
    """補完エンジン (jedi 相当) を返す factory。None なら autocomplete 全機能無効。"""

    folding_strategy: Optional[Callable] = None
    """コード折りたたみ判定関数。None なら折りたたみ無効。"""

    # ===== 自動生成プロパティ =====
    @property
    def file_filter(self) -> str:
        """ファイルダイアログフィルタ。例: 'Python Files (*.py)'。"""
        ext_pattern = " ".join(f"*{e}" for e in self.extensions)
        return f"{self.display_name} Files ({ext_pattern})"

    @property
    def line_comment_with_space(self) -> Optional[str]:
        """`line_comment` + 空白。line_comment が None なら None。"""
        return f"{self.line_comment} " if self.line_comment else None
```

#### 必須 / Optional / 自動生成 一覧

**必須（4 項目）** — どの言語でも必ず指定する:
| フィールド | 用途 |
|---|---|
| `id` | profile 識別子（設定永続化のキー） |
| `display_name` | UI 表示 + `file_filter` 生成元 |
| `extensions` | パスから profile 解決 + `file_filter` 生成元 |
| `default_extension` | 新規ファイル名生成 |

**Optional（11 項目、すべて `None` がデフォルト）** — `None` のとき該当機能を消費側で無効化:
| フィールド | None で無効化される機能 |
|---|---|
| `line_comment` | コメントトグル（`Ctrl+/`） |
| `block_comment` | ブロックコメントトグル |
| `extra_indent_trigger` | auto-indent の追加インデント発生条件（ブラケット系は既存の hanging indent で処理されるため不要） |
| `source_type` | Run / 実行関連すべて |
| `shelf_config` | "Add to Shelf" メニュー項目 |
| `context_menu_extender` | 言語固有右クリック項目 |
| `identifier_validator` | 識別子ベースのアクション全般 |
| `inspection_snippets` | Inspect Object / Help |
| `highlighter_factory` | シンタックスハイライト（プレーン表示にフォールバック） |
| `completion_engine_factory` | autocomplete |
| `folding_strategy` | コード折りたたみ |

**自動生成プロパティ（2 項目）** — フィールドではなく派生値:
| プロパティ | 導出元 |
|---|---|
| `file_filter` | `display_name`, `extensions` |
| `line_comment_with_space` | `line_comment` |

#### PYTHON インスタンス

```python
# languages/python.py
from . import LanguageProfile, ShelfConfig

PYTHON = LanguageProfile(
    id="python",
    display_name="Python",
    extensions=(".py",),
    default_extension=".py",
    line_comment="#",
    extra_indent_trigger=lambda s: s.endswith(":") and not s.startswith("#"),
    source_type="python",
    shelf_config=ShelfConfig(
        source_type="python",
        label="Python",
        icon="pythonFamily.png",
    ),
    # context_menu_extender, inspection_snippets, identifier_validator は commit 7 で設定
    # highlighter_factory は commit 2 で設定
    # completion_engine_factory, folding_strategy は将来追加分
)
```

#### MEL インスタンス参考形（Phase 1 想定、機能セットは着手時に再相談）

```python
# languages/mel.py（Phase 1 で新設）
from . import LanguageProfile, ShelfConfig

MEL = LanguageProfile(
    id="mel",
    display_name="MEL",
    extensions=(".mel",),
    default_extension=".mel",
    line_comment="//",
    block_comment=("/*", "*/"),
    # extra_indent_trigger=None  ← `{` はブラケットなので hanging indent で処理、述語不要
    source_type="mel",
    shelf_config=ShelfConfig(
        source_type="mel",
        label="MEL",
        icon="commandButton.png",  # 仮、要確認
    ),
    # autocomplete・highlighter・folding・context_menu_extender は採否を着手時に決定
)
```

### 4.3 リネーム戦略（互換維持）

`ui/code_editor.py` 末尾に alias を残す:

```python
PythonEditor = CodeEditor   # deprecated: kept for one release
```

**29 箇所の `isinstance(editor, PythonEditor)` は alias 経由で動作する** ため、機械的書き換えは不要。

### 4.4 やらないこと（Phase 0 スコープ外）

- `python_highlighter.py` 本体の汎化（factory で包むだけ）
- `auto_indent.py` / `code_folding.py` / `bracket_match_highlighter.py` の汎化
- `maya_help_detector.py` の MEL パターン
- jedi エンジンの差し替え機構

これらはすべて profile に空フィールドを用意するだけで、利用は Phase 1 以降。

## 5. コミット粒度

| # | 内容 | 触るファイル |
|---|---|---|
| 1 | `languages/` 新設、`LanguageProfile` / `ShelfConfig` / `PYTHON` 定義のみ（誰も使わない） | `languages/__init__.py`, `languages/_types.py`, `languages/python.py` |
| 2 | `CodeEditor` リネーム + alias、`language` 引数追加、`setup_syntax_highlighting` を factory 経由に | `ui/code_editor.py` |
| 3 | `execution.py` / `execution_manager.py` を profile 化 | `command/execution.py`, `ui/execution_manager.py` |
| 4 | `maya_shelf.py` を profile 化 + 呼出側 `main_window.add_to_shelf` で active editor の language を渡す | `command/maya_shelf.py`, `ui/main_window.py` |
| 5a | ファイル操作系（低レベル）を profile 化 | `command/file_ops.py`, `settings/session_manager.py`, `ui/ui_session_manager.py`, `settings/workspace_manager.py`, `languages/__init__.py`（`KNOWN_EXTENSIONS` 追加） |
| 5b | ファイル操作系（UI レベル）を profile 化 | `ui/file_operations_controller.py`, `ui/editor_tab_widget.py`, `ui/panels/file_explorer.py` |
| 6 | コメントトグルを profile 化 | `ui/shortcut_handler.py` |
| 7 | コンテキストメニュー / Inspect を profile 化 | `ui/editor_context_menu.py`, `ui/execution_manager.py`, `languages/python.py` |
| 8 | docstring / `__init__.py` の説明文修正 | `code_editor/__init__.py` |

各コミット後に **Maya 起動確認 + ruff/mypy** を入れる。

## 6. 進捗チェックリスト

> 完了したらチェックを入れる。コミットハッシュも記録する。
> 各 commit のあとには **`uv run ruff check scripts/faketools/tools/common/code_editor` と `uv run mypy scripts/faketools/tools/common/code_editor` を流して PASS を確認** する。

### Phase 0
- [x] **commit 1**: `languages/` 新設、`LanguageProfile` / `ShelfConfig` / `PYTHON` 定義。ruff PASS、smoke test PASS。`maya_terminal.py:24` の mypy エラーは**既存の無関係な問題** _(hash: `30c26f2`)_
- [x] **commit 2**: `PythonEditor` → `CodeEditor` リネーム + alias、`__init__` に `language: LanguageProfile = PYTHON` 引数追加、`setup_syntax_highlighting` を `language.highlighter_factory` 経由に。PYTHON 側に `_python_highlighter_factory`（遅延 import）を追加。ruff PASS、smoke test PASS。`languages/` パッケージは Qt 非依存を維持 _(hash: `d0ac3ea`)_
- [x] **commit 3**: `NativeExecutionBridge` に `language: LanguageProfile = PYTHON` 引数追加、`sourceType` を `language.source_type` から取得、hidden window 名を per-language 化（`hiddenNativeExecuter_{id}`）、`python_executer` → `executer` rename。`ExecutionManager` に `_bridges: dict` キャッシュと `_active_editor_language()` / `_refresh_active_bridge()` / `cleanup_bridges()` を追加、執行/inspection 両メソッドで `_refresh_active_bridge` 呼出に置換。`main_window.closeEvent` を `cleanup_bridges()` 呼出に変更。`execute_silent` / `build_exec_globals` の Python 固有性は docstring 明記、変更は Phase 1 持ち越し。ruff PASS、smoke test PASS _(hash: `85d1b1c`)_
- [x] **commit 4**: `maya_shelf.add_to_active_shelf` に `language: LanguageProfile = PYTHON` 引数追加、`-stp` / `-l` / `-i1` を `language.shelf_config` から取得、`shelf_config is None` で `(False, "Shelf-add not supported for ...")` を即返却。`main_window.add_to_shelf` で active editor の language を渡すよう修正。ruff PASS、smoke test PASS（Maya 不在環境 / `shelf_config=None` 両パス確認） _(hash: `56fdc95`)_
- [x] **commit 5a**: `languages/__init__.py` に `KNOWN_EXTENSIONS` frozenset 追加。`file_ops.create_python_file` を `create_source_file(parent_dir, name, language=PYTHON, initial_content=None)` にリネーム + 言語の `default_extension` / `line_comment_with_space` から自動生成、旧名 `create_python_file` を deprecated alias として保持。`session_manager` / `ui_session_manager` の `"Untitled.py"` フォールバックを `f"Untitled{DEFAULT_PROFILE.default_extension}"` に。`workspace_manager._copy_startup_files` の `endswith(".py")` を `KNOWN_EXTENSIONS` 判定に。ruff PASS、smoke test PASS _(hash: `119f0e4`)_
- [x] **commit 5b**: `file_operations_controller.new_file` の `.py` 拡張子を `DEFAULT_PROFILE.default_extension` 経由に。`editor_tab_widget.new_file` に `language: LanguageProfile = DEFAULT_PROFILE` 引数追加、`Untitled{n}.py` を `language.default_extension` 経由に、preview 昇格と save dialog（タイトル / フィルタ）を editor の language 経由に。`file_explorer.py` に `_path_has_known_extension(path)` ヘルパ追加し 4 箇所の `suffix().lower() == "py"` ゲートを置換、外部ドラッグフィルタも置換、メニュー文言 / ダイアログタイトルを `DEFAULT_PROFILE.display_name` 経由に、`create_python_file` を `create_source_file(language=DEFAULT_PROFILE)` に切替。ruff PASS、smoke test PASS _(hash: `31fa1aa`)_
- [x] **commit 6**: `shortcut_handler.toggle_line_comment` で `editor.language.line_comment` / `line_comment_with_space` を参照、`line_comment is None` で no-op（graceful degradation）。`#` / `# ` リテラルを `prefix` / `prefix_with_space` 経由に、`KeepAnchor, 1/2` を `len(prefix)` / `len(prefix_with_space)` 経由に。`_toggle_comment_multi_cursor` を `(editor, prefix, prefix_with_space)` 受取に変更、`deleteChar()` 単呼びを `for _ in range(len(prefix))` ループに（複数文字 prefix 対応）。`cursor.block().text()[0] == " "` の trailing-space 検出ロジックは既存挙動（軽微なバグ含む）保持、§8 に記録。ruff PASS、構造検証 PASS _(hash: `8600d62`)_
- [x] **commit 7 (実装完了、コミット待ち)**: Python 専用ヘルパ（`_is_valid_identifier` / `_is_valid_module_name` / `_reload_module` / `_build_reload_code` / `_find_execution_manager` / dir & help テンプレート）を `editor_context_menu.py` と `execution_manager.py` から `languages/python.py` に集約。新規 `_python_context_menu_extender(menu, editor, identifier)` と `_python_inspection_snippets(inspection_type, object_name)` を追加（Qt は extender 内部で遅延 import）。PYTHON プロファイルに `context_menu_extender` / `identifier_validator` / `inspection_snippets` を設定。`build_context_menu` を「validator → extender 呼出」のジェネリックフローに、`handle_object_inspection` を「ヘッダ表示 → `language.inspection_snippets` 経由でコード生成 → execute」に置換。ruff PASS、smoke test PASS（profile fields / validator / snippets / Qt 非依存維持） _(hash: 未コミット)_
- [ ] **commit 8**: docstring / 説明文修正 _(hash: ____)_
- [ ] **Phase 0 動作確認**: Maya 起動 → 既存 `.py` ファイル開閉 / 新規 Untitled / 保存ダイアログ / コメントトグル / Run / Add to Shelf / ファイルエクスプローラ操作 / preview 昇格 / セッション復元 / 右クリック Inspect Object / Inspect Help / Reload Module がすべて従来通り動く

### Phase 1
> **着手前にユーザーと再相談**: MEL に含める機能 / 含めない機能を確定させる（§1.5.1, §1.5.3 参照）。
> 以下は **暫定リスト**。autocomplete / コンテキストメニュー extender / 折りたたみ等は MEL では不要かもしれない。

- [ ] **着手前確認**: MEL に含める機能セットをユーザーと確定
- [ ] **着手前確認**: UI/UX 方針（タブ表示・新規ファイル UI 等）をユーザーと相談
- [ ] `MEL` プロファイル追加（`languages/mel.py`） — 採用機能のみ実装、その他は `None`
- [ ] 保存ダイアログフィルタの拡張
- [ ] `execution.py` で `sourceType="mel"` 用の 2 つ目の `cmdScrollFieldExecuter` を生成・分岐
- [ ] `maya_shelf.py` の `-stp` / ラベル / アイコン分岐
- [ ] `file_explorer.py` で `.mel` ファイルの開封
- [ ] 新規ファイルダイアログのタイトル / デフォルト名分岐
- [ ] （MEL に含める場合のみ）MEL 用 `context_menu_extender` / `inspection_snippets` 実装
- [ ] Maya で MEL ファイル open / edit / save / run の smoke test

### Phase 2 以降
未着手（Phase 1 完了後に詳細化）

#### Phase 4 で対応するヘルプレンダラ関連（事前メモ）
- `LanguageProfile.signature_highlighter` フィールドを追加し、`syntax.highlight_python` 直呼びを profile 経由に
- `detect.SIGNATURE_RE` を Python 用と MEL 用で分岐、もしくは profile に `signature_pattern` を持たせる
- ユーザー定義 `global proc` のシグネチャ抽出パスを `structured` / `plain` の MEL 版として追加
- Maya help 分岐（`maya.render`）はそのまま流用可能

## 7. 決定ログ

| 日付 | 決定事項 | 理由 |
|---|---|---|
| 2026-05-01 | 多言語化方針として案 B（`LanguageProfile` データクラス）を採用 | 案 A は分岐散在で 3 言語目に破綻、案 C は `isinstance` 大量書き換えで侵襲的すぎる |
| 2026-05-01 | `.ipynb` より MEL を先行 | MEL 対応で多言語化基盤を実証 → `.ipynb` はその基盤の上に乗せる |
| 2026-05-01 | `PythonEditor` は alias で残す | 29 箇所の `isinstance` を一括書き換えしないため |
| 2026-05-01 | `block_open_chars` などは Phase 0 でフィールドだけ追加し参照側は Phase 3 まで触らない | 段階的に進めて回帰範囲を絞る |
| 2026-05-01 | コンテキストメニューも profile 化対象に追加（commit 7） | Inspect Object / Help / Reload Module は Python 専用で、MEL では whatIs / Source File に置き換わるべき。単純な分岐ではなく extender 関数を profile に持たせる方式 |
| 2026-05-01 | ヘルプポップアップ レンダラ（`ui/help/renderer/`）は Phase 0 では触らず、Phase 4 で対応 | Maya help 分岐は既に言語非依存で動作。Python 専用パス（`structured` / `syntax.PythonLexer` / `detect.SIGNATURE_RE`）の改修は MEL autocomplete 実装と一体で進めた方が依存関係を整理できる |
| 2026-05-01 | **言語ごとの機能セットは opt-in 方式とする** | Python 全機能を他言語に強制しない。MEL は autocomplete 不要かもしれない等、含む/含まないは各言語の本格追加時に再判断。`LanguageProfile` の Optional フィールドを `None` のまま残せばその機能は無効になる消費側設計（グレースフル・デグラデーション）。詳細 §1.5 |
| 2026-05-01 | UI/UX 詳細は後で別途相談 | タブヘッダー言語表示、ツールバー状態切替、新規ファイルダイアログのフォーマット、設定 UI など。決まった時点で本ファイルに追記 |
| 2026-05-01 | `LanguageProfile` を全 Optional 設計に再構成 | §1.5 opt-in 原則と整合。必須は `id` / `display_name` / `extensions` / `default_extension` の 4 項目のみ。`file_filter` と `line_comment_with_space` は自動生成プロパティ化。`shelf_*` 3 フィールドは `ShelfConfig` データクラスに集約しまるごと Optional 化 |
| 2026-05-01 | `block_open_chars: tuple[str, ...]` を `extra_indent_trigger: Callable[[str], bool]` に変更 | `auto_indent.py` の hanging indent 規則は既に `(`, `[`, `{` の未閉じを処理するため、ブラケット系言語（MEL 等）には追加トリガが不要。`block_open_chars` が必要なのは事実上 Python の `:` だけ。Callable 化で将来コメント除去・トークン解析等の複雑な条件にも拡張可能。MEL は `None` で済み、hanging indent と closing bracket alignment で完全カバー |
| 2026-05-01 | `line_comment` / `block_comment` は文字列ベースのまま維持（Callable 化しない） | コメントトグルは「行頭プレフィックスの追加 / 除去」のみで、インデント判定のような行内コンテキスト解析を必要としない。Python / MEL とも単一文字列で完全表現可。複数形式が必要になれば後方互換的に `tuple[str, ...]` 化可能。Python の `"""..."""` を `block_comment` に入れない（文字列リテラルでコメントではない、linter 警告の原因）ため Python は `block_comment=None` |
| 2026-05-01 | 型定義を `_types.py` に分離 | 当初 `__init__.py` に `LanguageProfile` / `ShelfConfig` を直接定義する計画だったが、`from .python import PYTHON` を classes 定義の後に置くと ruff E402（module-level import not at top）が発生。`_types.py` を分離することで `__init__.py` を純粋な再エクスポート + ファクトリ関数のみに保てる |

## 7.5 UI/UX 検討事項（保留中、別途相談）

以下は実装時にユーザーと相談して決める。決定したら本セクションを更新。

- タブヘッダーでの言語表示（アイコン / ラベル / ツールチップ）
- ツールバーの言語依存ボタン（Run / Add to Shelf 等）の状態切替（言語に応じて活性/非活性、ラベル変更等）
- 新規ファイルダイアログ（言語選択ドロップダウン / 拡張子別の独立メニュー / "New Python File" "New MEL File" の並列メニュー等）
- ファイルエクスプローラのファイル種別アイコン拡張
- ステータスバー / ウィンドウタイトルでの言語表示
- コンテキストメニューでの言語固有アクションの位置（先頭 / 末尾 / セパレータ）
- autocomplete / 折りたたみ等が無効な言語タブでのキーバインド挙動（無視 / 通知 / グレーアウト）

## 8. 未解決事項

- `cmds.help("-list", "*")` のレスポンスサイズと速度（Phase 4 のキャッシュ戦略に影響）
- ユーザ定義 `global proc` の列挙 API は存在しない → 開いているファイルの静的パースに留める方針
- `cmdScrollFieldExecuter(sourceType="mel")` の選択範囲実行のセマンティクス（`;` 区切りで Python と挙動が微妙に違う可能性、要スモークテスト）
- 同一タブ内で Python/MEL 混在は **不可**（プロファイルはタブ単位）
- stdout キャプチャは Maya のレポーターを共有する現アーキで透過のはずだが要確認
- ヘルプポップアップ syntax renderer（`renderer/syntax.py`）の Pygments `PythonLexer` は MEL 例にも当たる → cosmetic、deprioritize
- **MEL ブロックコメント `/* */` のネスト破綻**: トグル対象の選択範囲内に既存の `/* */` があると壊れる。これは MEL の言語仕様（ネスト非サポート）に起因し、`block_comment` のデータ構造設計では解決しない。Phase 1 で MEL を本格追加するときに「既存コメント検出 → トグルキャンセル / ユーザー通知」を消費側（`shortcut_handler.py`）に実装するか判断
- **既存の trailing-space 検出ロジック（`_toggle_comment_multi_cursor`）の軽微なバグ**: `cursor.block().text()[0] == " "` は行頭文字を見ているだけで、削除位置の文字を見ていない。`    #foo`（インデント + space なしコメント）のような edge case でアンコメント時に `f` を巻き込み削除する可能性。Phase 0 では既存挙動を保持。修正は Phase 1+ で `cursor.block().text()[spaces] == " "` に変える等で対応可能

## 9. 制約・ルール（CLAUDE.md より抜粋）

- ❌ **ユーザーの明示的な許可なしにコミットしない**（「commit」「コミット」と言われたときだけ）
- ❌ 新規外部依存ライブラリの追加禁止（ユーザー承認 + 互換ライセンス確認が必要）
- ✅ Python 3.9.7（Maya 2023+）
- ✅ ruff: line-length 150, double quotes
- ✅ Google style docstrings
- ✅ Resolution-independent UI（ピクセル直書き禁止）
- ✅ PySide は `qt_compat` 経由で import
- ✅ 進捗があるたびにこのファイルを更新する

## 10. 詳細調査メモ（参考）

### 10.1 拡張子 `.py` ハードコード箇所

- `command/file_ops.py:115-122` — `create_python_file()` が `.py` を hard-suffix
- `command/file_ops.py:145` — エクスポート名 `create_python_file`
- `ui/file_operations_controller.py:125-131` — "Enter filename (with .py extension)"、auto-append `.py`
- `ui/editor_tab_widget.py:88` — `Untitled{n}.py`
- `ui/editor_tab_widget.py:176-177, 397, 409` — preview 昇格時に `.py` 強制、保存ダイアログ filter `"Python Files (*.py)"`
- `ui/panels/file_explorer.py:300, 578, 595, 644, 1064-1072` — Run ボタンホバー、シングルクリックプレビュー、ダブルクリック開、context menu の "Open"、外部ドラッグフィルタすべて `suffix == "py"` ゲート
- `ui/panels/file_explorer.py:154` — 拡張子→アイコン表に `"py": "python"` のみ
- `ui/panels/file_explorer.py:651, 714` — "New Python File" メニューラベル / ダイアログタイトル
- `settings/session_manager.py:270`, `ui/ui_session_manager.py:164` — フォールバックタブ名 `"Untitled.py"`
- `settings/workspace_manager.py:177` — startup-files copier が `endswith(".py")` でフィルタ

### 10.2 実行ブリッジ

- `command/execution.py:109-114` — `cmdScrollFieldExecuter(... sourceType="python", ...)`（単一ハードコード）
- `command/execution.py:134-143` — 5 箇所の `cmds.cmdScrollFieldExecuter(self.python_executer, ...)` がすべて Python executer 前提
- `command/execution.py:165` — `cmds.python(code)` silent execution
- `command/execution.py:34-55` — `build_exec_globals` は `cmds`/`om2`/`om` のみ注入

### 10.3 シェルフ

- `command/maya_shelf.py:38` — `-stp "python"`、ラベル `"Python"`、アイコン `"pythonFamily.png"` 固定

### 10.4 コメントトグル

- `ui/shortcut_handler.py:319-405` — `toggle_line_comment`：`# ` `#` ベタ書き（lines 365, 386, 388, 392, 394, 402）
- `ui/shortcut_handler.py:407-460` — `_toggle_comment_multi_cursor`（425, 448, 455）

### 10.5 コンテキストメニュー / Inspect

`ui/editor_context_menu.py` のメニュー構成:

| アクション | 実装場所 | Python 依存度 |
|---|---|---|
| Maya help on `cmds.*` | `_maybe_add_maya_help` (line 65-85) + `MayaHelpDetector` | 部分的（MEL は別パターン、Phase 5） |
| **Inspect Object 'X'** | line 43-45 → `editor.inspect_object.emit(X, "dir")` | **完全に Python 専用** |
| **Inspect Object Help 'X'** | line 47-49 → `editor.inspect_object.emit(X, "help")` | **完全に Python 専用** |
| **Reload Module 'X'** | line 51-54 → `_build_reload_code` (line 161-189) | **完全に Python 専用**（MEL に概念なし） |
| Add to Shelf | line 56-60 | profile 化済（commit 4） |

`ui/execution_manager.py:144-203` の `handle_object_inspection` が `dir(X)` / `help(X)` Python スニペットをハードコード。

`_is_valid_identifier` / `_is_valid_module_name` (line 140-158) は Python 識別子規則。

**MEL 等価**:
- `dir(X)` → `whatIs $X`（プロシージャ/コマンドの定義場所と種類）
- `help(X)` → `help X`（コマンドのフラグ一覧）
- `importlib.reload` → 概念なし。代わりに `source "path/to/file.mel"` でファイル再ソース

### 10.6 ヘルプポップアップ レンダラ（autocomplete の一部）

`ui/help/renderer/` は autocomplete のホバー / カーソル位置 docstring 表示で呼ばれるレンダラ。`popup.py` から `render_docstring(text)` 経由で使用。

| ファイル | Python 依存箇所 |
|---|---|
| `__init__.py:50-55` | `looks_like_maya_help` → `maya.render` 分岐は **言語非依存**（`cmds.help()` 出力は呼び出し言語によらず同形）→ MEL でもそのまま動く |
| `syntax.py` | 全体が Pygments `PythonLexer` のみ。シグネチャ着色（`blocks.py:79`）、コードブロック着色（`blocks.py:95`）、Maya help Examples 節着色（`maya.py:41`）で使用 |
| `structured.py` | `docstring_parser` で numpydoc / Google / RST を解析。MEL には docstring 概念がないため使用機会なし |
| `detect.py:32` | `SIGNATURE_RE = r"^\s*(?:def\s+)?([A-Za-z_][\w.]*)\s*\("` — Python の `def foo(...)` / `foo(...)` 前提。MEL の `global proc int foo(int $x)` には不適合 |
| `maya.py:41` | Examples 節を `highlight_python=True` で渡す。MEL 例は色が崩れるが cosmetic |

**Phase 0 ではここは触らない**。**Phase 4（MEL autocomplete）で対応**:
- MEL identifier 選択 → `cmds.help(name)` 出力なら `maya.py` 既存パスがそのまま動く
- ユーザー定義 `global proc` のヘルプは MEL 用シグネチャ抽出パス（`detect.py` に MEL `SIGNATURE_RE` を追加 or 別関数）が必要
- Pygments 標準に MELLexer は無し → シグネチャ着色は cosmetic として諦めるか、自前の MEL ハイライタを `syntax.py` に追加して切り替える
- `LanguageProfile` に `signature_highlighter: Optional[Callable]` を追加し、profile から取得する形が望ましい（Phase 4 で）

### 10.7 エディタクラス参照

- `ui/code_editor.py:36` — `class PythonEditor(QPlainTextEdit, ...)`
- `ui/code_editor.py:151` — placeholder `"# Start typing Python code..."`
- 11 ファイル / 29 箇所で参照（多くは `isinstance(editor, PythonEditor)`）
- `editor_tab_widget.py:389, 423, 430` などの `isinstance` 箇所は alias で吸収

### 10.8 アーキテクチャ案比較（採用済み: 案 B）

| 案 | 規模 | 得られる機能 | 欠点 |
|---|---|---|---|
| A. タブごとの `language` flag | 小 | 実行・保存・コメント・シェルフ | 分岐が散らばり 3 言語目で破綻 |
| **B. `LanguageProfile` データクラス** | 中（~15 ファイル / 300〜500 行） | フル多言語対応 | 実リファクタが必要 |
| C. エディタサブクラス分離 | 大 | クリーンな分離 | `isinstance` 大量書き換え |

---

**最終更新**: 2026-05-01（**commit 7 実装完了、コミット待ち**: コンテキストメニュー / Inspect を language profile 経由に — Python ヘルパを `languages/python.py` に集約）
