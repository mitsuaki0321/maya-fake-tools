"""
FakeTools Documentation Build Script

Builds HTML documentation from Markdown sources using Pandoc.
Integrates with ToolRegistry to automatically generate tool listings.
"""

import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Optional

import yaml


class DocBuilder:
    """Documentation builder for FakeTools."""

    def __init__(self, docs_root: Path):
        """
        Initialize the documentation builder.

        Args:
            docs_root: Root directory of the docs system
        """
        self.docs_root = docs_root
        self.src_dir = docs_root / "src"
        self.output_dir = docs_root / "output"
        self.templates_dir = docs_root / "templates"
        self.css_dir = docs_root / "css"
        self.js_dir = docs_root / "js"
        self.images_dir = docs_root / "images"

        # Load configuration
        config_path = docs_root / "config.yaml"
        with open(config_path, encoding="utf-8") as f:
            self.config = yaml.safe_load(f)

        # Load tool information from ToolRegistry
        self.tools_info = self._load_tools_info()

        # Search index cache (populated during build)
        self._search_indices: dict[str, str] = {}

        # Navigation data cache (populated during build)
        self._nav_data: dict[str, list[dict]] = {}
        self._nav_json: dict[str, str] = {}

        # Page order cache for prev/next links (populated during build)
        self._page_order: dict[str, dict[str, dict]] = {}

    def _load_tools_info(self) -> dict:
        """
        Load all tools information from ToolRegistry.

        Returns:
            dict: Tools organized by category
        """
        # Add project root to Python path
        project_root = self.docs_root.parent
        scripts_path = project_root / "scripts"
        if str(scripts_path) not in sys.path:
            sys.path.insert(0, str(scripts_path))

        try:
            from faketools.core.registry import get_registry

            registry = get_registry()
            registry.discover_tools()

            tools_by_category = {}
            for category in registry.get_all_categories():
                tools = registry.get_tools_by_category(category)
                tools_by_category[category] = tools

            return tools_by_category
        except ImportError as e:
            print(f"Warning: Could not load ToolRegistry: {e}")
            print("Tool information will not be available.")
            return {}

    def check_pandoc(self) -> bool:
        """
        Check if Pandoc is installed.

        Returns:
            bool: True if Pandoc is available
        """
        try:
            result = subprocess.run(["pandoc", "--version"], capture_output=True, text=True)
            return result.returncode == 0
        except FileNotFoundError:
            return False

    def clean_output(self):
        """Clean the output directory."""
        if self.output_dir.exists():
            shutil.rmtree(self.output_dir)
        self.output_dir.mkdir(parents=True)
        print(f"Cleaned output directory: {self.output_dir}")

    def copy_assets(self):
        """Copy CSS, JS, and common images to output directory."""
        # Copy CSS
        output_css = self.output_dir / "css"
        if self.css_dir.exists():
            shutil.copytree(self.css_dir, output_css, dirs_exist_ok=True)
            print(f"Copied CSS files to {output_css}")

        # Copy JS
        output_js = self.output_dir / "js"
        if self.js_dir.exists():
            shutil.copytree(self.js_dir, output_js, dirs_exist_ok=True)
            print(f"Copied JS files to {output_js}")

        # Copy common images from docs/images
        output_images = self.output_dir / "images"
        if self.images_dir.exists():
            shutil.copytree(self.images_dir, output_images, dirs_exist_ok=True)
            print(f"Copied common images to {output_images}")

        # Copy common images from docs/src/images
        src_images_dir = self.src_dir / "images"
        if src_images_dir.exists():
            shutil.copytree(src_images_dir, output_images, dirs_exist_ok=True)
            print(f"Copied source images to {output_images}")

    def get_relative_path(self, from_path: Path, to_path: Path) -> str:
        """
        Calculate relative path from one file to another.

        Args:
            from_path: Source file path
            to_path: Target file path

        Returns:
            str: Relative path
        """
        try:
            rel_path = Path(to_path).relative_to(from_path.parent)
            return str(rel_path).replace("\\", "/")
        except ValueError:
            # If relative_to fails, calculate manually
            from_parts = from_path.parent.parts
            to_parts = to_path.parts

            # Find common prefix
            common_length = 0
            for i, (a, b) in enumerate(zip(from_parts, to_parts)):
                if a == b:
                    common_length = i + 1
                else:
                    break

            # Calculate ups (..) and remaining path
            ups = len(from_parts) - common_length
            remaining = to_parts[common_length:]

            if ups == 0:
                result = "/".join(remaining)
            else:
                result = "/".join([".."] * ups + list(remaining))

            return result

    def calculate_root_path(self, output_file: Path) -> str:
        """
        Calculate relative path from output file to output root.

        Args:
            output_file: Output HTML file path

        Returns:
            str: Relative path to root (ends with /)
        """
        rel_path = self.get_relative_path(output_file, self.output_dir)
        if rel_path == ".":
            return ""
        # Count directory levels
        level = len(output_file.relative_to(self.output_dir).parent.parts)
        if level == 0:
            return ""
        return "../" * level

    def parse_front_matter(self, md_file: Path) -> tuple[dict, str]:
        """
        Parse YAML front matter from markdown file.

        Args:
            md_file: Markdown file path

        Returns:
            tuple: (metadata dict, content without front matter)
        """
        with open(md_file, encoding="utf-8") as f:
            content = f.read()

        if not content.startswith("---"):
            return {}, content

        # Find end of front matter
        try:
            _, yaml_str, md_content = content.split("---", 2)
            metadata = yaml.safe_load(yaml_str)
            return metadata or {}, md_content.strip()
        except ValueError:
            return {}, content

    def find_lang_pair(self, md_file: Path, current_lang: str) -> Optional[Path]:
        """
        Find corresponding file in other language.

        Args:
            md_file: Current markdown file
            current_lang: Current language code

        Returns:
            Path | None: Corresponding file in other language
        """
        # Get lang-ref from metadata
        metadata, _ = self.parse_front_matter(md_file)
        lang_ref = metadata.get("lang-ref")

        if not lang_ref:
            return None

        # Find other language
        other_lang = "en" if current_lang == "ja" else "ja"

        # Calculate relative path within language directory
        lang_dir = self.src_dir / current_lang
        rel_path = md_file.relative_to(lang_dir)

        # Look for file with same relative path in other language
        other_file = self.src_dir / other_lang / rel_path

        if other_file.exists():
            other_metadata, _ = self.parse_front_matter(other_file)
            if other_metadata.get("lang-ref") == lang_ref:
                return other_file

        return None

    def convert_markdown(self, md_file: Path, output_file: Path, lang: str):
        """
        Convert markdown file to HTML using Pandoc.

        Args:
            md_file: Source markdown file
            output_file: Output HTML file
            lang: Language code
        """
        # Parse front matter
        metadata, content = self.parse_front_matter(md_file)

        # Calculate paths
        root_path = self.calculate_root_path(output_file)

        # Find language pair
        lang_pair = self.find_lang_pair(md_file, lang)
        lang_link = ""
        lang_link_text = ""

        if lang_pair:
            # Calculate output path for language pair
            lang_pair_lang = "en" if lang == "ja" else "ja"
            lang_pair_rel = lang_pair.relative_to(self.src_dir / lang_pair_lang)
            lang_pair_output = self.output_dir / lang_pair_lang / lang_pair_rel.with_suffix(".html")
            lang_link = self.get_relative_path(output_file, lang_pair_output)
            lang_link_text = "English" if lang == "ja" else "日本語"

        # Build breadcrumb
        breadcrumb = self.build_breadcrumb(md_file, lang, metadata)

        # Prepare template variables
        home_text = "ホーム" if lang == "ja" else "Home"
        home_link = "index.html" if lang == "ja" else "index_en.html"
        template_vars = {
            "lang": lang,
            "title": metadata.get("title", ""),
            "description": metadata.get("description", ""),
            "root_path": root_path,
            "project_name": self.config["project"]["name" if lang == "ja" else "name_en"],
            "home_text": home_text,
            "home_link": home_link,
            "toc_title": "目次" if lang == "ja" else "Table of Contents",
            "lang_link": lang_link,
            "lang_link_text": lang_link_text,
        }

        # Add breadcrumb HTML if available
        if breadcrumb:
            breadcrumb_html = self.render_breadcrumb_html(breadcrumb, root_path, home_link, home_text)
            template_vars["breadcrumb_html"] = breadcrumb_html

        # Note: search_index_script and nav_data_script are injected post-Pandoc
        # to avoid Windows command-line length limits

        # Add current tool/category info for sidebar highlighting
        lang_dir = self.src_dir / lang
        try:
            rel_path = md_file.relative_to(lang_dir)
            if len(rel_path.parts) > 1:
                template_vars["current_category"] = rel_path.parts[0]
                template_vars["current_tool"] = md_file.stem

                # Add prev/next navigation links
                page_key = f"{rel_path.parts[0]}/{md_file.stem}"
                nav_info = self._page_order.get(lang, {}).get(page_key, {})
                if nav_info:
                    template_vars["has_page_nav"] = "true"
                    if "prev_title" in nav_info:
                        template_vars["prev_title"] = nav_info["prev_title"]
                        template_vars["prev_link"] = nav_info["prev_link"]
                    if "next_title" in nav_info:
                        template_vars["next_title"] = nav_info["next_title"]
                        template_vars["next_link"] = nav_info["next_link"]
        except ValueError:
            pass

        # Write content to temp file (without front matter)
        temp_md = md_file.with_suffix(".tmp.md")
        temp_md.write_text(content, encoding="utf-8")

        try:
            # Build Pandoc command
            cmd = [
                "pandoc",
                str(temp_md),
                "-o",
                str(output_file),
                "--template",
                str(self.templates_dir / "page.html"),
                "--no-highlight",
                "--toc",
                "--toc-depth=3",
                "-f",
                "markdown-implicit_figures",
            ]

            # Add metadata as Pandoc variables
            for key, value in template_vars.items():
                if isinstance(value, list):
                    # Skip lists for now
                    continue
                cmd.extend(["-V", f"{key}={value}"])

            # Run Pandoc
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode != 0:
                print(f"Error converting {md_file}:")
                print(result.stderr)
            else:
                # Post-process: inject inline scripts that are too large for -V flags
                self._inject_inline_scripts(output_file, lang)
                print(f"Converted: {md_file} -> {output_file}")

        finally:
            # Clean up temporary files
            if temp_md.exists():
                temp_md.unlink()

    def _inject_inline_scripts(self, output_file: Path, lang: str):
        """
        Inject inline data scripts into generated HTML file.

        Replaces template placeholders with actual script tags to avoid
        Windows command-line length limits when passing large data via Pandoc -V flags.

        Args:
            output_file: Generated HTML file
            lang: Language code
        """
        html = output_file.read_text(encoding="utf-8")

        scripts = []
        if lang in self._nav_json:
            scripts.append(f"<script>window.__NAV_DATA__={self._nav_json[lang]};</script>")
        if lang in self._search_indices:
            scripts.append(f"<script>window.__SEARCH_INDEX__={self._search_indices[lang]};</script>")

        if scripts:
            injection = "\n    ".join(scripts)
            # Inject before main.js script tag
            html = html.replace('<script src="', f'{injection}\n    <script src="', 1)
            output_file.write_text(html, encoding="utf-8")

    def substitute_template_vars(self, template: str, vars: dict) -> str:
        """
        Simple template variable substitution.

        Args:
            template: Template string
            vars: Variables to substitute

        Returns:
            str: Substituted string
        """
        result = template
        for key, value in vars.items():
            if isinstance(value, (str, int, float)):
                result = result.replace(f"${key}$", str(value))
        return result

    def build_breadcrumb(self, md_file: Path, lang: str, metadata: dict) -> list[dict]:
        """
        Build breadcrumb navigation.

        Args:
            md_file: Markdown file
            lang: Language code
            metadata: File metadata

        Returns:
            list: Breadcrumb items
        """
        breadcrumb = []

        # Get relative path from language root
        lang_dir = self.src_dir / lang
        try:
            rel_path = md_file.relative_to(lang_dir)
        except ValueError:
            return breadcrumb

        parts = rel_path.parts

        # Skip if it's index.md at root
        if len(parts) == 1 and parts[0] == "index.md":
            return breadcrumb

        # Add category if file is in a category subdirectory
        if len(parts) > 1:
            category_id = parts[0]
            # Find category name from config
            category_name = category_id
            for cat in self.config["categories"]:
                if cat["id"] == category_id:
                    category_name = cat["name_ja"] if lang == "ja" else cat["name_en"]
                    break

            breadcrumb.append({"text": category_name, "url": None, "active": False})

        # Add parent page link if specified (for sub-pages)
        parent = metadata.get("parent")
        if parent:
            parent_title = metadata.get("parent_title", parent)
            parent_url = f"{parent}.html"
            breadcrumb.append({"text": parent_title, "url": parent_url, "active": False})

        # Add current page (no link, marked as active)
        page_title = metadata.get("title", md_file.stem)
        breadcrumb.append({"text": page_title, "url": None, "active": True})

        return breadcrumb

    def render_breadcrumb_html(self, breadcrumb: list[dict], root_path: str, home_link: str, home_text: str) -> str:
        """
        Render breadcrumb navigation as HTML string.

        Args:
            breadcrumb: Breadcrumb items
            root_path: Relative path to root
            home_link: Home page link
            home_text: Home link text

        Returns:
            str: HTML string for breadcrumb
        """
        html_parts = ['<nav class="breadcrumb" aria-label="breadcrumb">', "    <ol>"]
        html_parts.append(f'        <li><a href="{root_path}{home_link}">{home_text}</a></li>')

        for item in breadcrumb:
            if item.get("active"):
                html_parts.append(f'        <li class="active">{item["text"]}</li>')
            elif item.get("url"):
                html_parts.append(f'        <li><a href="{item["url"]}">{item["text"]}</a></li>')
            else:
                html_parts.append(f"        <li>{item['text']}</li>")

        html_parts.append("    </ol>")
        html_parts.append("</nav>")

        return "\n".join(html_parts)

    def copy_images_for_file(self, md_file: Path, output_file: Path, lang: str):
        """
        Copy images for a specific markdown file.

        Args:
            md_file: Source markdown file
            output_file: Output HTML file
            lang: Language code
        """
        # Determine image source directory
        lang_dir = self.src_dir / lang
        images_src = lang_dir / "images"

        # Determine image output directory
        lang_output = self.output_dir / lang
        images_dst = lang_output / "images"

        # Copy all images from language-specific images directory
        if images_src.exists():
            shutil.copytree(images_src, images_dst, dirs_exist_ok=True)

    def process_markdown_files(self):
        """Process all markdown files in src directory."""
        for lang_code in ["ja", "en"]:
            lang_dir = self.src_dir / lang_code
            if not lang_dir.exists():
                print(f"Warning: Language directory not found: {lang_dir}")
                continue

            # Find all markdown files
            md_files = list(lang_dir.rglob("*.md"))

            for md_file in md_files:
                # Calculate output path
                rel_path = md_file.relative_to(lang_dir)
                output_file = self.output_dir / lang_code / rel_path.with_suffix(".html")

                # Create output directory
                output_file.parent.mkdir(parents=True, exist_ok=True)

                # Convert markdown to HTML
                self.convert_markdown(md_file, output_file, lang_code)

                # Copy images
                self.copy_images_for_file(md_file, output_file, lang_code)

    def generate_index_pages(self):
        """Generate index.html pages for all languages."""
        for lang_config in self.config["languages"]:
            lang_code = lang_config["code"]
            self.generate_index_page(lang_code)

    def _collect_tools_from_markdown(self, lang: str, cat_id: str) -> list[dict]:
        """
        Collect tool information from markdown files in a category.

        Args:
            lang: Language code
            cat_id: Category ID

        Returns:
            list[dict]: List of tool information (sorted by order field)
        """
        tools_data = []
        cat_dir = self.src_dir / lang / cat_id

        if not cat_dir.exists():
            return tools_data

        # Find all markdown files in category (excluding index.md)
        md_files = [f for f in cat_dir.glob("*.md") if f.stem != "index"]

        for md_file in md_files:
            metadata, _ = self.parse_front_matter(md_file)

            # Skip hidden pages (sub-pages)
            if metadata.get("hidden"):
                continue

            tool_name = metadata.get("title", md_file.stem)
            tool_description = metadata.get("description", "")
            order = metadata.get("order", 100)  # Default order: 100

            tools_data.append(
                {
                    "name": tool_name,
                    "description": tool_description,
                    "version": "",
                    "url": f"{lang}/{cat_id}/{md_file.stem}.html",
                    "has_doc": True,
                    "order": order,
                }
            )

        # Sort by order (ascending), then by name (alphabetically)
        tools_data.sort(key=lambda t: (t["order"], t["name"]))

        return tools_data

    def generate_index_page(self, lang: str):
        """
        Generate index page for a specific language.

        Args:
            lang: Language code
        """
        # Determine output file
        if lang == "ja":
            output_file = self.output_dir / "index.html"
        else:
            output_file = self.output_dir / f"index_{lang}.html"

        # Check if there's a custom index.md
        index_md = self.src_dir / lang / "index.md"
        intro_content = ""

        if index_md.exists():
            metadata, content = self.parse_front_matter(index_md)
            # Convert markdown content to HTML for intro
            if content:
                intro_content = self.markdown_to_html_simple(content)

        # Build categories data
        categories_data = []

        for cat_config in self.config["categories"]:
            cat_id = cat_config["id"]
            cat_name = cat_config["name_ja"] if lang == "ja" else cat_config["name_en"]
            cat_desc = cat_config.get("description_ja" if lang == "ja" else "description_en", "")

            # Get tools in this category - try registry first, then fallback to markdown
            tools_in_category = self.tools_info.get(cat_id, [])
            tools_data = []

            if tools_in_category:
                # Use registry data
                for tool in tools_in_category:
                    tool_name = tool["name"]
                    tool_config = tool.get("config", {})
                    tool_description = tool_config.get("description", "")
                    tool_version = tool_config.get("version", "")
                    tool_tool_name = tool["tool_name"]

                    # Check if documentation exists
                    doc_file = self.src_dir / lang / cat_id / f"{tool_tool_name}.md"
                    has_doc = doc_file.exists()
                    url = ""
                    order = 100  # Default order

                    if has_doc:
                        url = f"{lang}/{cat_id}/{tool_tool_name}.html"
                        # Get order from markdown front matter
                        metadata, _ = self.parse_front_matter(doc_file)
                        order = metadata.get("order", 100)

                    tools_data.append(
                        {"name": tool_name, "description": tool_description, "version": tool_version, "url": url, "has_doc": has_doc, "order": order}
                    )

                # Sort by order (ascending), then by name (alphabetically)
                tools_data.sort(key=lambda t: (t["order"], t["name"]))
            else:
                # Fallback: collect from markdown files
                tools_data = self._collect_tools_from_markdown(lang, cat_id)

            if tools_data:  # Only add category if it has tools
                categories_data.append({"id": cat_id, "name": cat_name, "description": cat_desc, "tools": tools_data})

        # Prepare template data
        template_data = {
            "lang": lang,
            "title": self.config["project"]["name" if lang == "ja" else "name_en"],
            "intro": intro_content,
            "categories": categories_data,
            "project_name": self.config["project"]["name" if lang == "ja" else "name_en"],
            "home_link": "index.html" if lang == "ja" else "index_en.html",
            "lang_link": "index_en.html" if lang == "ja" else "index.html",
            "lang_link_text": "日本語" if lang == "en" else "English",
        }

        # Generate HTML from template
        self.render_index_template(output_file, template_data)

        print(f"Generated index page: {output_file}")

    def markdown_to_html_simple(self, markdown_text: str) -> str:
        """
        Convert markdown to HTML using Pandoc (simple conversion).

        Args:
            markdown_text: Markdown text

        Returns:
            str: HTML text
        """
        try:
            result = subprocess.run(["pandoc", "-f", "markdown", "-t", "html"], input=markdown_text, capture_output=True, text=True, encoding="utf-8")

            if result.returncode == 0:
                return result.stdout
            else:
                return markdown_text
        except Exception:
            return markdown_text

    def render_index_template(self, output_file: Path, data: dict):
        """
        Render index template with data.

        Args:
            output_file: Output HTML file
            data: Template data
        """
        # Build HTML directly instead of using template substitution
        html_parts = []

        # Header
        html_parts.append("<!DOCTYPE html>")
        html_parts.append(f'<html lang="{data["lang"]}">')
        html_parts.append("<head>")
        html_parts.append('    <meta charset="utf-8">')
        html_parts.append('    <meta name="viewport" content="width=device-width, initial-scale=1.0">')
        html_parts.append(f"    <title>{data['title']} - FakeTools</title>")
        html_parts.append('    <link rel="stylesheet" href="css/style.css">')
        html_parts.append("</head>")
        html_parts.append("<body>")

        # Site header
        html_parts.append('    <header class="site-header">')
        html_parts.append('        <div class="header-content">')
        html_parts.append('            <div class="logo">')
        html_parts.append(f'                <a href="{data["home_link"]}">{data["project_name"]}</a>')
        html_parts.append("            </div>")
        html_parts.append('            <div class="header-actions">')
        html_parts.append('                <button class="search-trigger-btn" aria-label="Search">')
        html_parts.append(
            '                    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><circle cx="6.5" cy="6.5" r="5"/><line x1="10" y1="10" x2="15" y2="15"/></svg>'
        )
        html_parts.append('                    <span class="search-shortcut-hint">Ctrl+K</span>')
        html_parts.append("                </button>")
        html_parts.append('                <nav class="language-switcher">')
        html_parts.append(f'                    <a href="{data["lang_link"]}" class="lang-switch-btn">{data["lang_link_text"]}</a>')
        html_parts.append("                </nav>")
        html_parts.append("            </div>")
        html_parts.append("        </div>")
        html_parts.append("    </header>")

        # Page layout with nav sidebar
        html_parts.append('    <div class="page-layout">')
        html_parts.append('        <aside class="nav-sidebar" id="navSidebar">')
        html_parts.append('            <div class="nav-sidebar-content"></div>')
        html_parts.append("        </aside>")
        html_parts.append('        <div class="content-area">')
        html_parts.append('            <main class="main-content">')
        html_parts.append(f'                <h1 class="page-title">{data["title"]}</h1>')

        # Categories
        if data.get("categories"):
            html_parts.append(self.render_categories(data["categories"]))

        html_parts.append("            </main>")
        html_parts.append("        </div>")
        html_parts.append("    </div>")

        # Footer
        html_parts.append('    <footer class="site-footer">')
        html_parts.append('        <div class="footer-content">')
        html_parts.append("            <p>&copy; 2025 FakeTools. Generated with Pandoc.</p>")
        html_parts.append("        </div>")
        html_parts.append("    </footer>")

        # Navigation data inline script
        if data["lang"] in self._nav_json:
            html_parts.append(f"    <script>window.__NAV_DATA__={self._nav_json[data['lang']]};</script>")

        # Search index inline script
        if data["lang"] in self._search_indices:
            html_parts.append(f"    <script>window.__SEARCH_INDEX__={self._search_indices[data['lang']]};</script>")

        # Scripts
        html_parts.append('    <script src="js/main.js"></script>')
        html_parts.append("</body>")
        html_parts.append("</html>")

        # Write output
        output_file.write_text("\n".join(html_parts), encoding="utf-8")

    def remove_conditional_block(self, template: str, condition: str) -> str:
        """
        Remove a conditional block from template.

        Args:
            template: Template string
            condition: Condition name

        Returns:
            str: Template without the block
        """
        import re

        pattern = rf"\$if\({condition}\)\$.*?\$endif\$"
        return re.sub(pattern, "", template, flags=re.DOTALL)

    def _find_thumbnail(self, tool: dict) -> dict:
        """
        Find thumbnail images for a tool card.

        Checks docs/src/images/thumbnails/ for static and animated images.

        Args:
            tool: Tool data dict with 'url' key

        Returns:
            dict: {'static': path, 'gif': path} - either or both may be empty
        """
        result = {"static": "", "gif": ""}
        if not tool.get("url"):
            return result

        tool_stem = tool["url"].rsplit("/", 1)[-1].replace(".html", "")
        thumb_dir = self.src_dir / "images" / "thumbnails"

        # Check for GIF
        if (thumb_dir / f"{tool_stem}.gif").exists():
            result["gif"] = f"images/thumbnails/{tool_stem}.gif"

        # Check for static image (PNG or JPG)
        for ext in (".png", ".jpg"):
            if (thumb_dir / f"{tool_stem}{ext}").exists():
                result["static"] = f"images/thumbnails/{tool_stem}{ext}"
                break

        return result

    def render_categories(self, categories: list[dict]) -> str:
        """
        Render categories HTML.

        Args:
            categories: Categories data

        Returns:
            str: HTML string
        """
        html_parts = ['            <div class="tool-categories">']

        for cat in categories:
            html_parts.append('                <section class="category-section">')
            html_parts.append(f'                    <h2 id="{cat["id"]}">{cat["name"]}</h2>')

            if cat.get("tools"):
                html_parts.append('                    <div class="tool-grid">')

                for tool in cat["tools"]:
                    has_doc_class = " has-doc" if tool.get("has_doc") else ""
                    thumb = self._find_thumbnail(tool)
                    has_thumb = thumb["static"] or thumb["gif"]
                    has_thumb_class = " has-thumb" if has_thumb else ""
                    html_parts.append(f'                        <div class="tool-card{has_doc_class}{has_thumb_class}">')
                    html_parts.append('                            <div class="tool-card-header">')
                    html_parts.append("                            <h3>")

                    if tool.get("url"):
                        html_parts.append(f'                                <a href="{tool["url"]}">{tool["name"]}</a>')
                    else:
                        html_parts.append(f"                                {tool['name']}")

                    html_parts.append("                            </h3>")
                    html_parts.append("                            </div>")

                    # Thumbnail between title and description
                    if has_thumb:
                        src = thumb["static"] or thumb["gif"]
                        gif_attr = f' data-gif="{thumb["gif"]}"' if thumb["gif"] and thumb["static"] else ""
                        html_parts.append(
                            f'                            <img class="tool-card-thumb" src="{src}"{gif_attr} alt="{tool["name"]}" loading="lazy">'
                        )

                    html_parts.append('                            <div class="tool-card-body">')
                    html_parts.append(f'                            <p class="tool-description">{tool.get("description", "")}</p>')

                    if tool.get("version"):
                        html_parts.append(f'                            <span class="tool-version">v{tool["version"]}</span>')

                    html_parts.append("                            </div>")
                    html_parts.append("                        </div>")

                html_parts.append("                    </div>")

            html_parts.append("                </section>")

        html_parts.append("            </div>")

        return "\n".join(html_parts)

    def build_nav_data(self, lang: str) -> list[dict]:
        """
        Build navigation data structure for sidebar.

        Args:
            lang: Language code

        Returns:
            list[dict]: Categories with their tools for navigation
        """
        nav_categories = []
        for cat_config in self.config["categories"]:
            cat_id = cat_config["id"]
            cat_name = cat_config["name_ja"] if lang == "ja" else cat_config["name_en"]
            tools = self._collect_tools_from_markdown(lang, cat_id)
            if tools:
                nav_tools = [{"name": t["name"], "url": t["url"], "tool_name": t["url"].rsplit("/", 1)[-1].replace(".html", "")} for t in tools]
                nav_categories.append({"id": cat_id, "name": cat_name, "tools": nav_tools})
        return nav_categories

    def build_page_order(self, lang: str) -> dict[str, dict]:
        """
        Build prev/next link mapping for all tool pages within each category.

        Args:
            lang: Language code

        Returns:
            dict: Mapping of md file stem to {prev_title, prev_link, next_title, next_link}
        """
        page_nav = {}
        for cat_config in self.config["categories"]:
            cat_id = cat_config["id"]
            tools = self._collect_tools_from_markdown(lang, cat_id)
            for i, tool in enumerate(tools):
                stem = tool["url"].rsplit("/", 1)[-1].replace(".html", "")
                nav_info = {}
                if i > 0:
                    nav_info["prev_title"] = tools[i - 1]["name"]
                    nav_info["prev_link"] = tools[i - 1]["url"].rsplit("/", 1)[-1]
                if i < len(tools) - 1:
                    nav_info["next_title"] = tools[i + 1]["name"]
                    nav_info["next_link"] = tools[i + 1]["url"].rsplit("/", 1)[-1]
                if nav_info:
                    page_nav[f"{cat_id}/{stem}"] = nav_info
        return page_nav

    def build_search_index(self, lang: str) -> str:
        """
        Build search index JSON string for a language.

        Args:
            lang: Language code

        Returns:
            str: JSON string of search index entries
        """
        entries = []
        lang_dir = self.src_dir / lang

        if not lang_dir.exists():
            return "[]"

        for md_file in lang_dir.rglob("*.md"):
            # Skip index files
            if md_file.stem == "index":
                continue

            metadata, content = self.parse_front_matter(md_file)

            # Skip hidden pages (sub-pages)
            if metadata.get("hidden"):
                continue

            title = metadata.get("title", md_file.stem)
            description = metadata.get("description", "")

            # Determine category
            rel_path = md_file.relative_to(lang_dir)
            category = ""
            category_name = ""
            if len(rel_path.parts) > 1:
                category = rel_path.parts[0]
                for cat in self.config["categories"]:
                    if cat["id"] == category:
                        category_name = cat["name_ja"] if lang == "ja" else cat["name_en"]
                        break

            # Strip markdown syntax for body text
            body_text = re.sub(r"[#*`\[\]()!]", "", content)
            body_text = re.sub(r"\n+", " ", body_text)
            body_text = re.sub(r"\s+", " ", body_text).strip()

            # Calculate URL
            url = f"{lang}/{str(rel_path.with_suffix('.html')).replace(chr(92), '/')}"

            entries.append(
                {
                    "title": title,
                    "description": description,
                    "category": category_name,
                    "url": url,
                    "body": body_text,
                }
            )

        return json.dumps(entries, ensure_ascii=False)

    def build(self):
        """Run the complete build process."""
        print("=" * 60)
        print("FakeTools Documentation Build")
        print("=" * 60)

        # Check Pandoc
        if not self.check_pandoc():
            print("ERROR: Pandoc is not installed or not in PATH.")
            print("Please install Pandoc from: https://pandoc.org/installing.html")
            return False

        print("[OK] Pandoc is available")
        print(f"[OK] Loaded {sum(len(tools) for tools in self.tools_info.values())} tools from registry")

        # Clean output directory
        self.clean_output()

        # Copy assets
        self.copy_assets()

        # Build navigation data and page order (before processing markdown)
        print("\nBuilding navigation data...")
        for lang_config in self.config["languages"]:
            lang_code = lang_config["code"]
            self._nav_data[lang_code] = self.build_nav_data(lang_code)
            self._nav_json[lang_code] = json.dumps(self._nav_data[lang_code], ensure_ascii=False)
            self._page_order[lang_code] = self.build_page_order(lang_code)
            tool_count = sum(len(c["tools"]) for c in self._nav_data[lang_code])
            print(f"  [{lang_code}] {tool_count} tools in {len(self._nav_data[lang_code])} categories")

        # Build search indices (before processing markdown so they can be embedded)
        print("\nBuilding search indices...")
        for lang_config in self.config["languages"]:
            lang_code = lang_config["code"]
            self._search_indices[lang_code] = self.build_search_index(lang_code)
            entry_count = self._search_indices[lang_code].count('"title"')
            print(f"  [{lang_code}] {entry_count} entries")

        # Process markdown files
        print("\nProcessing markdown files...")
        self.process_markdown_files()

        # Generate index pages
        print("\nGenerating index pages...")
        self.generate_index_pages()

        print("\n" + "=" * 60)
        print("Build completed successfully!")
        print(f"Output directory: {self.output_dir.absolute()}")
        print("=" * 60)

        return True


def main():
    """Main entry point."""
    # Determine docs root (current directory of this script)
    docs_root = Path(__file__).parent

    # Create builder and run build
    builder = DocBuilder(docs_root)
    success = builder.build()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
