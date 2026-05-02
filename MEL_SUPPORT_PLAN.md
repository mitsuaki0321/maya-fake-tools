# Code Editor 多言語化 / MEL 対応 実装計画 & 進捗

> このドキュメントは、`scripts/faketools/tools/common/code_editor/` を Python 専用から多言語対応（まずは MEL）へ拡張するための計画と進捗を保持する作業用ファイルです。
> **新しい会話セッションで再開するときは、このファイルだけ読めば全体像と現在地が分かる** ことを目的としています。

---

## 0. 再開用クイックスタート（コンテキスト切れ時）

新しいセッションで作業を継続するときは、この順で読む:

1. このファイル全体（特に §6 Phase 1 と §7 決定ログ、§7.5 UI/UX 決定）
2. `scripts/faketools/tools/common/code_editor/languages/__init__.py`（`ALL_PROFILES` / `KNOWN_EXTENSIONS` の現在地）
3. `scripts/faketools/tools/common/code_editor/languages/python.py`（プロファイル組み立て例）
4. `scripts/faketools/tools/common/code_editor/languages/python_actions.py`（`context_menu_extender` 実装例 — MEL では Phase 1 では作らない）
5. `scripts/faketools/tools/common/code_editor/languages/types.py`（`LanguageProfile` / `ShelfConfig` の最新フィールド）
6. `scripts/faketools/tools/common/code_editor/command/execution.py`（実行ブリッジ、bridge per language キャッシュ）
7. CLAUDE.md の「Git Commit Rules」（**勝手にコミットしない**）

実装を再開する前に、**ユーザーに「`MEL_SUPPORT_PLAN.md` の進捗を確認しました。次は commit P1-X から進めますがよろしいですか？」と確認** すること。

### Phase 1 着手時の最初の commit（P1-1）の概要

`languages/mel.py` を新規作成し、`languages/__init__.py` の `ALL_PROFILES` に `MEL` を追加するだけ。MEL プロファイル本体:

```python
# languages/mel.py（Phase 1 で新設）
from .types import LanguageProfile, ShelfConfig

MEL = LanguageProfile(
    id="mel",
    display_name="MEL",
    extensions=(".mel",),
    default_extension=".mel",
    line_comment="//",
    source_type="mel",
    shelf_config=ShelfConfig(
        source_type="mel",
        label="MEL",
        icon="commandButton.png",
    ),
    # extra_indent_trigger / context_menu_extender / highlighter_factory /
    # completion_engine_factory / folding_strategy はすべて未指定（None）
)

__all__ = ["MEL"]
```

`languages/__init__.py`:
```python
from .mel import MEL    # 追加
from .python import PYTHON
...
ALL_PROFILES: tuple[LanguageProfile, ...] = (PYTHON, MEL)   # MEL を追加
```

これだけで `KNOWN_EXTENSIONS` が `{".py", ".mel"}` に自動拡張、`get_profile_for_path("foo.mel")` が MEL を返すようになり、消費側の既存ロジックが MEL を拾い始める。

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
| **0** | `LanguageProfile` 導入、`PythonEditor` → `CodeEditor` リネーム、Python 定数の集約。挙動は変えない | **完了**（2026-05-01 動作確認済） |
| **1** | `MEL` プロファイル追加。実行・保存・コメント・シェルフ・新規ファイル・placeholder を分岐 + open/restore 時の language 解決バグ修正 | **完了**（2026-05-02 動作確認済） |
| 2 | `mel_highlighter.py`（正規表現ステートマシン）+ `syntax_colors.json` キー追加 | 未着手 |
| 3 | ブレース折りたたみ戦略追加、`auto_indent` の汎用化 | 未着手 |
| 4 | `MelCompletionEngine`（`cmds.help` 経由）、`global proc` 静的パース | 未着手 |
| 5 | `MayaHelpDetector` の MEL パターン追加 | 未着手 |
| 6 | コンテキストメニュー（MEL `context_menu_extender` 実装、whatIs のみ。Source File は対象外） | 未着手 |
| 7 | 最終的な UI/UX 修正（ツールバー MEL ボタン専用アイコンデザイン、その他 Phase 1 後に発見された UI/UX 改善） | 未着手 |

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
    ├── types.py           # LanguageProfile, ShelfConfig（型定義のみ、循環インポート回避のため分離）
    ├── helpers.py         # cross-language ヘルパ（find_execution_manager 等）
    ├── python_actions.py  # Python のメニュー extender / inspection snippets / reload 実装
    └── python.py          # PYTHON profile の組み立てのみ（slim）
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
    """選択中テキストに対し言語固有メニュー項目を追加し、
    各項目のアクション実行（Inspect / Reload 等）まで一手に所有する。
    引数: (menu, editor, selected_text)。None なら追加項目なし。
    extender は無条件にメニュー項目を追加してよい — 実行側 (Inspect / Reload) の
    try/except が無効な選択にも graceful に対応するため、ここで識別子文法の
    バリデーションは不要。インスペクションコード生成・dispatch も extender 内部の
    実装詳細とし、別フィールド (旧 inspection_snippets) には分離しない。
    Python: Inspect Object / Inspect Help / Reload Module
    MEL:    whatIs / Source File（採用するかは Phase 1 着手時に再相談）"""

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

**Optional（8 項目、すべて `None` がデフォルト）** — `None` のとき該当機能を消費側で無効化:
| フィールド | None で無効化される機能 |
|---|---|
| `line_comment` | コメントトグル（`Ctrl+/`） |
| `extra_indent_trigger` | auto-indent の追加インデント発生条件（ブラケット系は既存の hanging indent で処理されるため不要） |
| `source_type` | Run / 実行関連すべて |
| `shelf_config` | "Add to Shelf" メニュー項目 |
| `context_menu_extender` | 言語固有右クリック項目 + 各項目のアクション実行（Inspect / Reload 等を一手に所有） |
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
    # context_menu_extender は commit 7 で設定（commit 12 で inspection も内包）
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
| 1 | `languages/` 新設、`LanguageProfile` / `ShelfConfig` / `PYTHON` 定義のみ（誰も使わない） | `languages/__init__.py`, `languages/types.py`, `languages/python.py` |
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
- [x] **commit 7**: Python 専用ヘルパ（`_is_valid_identifier` / `_is_valid_module_name` / `_reload_module` / `_build_reload_code` / `_find_execution_manager` / dir & help テンプレート）を `editor_context_menu.py` と `execution_manager.py` から `languages/python.py` に集約。新規 `_python_context_menu_extender(menu, editor, identifier)` と `_python_inspection_snippets(inspection_type, object_name)` を追加（Qt は extender 内部で遅延 import）。PYTHON プロファイルに `context_menu_extender` / `identifier_validator` / `inspection_snippets` を設定。`build_context_menu` を「validator → extender 呼出」のジェネリックフローに、`handle_object_inspection` を「ヘッダ表示 → `language.inspection_snippets` 経由でコード生成 → execute」に置換。ruff PASS、smoke test PASS（profile fields / validator / snippets / Qt 非依存維持） _(hash: `1fead95`)_
- [x] **commit 8**: `code_editor/__init__.py` の package docstring と `TOOL_CONFIG.description` を Python 限定から多言語化前提の文言に更新（"Multi-language code editor ..."）。`ui/code_editor.py` の placeholder text "# Start typing Python code..." は §4.4 に従い据え置き（Phase 0 スコープ外）。Phase 0 全体で `ruff check` クリーン、最終 smoke test PASS（全 profile フィールド・autoderived properties・全 consumer module の Qt 非依存 import） _(hash: `e684ff6`)_
- [x] **Phase 0 動作確認**: ユーザー確認済み（2026-05-01）。Maya 上で既存挙動の回帰なし
- [x] **commit 9**: `LanguageProfile.identifier_validator` フィールドを削除。`languages/python.py` から `_is_valid_identifier` / `_is_valid_module_name` を削除し、`_python_context_menu_extender` は Reload Module を **常に** 追加（実行側の try/except が無効識別子を graceful に処理するため、文法バリデーションを extender 側でゲートしない方針）。`editor_context_menu.build_context_menu` から validator チェックを削除（選択語非空ガードのみ残す）。プロファイル API スリム化（11 → 10 Optional）。ruff PASS、smoke test PASS _(hash: `cc797f7`)_
- [x] **commit 10**: デッドコード削除。`ExecutionManager.handle_object_inspection` 内の `"Syntax Errors:"` 分岐（emit する側が存在せず到達不可）と `MayaCodeEditor.show_syntax_errors_in_terminal()` メソッド（呼出元なし）を削除。`inspect_object` シグナルが純粋に inspection 用途のみとなる _(hash: `604a5e5`)_
- [x] **types.py リネーム**: `_types.py` → `types.py`（プロジェクト多数派の慣習に揃える、`_` プレフィックスなし）_(hash: `af7d8bc`)_
- [x] **commit 11**: ファイル分割（振る舞い不変）。`languages/helpers.py` を新設し `find_execution_manager` を移動（cross-language ヘルパとして将来 MEL でも再利用）。`languages/python_actions.py` を新設し `_PYTHON_DIR_TEMPLATE` / `_PYTHON_HELP_TEMPLATE` / `_build_reload_code` / `_reload_module` / `_python_inspection_snippets` / `_python_context_menu_extender` を全部移動。`languages/python.py` は 210 行 → 50 行に slim 化（PYTHON 組み立て + extra_indent_trigger + highlighter_factory のみ）。cross-module 参照される関数は `_` プレフィックスを外す（`python_context_menu_extender` / `python_inspection_snippets` / `find_execution_manager`）。ruff PASS、smoke test PASS _(hash: `9307c59`)_
- [x] **commit 12**: コンテキストメニューと inspection を統合。`helpers.py` に `dispatch_inspection(editor, header, code)` を追加（cross-language ヘルパ）。`python_actions.py` に `python_inspect_dir` / `python_inspect_help` ファサードを追加し `dispatch_inspection` 経由で実行、`_reload_module` も同ヘルパ経由にリファクタ（`hasattr` フォールバック撤廃）。`python_context_menu_extender` の lambda がシグナル経由ではなく直接ファサードを呼ぶように変更。`LanguageProfile.inspection_snippets` フィールド削除（10 → 9 Optional）。`python_inspection_snippets` 関数削除。`code_editor.py` / `editor_tab_widget.py` から `inspect_object` シグナル定義 + 4 connect 削除、`ui_layout_manager.py` から該当 connect 削除、`execution_manager.handle_object_inspection` メソッド削除。シグナル経路 4 ホップを直接呼出 1 ホップに圧縮。ruff PASS、smoke test PASS _(hash: `4179139`)_

### Phase 1（commit 粒度確定済、実装着手準備完了）

- [x] **着手前確認**: MEL に含める機能セットをユーザーと確定（§7 決定ログ参照）
- [x] **着手前確認**: UI/UX 方針をユーザーと確定（§7.5 参照）
- [x] **commit P1-1**: `MEL` プロファイル追加 — `languages/mel.py` 新設（最小骨格、機能セットは §7 確定通り `id` / `display_name` / `extensions` / `default_extension` / `line_comment="//"` / `block_comment=("/*", "*/")` / `source_type="mel"` / `shelf_config` のみ、それ以外の Optional フィールドはすべて `None`）、`languages/__init__.py` に `MEL` import 追加 + `ALL_PROFILES = (PYTHON, MEL)` + `__all__` に `"MEL"` 追加。`KNOWN_EXTENSIONS` が `{".py", ".mel"}` に自動拡張。ruff PASS、smoke test PASS（profile フィールド / `file_filter` / `line_comment_with_space` / `get_profile_for_path` 解決を確認）。Maya 上の動作確認は P1-2/P1-3 で UI が整ってからまとめて実施 _(hash: `ef84050`)_
- [x] **commit P1-2**: 新規ファイル UI を並列化 — `file_explorer.show_context_menu` の "New X File" を `ALL_PROFILES` 反復で並列メニュー化（`create_new_file` に `language: LanguageProfile = DEFAULT_PROFILE` 引数追加）。`file_operations_controller.new_file` も `language` 引数受取に変更（タイトル / 拡張子は profile 経由）。`toolbar.py` の単一 `new_button` を `new_buttons: dict[str, VSCodeButton]` に分解、`ALL_PROFILES` 反復で並列ボタン生成、`new_clicked = Signal(object)` 化（profile を運ぶ）、Ctrl+N ヒントは DEFAULT_PROFILE のボタンのみ。MEL ボタンアイコンは Python 用 (`new`) を暫定流用。`ui_layout_manager.connect_signals` は `signal.connect(file_ops.new_file)` のままで動作（Signal(object) → 第一位置引数 language）。ruff PASS、smoke test PASS（AST parse + 反復生成される menu/button 文字列の確認） _(hash: `fab0f82`)_
- [x] **commit P1-3**: placeholder text を profile 駆動に — `code_editor.py:init_editor` のハードコード `"# Start typing Python code..."` を `editor.language.line_comment_with_space` + `display_name` から動的生成に。`line_comment is None` ならプレフィックスなしフォールバック。ruff PASS、smoke test PASS（PYTHON / MEL / line_comment=None の 3 パターン）。**ただし P1-4 のバグにより MEL タブの editor.language が PYTHON のままなので、Maya 上の見た目は P1-4 完了まで Python のまま** _(hash: `03cd0e1`)_
- [x] **commit P1-4**: ファイル open / セッション復元時に editor.language を解決するバグ修正（**Phase 0 リファクタの取りこぼし**、Phase 1 で MEL 実装後に Maya 動作確認時点で顕在化、2026-05-02 ユーザー報告）。`code_editor.py` に `set_language(language)` メソッド新設（`self.language` 更新 + `setup_syntax_highlighting()` 再呼出 + `_apply_placeholder_text()` 再呼出）と `_apply_placeholder_text()` ヘルパ抽出（`init_editor` と `set_language` の DRY）。`load_file` で `get_profile_for_path(file_path)` から language を解決、現状と異なれば `set_language()` 呼出。`ui_session_manager.restore_tab` で `new_file(language=get_profile_for_path(file_path))` を渡す。これで `open_file_permanent` / `open_file_preview`（新規 / 既存 preview 再利用 両方）/ "New MEL File" 経由 / セッション復元 のすべてが正しい language にバインドされる。ruff PASS、smoke test PASS _(hash: `f51bf84`)_
- [x] **Phase 1 動作確認**: ユーザー確認済み（2026-05-02）。`.mel` の open / 新規作成 / placeholder / コメントトグル / Run / Add to Shelf / file_explorer Run / Python 側回帰なし、すべて問題なし

### Phase 1 後の follow-up（このフェーズ内で対応 / 別フェーズに移管）
- [x] **このフェーズ内で対応**: MEL ブロックコメント `/* */` のネスト破綻対策 — **block_comment フィールド自体を削除**（line comment トグルだけで十分とユーザー判断 2026-05-02）。`LanguageProfile.block_comment` / MEL の `block_comment=("/*", "*/")` / Python 側の関連コメントを撤去。Optional フィールド数 9 → 8
- **Phase 6 へ移管**: MEL 用 `context_menu_extender`（whatIs のみ、Source File は対象外）
- **Phase 7 へ移管**: ツールバー MEL ボタンの専用アイコンデザイン
- **不要判断**: ファイルエクスプローラの `.mel` アイコン（現状の自動表示で問題なし、ユーザー判断 2026-05-02）
- **保留**（任意 / 別の機会に検討）: `extra_indent_trigger` のリネーム検討（`indent_on_enter` 等への変更、§7 決定ログでユーザー指摘済）

### Phase 2（MEL シンタックスハイライト）
未着手（Phase 1 完了後に詳細化）

事前メモ:
- `highlighting/mel_highlighter.py` 新設、`MelHighlighter(QSyntaxHighlighter)` クラス（正規表現ステートマシン）
- `themes/syntax_colors.json` に MEL 固有トークン（`flag` / `variable_dollar` 等）を追加
- `languages/mel.py` の `MEL.highlighter_factory = _mel_highlighter_factory`（遅延 import）
- `syntax_config_loader.py` は無変更（既に汎用）

### Phase 3 以降
未着手

#### Phase 3 で対応する auto_indent 汎用化（事前メモ）
- `auto_indent.py:163` の Rule 3（`endswith(":")` ハードコード）を `language.extra_indent_trigger(stripped)` 経由に
- コメント除外（`startswith("#")`）も `language.line_comment` 経由に汎化
- `_python_extra_indent_trigger` 述語の中身も同タイミングで見直し
- フィールド名 `extra_indent_trigger` → `indent_on_enter` 等にリネーム検討（§7 決定ログ）
- ブレース折りたたみ戦略追加（`folding_strategy` field）

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
| 2026-05-01 | `identifier_validator` フィールドを削除（commit 9） | コンテキストメニュー extender の責務をシンプルに保ち、文法チェックは実行側 (Inspect / Reload の try/except) に集約する方針。Python 識別子規則・MEL の `$var` 規則などを各言語が個別に書く必要がなくなる。ユーザーが無効識別子を Inspect/Reload しても terminal に親切なエラーが出るだけで graceful。プロファイル API が 11 → 10 Optional にスリム化 |
| 2026-05-01 | `inspection_snippets` フィールドを削除し extender に統合（commit 12） | `context_menu_extender` と `inspection_snippets` は同じ言語固有機能（右クリックアクション）を 2 フィールドに分離していた。原因は editor → execution_manager 間のシグナル経路。直接呼出に切替えれば 1 フィールドで済む。シグナル 4 ホップを 1 ホップに、`handle_object_inspection` を撤廃、API が 10 → 9 Optional にさらにスリム化。MEL extender 実装時に「メニュー定義 + アクションコード」が 1 ファイル内で完結する見通しも良くなる |
| 2026-05-01 | `LanguageProfile` を全 Optional 設計に再構成 | §1.5 opt-in 原則と整合。必須は `id` / `display_name` / `extensions` / `default_extension` の 4 項目のみ。`file_filter` と `line_comment_with_space` は自動生成プロパティ化。`shelf_*` 3 フィールドは `ShelfConfig` データクラスに集約しまるごと Optional 化 |
| 2026-05-01 | `block_open_chars: tuple[str, ...]` を `extra_indent_trigger: Callable[[str], bool]` に変更 | `auto_indent.py` の hanging indent 規則は既に `(`, `[`, `{` の未閉じを処理するため、ブラケット系言語（MEL 等）には追加トリガが不要。`block_open_chars` が必要なのは事実上 Python の `:` だけ。Callable 化で将来コメント除去・トークン解析等の複雑な条件にも拡張可能。MEL は `None` で済み、hanging indent と closing bracket alignment で完全カバー |
| 2026-05-01 | `line_comment` / `block_comment` は文字列ベースのまま維持（Callable 化しない） | コメントトグルは「行頭プレフィックスの追加 / 除去」のみで、インデント判定のような行内コンテキスト解析を必要としない。Python / MEL とも単一文字列で完全表現可。複数形式が必要になれば後方互換的に `tuple[str, ...]` 化可能。Python の `"""..."""` を `block_comment` に入れない（文字列リテラルでコメントではない、linter 警告の原因）ため Python は `block_comment=None`（**追記 2026-05-02: `block_comment` フィールド自体を後日撤去**）|
| 2026-05-01 | 型定義を `types.py` に分離 | 当初 `__init__.py` に `LanguageProfile` / `ShelfConfig` を直接定義する計画だったが、`from .python import PYTHON` を classes 定義の後に置くと ruff E402（module-level import not at top）が発生。`types.py` を分離することで `__init__.py` を純粋な再エクスポート + ファクトリ関数のみに保てる（プロジェクト多数派に揃え `_` プレフィックスは付けない方針） |
| 2026-05-01 | ファイルエクスプローラ Run でアクティブタブの language を使うバグを修正 | `execute_file_directly` がファイル拡張子から profile を解決し `execute_code(content, language=...)` 経由で正しい bridge を選ぶように。`execute_code` / `_execute_code_internal` / `_refresh_active_bridge` に `language_override` 引数を追加。Phase 0 では Python のみのため顕在化しないが、Phase 1 で MEL ファイルを Python タブから実行する経路が確実に踏むバグ |
| 2026-05-01 | `execute_python_code` を `execute_with_echo` にリネーム | Phase 0 リファクタの取りこぼし。実体は active editor の language でディスパッチする言語非依存メソッドだが、名前が "python" を残していて誤読の元。`shortcut_handler` の 3 箇所も合わせて切替 |
| 2026-05-01 | **Phase 1 の MEL 機能セットを「最小実用」で確定** | Phase 1 では `id` / `display_name` / `extensions` / `default_extension` / `line_comment="//"` / `block_comment=("/*", "*/")` / `source_type="mel"` / `shelf_config` のみ設定。`extra_indent_trigger`（`{` は Rule 1 で処理）/ `context_menu_extender`（後フェーズ）/ `highlighter_factory`（Phase 2）/ `completion_engine_factory`（将来 Phase 4）/ `folding_strategy`（将来 Phase 3）はすべて `None`。最小骨格 + 動作確認に集中することで Phase 1 リリースのリスクを下げる |
| 2026-05-01 | MEL の `context_menu_extender` は **whatIs のみ実装**（Source File は不要） | ユーザー判断。実装タイミングは Phase 1 完了後（Phase 1.5 や Phase 2 と一緒に追加可能） |
| 2026-05-01 | MEL シェルフアイコンは `"commandButton.png"` | Maya 標準で言語非依存の汎用アイコン。`pythonFamily.png` を流用すると視覚的に混乱する |
| 2026-05-01 | 新規ファイル UI は並列メニュー / 並列ボタンで実装 | ファイルエクスプローラ右クリック・ツールバー両方で「New Python File」「New MEL File」を並列。`ALL_PROFILES` を反復して自動生成（言語追加時の拡張性） |
| 2026-05-01 | ツールバーの MEL 用 New File ボタンアイコンは Phase 1 では Python 用と同じアイコンを流用 | 視覚デザインは Phase 1 後に再検討（UI/UX 議論として独立） |
| 2026-05-01 | placeholder text を profile 駆動に変更（Phase 1 で対応） | Phase 0 §4.4 では「触らない」としていたが、Phase 1 で MEL タブが "# Start typing Python code..." と表示されると明確に誤りになるため、`f"{line_comment_with_space}Start typing {display_name} code..."` で動的生成 |
| 2026-05-02 | ファイル open / セッション復元時の editor.language 解決バグを **Phase 1 動作確認の前に P1-4 として修正** | Phase 0 リファクタの取りこぼし（§6 P1-4 参照）。Phase 1 動作確認の前提（`.mel` を開けば MEL bridge で実行される）が成り立たないため、commit 順序を「P1-2 → P1-3 → **P1-4（バグ修正）** → 動作確認」に確定。P1-2 / P1-3 を先に進めるのは plan の commit 順序を尊重する判断 |
| 2026-05-02 | Phase 1 後 follow-up を再編 — **Phase 6 = コンテキストメニュー実装** / **Phase 7 = 最終的な UI/UX 修正** を新設 | Phase 1 follow-up に並んでいた「MEL `context_menu_extender`」「ツールバー MEL ボタン専用アイコン」を、それぞれ独立フェーズに格上げ（コンテキストメニュー側は将来 Python の whatIs 等価機能や Inspect 系の汎化が絡む可能性があり Phase 単位で扱った方が見通しが良い、UI/UX は Phase 1 完了後に他の改善とまとめて議論できる方が良い）。`.mel` ファイルアイコンは現状の自動表示で問題ないとユーザー判断（不要扱い）。Phase 1 内で残した follow-up は `/* */` ネスト破綻対策のみ |
| 2026-05-02 | **`block_comment` フィールド自体を削除**（ブロックコメントトグル機能は実装しない） | `block_comment` プロファイルフィールドはあったが消費側ゼロ、ショートカットも未実装。`/* */` ネスト破綻の対策を入れる前にトグル本体の実装範囲を相談したところ、ユーザー判断で「現在の line comment トグル（`Ctrl+/`）で十分、ブロックコメントトグル機能自体不要」となった。`LanguageProfile.block_comment` / MEL の `block_comment=("/*", "*/")` / Python 側の説明コメントを撤去。Optional フィールド数 9 → 8。§8 の MEL `/* */` ネスト破綻エントリも撤去（実装しない以上の対策不要） |

## 7.5 UI/UX 決定事項（Phase 1 着手前に確定）

| 項目 | 決定 |
|---|---|
| **タブヘッダーでの言語表示** | 何も追加表示しない。拡張子で判別可能。視覚デザイン議論時に再検討 |
| **ステータスバー / ウィンドウタイトル** | 何も追加表示しない（同上） |
| **ツールバー Run / Add to Shelf** | 共通ボタン（active editor の language で動的にディスパッチ済、Phase 0 で実装完了） |
| **新規ファイル UI（ファイルエクスプローラ右クリック）** | 並列メニュー: "New Python File" / "New MEL File" を並べる。`ALL_PROFILES` を反復して自動生成すれば将来言語追加時に自動拡張 |
| **新規ファイル UI（ツールバー）** | 並列ボタン: 言語ごとに 1 ボタン。Phase 1 では暫定で **Python と同じアイコン**を MEL ボタンにも流用（視覚デザインは後で再検討） |
| **新規ファイルダイアログ文言** | 選択された profile の `display_name` / `default_extension` を使用（既存実装で対応済） |
| **ファイルエクスプローラのアイコン** | 既存の `_FILE_EXTENSION_ICONS` に `"mel": "file"` 等を追加（仮）、視覚デザイン議論時に再検討 |
| **コンテキストメニューの言語固有項目位置** | extender が `menu.addSeparator()` の後に追加（既存実装通り） |
| **autocomplete / 折りたたみ無効言語のキーバインド** | graceful no-op（既に Phase 0 / commit 6 で実装済） |
| **placeholder text** | profile から自動生成（`f"{line_comment_with_space}Start typing {display_name} code..."`）。MEL タブは `"// Start typing MEL code..."` |

## 8. 未解決事項

- `cmds.help("-list", "*")` のレスポンスサイズと速度（Phase 4 のキャッシュ戦略に影響）
- ユーザ定義 `global proc` の列挙 API は存在しない → 開いているファイルの静的パースに留める方針
- `cmdScrollFieldExecuter(sourceType="mel")` の選択範囲実行のセマンティクス（`;` 区切りで Python と挙動が微妙に違う可能性、要スモークテスト）
- 同一タブ内で Python/MEL 混在は **不可**（プロファイルはタブ単位）
- stdout キャプチャは Maya のレポーターを共有する現アーキで透過のはずだが要確認
- ヘルプポップアップ syntax renderer（`renderer/syntax.py`）の Pygments `PythonLexer` は MEL 例にも当たる → cosmetic、deprioritize
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

**最終更新**: 2026-05-02（**Phase 1 完了 + ロードマップ再編 + `block_comment` フィールド撤去**。Phase 6（コンテキストメニュー）/ Phase 7（最終 UI/UX 修正）を新設。block comment toggle 自体は実装しない方針となり、`LanguageProfile.block_comment` / MEL の `block_comment=("/*", "*/")` を削除（Optional 9 → 8）、§8 の `/* */` ネスト破綻エントリも撤去。Phase 1 follow-up はすべて消化済。次フェーズはユーザー判断、候補は Phase 2 から 7 のいずれか）
