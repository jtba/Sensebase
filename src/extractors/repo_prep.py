"""Smart file preparation module for repo-level LLM context generation.

Categorizes repository files into tiers and builds a structured manifest
for the LLM prompt, ensuring the most important files get full content
while staying within token limits.
"""

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_SKIP_DIRS = {
    "node_modules", "vendor", ".venv", "venv", "__pycache__", "target",
    "build", "dist", ".git", ".idea", ".vscode",
}

BINARY_EXTENSIONS = {
    # Images
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".svg", ".webp", ".tiff",
    # Fonts
    ".woff", ".woff2", ".ttf", ".otf", ".eot",
    # Archives
    ".zip", ".tar", ".gz", ".bz2", ".xz", ".rar", ".7z",
    # Compiled / binary
    ".pyc", ".pyo", ".class", ".o", ".so", ".dylib", ".dll", ".exe",
    ".jar", ".war", ".ear",
    # Media
    ".mp3", ".mp4", ".avi", ".mov", ".wav", ".flac",
    # Other binary
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".db", ".sqlite", ".sqlite3",
}

LOCK_FILES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "poetry.lock", "Cargo.lock", "go.sum", "Gemfile.lock",
    "composer.lock", "Pipfile.lock",
}

# Entry-point file names (case-insensitive matching handled in code)
ENTRY_POINT_NAMES = {
    "main.py", "app.py", "index.ts", "index.js", "application.java",
    "main.java", "main.go", "server.py", "server.js", "server.ts",
}

# Config file names that are always tier 1 regardless of location
CONFIG_FILE_NAMES = {
    "docker-compose.yml", "docker-compose.yaml", "docker-compose.override.yml",
    "dockerfile", "pom.xml", "build.gradle", "build.gradle.kts",
    "package.json", "go.mod", "pyproject.toml", "cargo.toml",
    "requirements.txt", "gemfile", "makefile", "cmakelists.txt",
    "tsconfig.json", "webpack.config.js", "vite.config.ts", "vite.config.js",
}

# Extensions for config files that are tier 1 only in root or config/ dir
CONFIG_EXTENSIONS = {".yaml", ".yml", ".toml", ".ini"}

# Tier-1 name substrings: files whose stem contains these are tier 1
TIER1_NAME_KEYWORDS = {
    "route", "controller", "handler", "endpoint",
    "model", "schema", "entity", "migration",
}

# Source code extensions eligible for tier 2 (signature extraction)
SOURCE_EXTENSIONS = {
    ".py", ".java", ".go", ".js", ".ts", ".jsx", ".tsx",
    ".rb", ".rs", ".cs", ".php", ".sql", ".graphql", ".proto",
}

# Extension -> language mapping
EXT_TO_LANGUAGE = {
    ".py": "python",
    ".pyi": "python",
    ".java": "java",
    ".go": "go",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".rb": "ruby",
    ".rs": "rust",
    ".cs": "csharp",
    ".php": "php",
    ".sql": "sql",
    ".graphql": "graphql",
    ".gql": "graphql",
    ".proto": "protobuf",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".json": "json",
    ".xml": "xml",
    ".ini": "ini",
    ".cfg": "ini",
    ".md": "markdown",
    ".rst": "restructuredtext",
    ".txt": "text",
    ".sh": "bash",
    ".bash": "bash",
    ".zsh": "zsh",
    ".dockerfile": "dockerfile",
}


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class RepoManifest:
    """Structured manifest of repository content for LLM consumption."""

    repo_name: str
    repo_path: str
    file_tree: str              # Indented tree of all files
    tier1_files: list[dict]     # [{path, content, language}] -- full content
    tier2_files: list[dict]     # [{path, signatures, language}] -- signatures only
    tier3_files: list[str]      # [path, ...] -- just file paths
    total_files: int
    estimated_tokens: int


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class RepoFilePreparator:
    """Prepare repository content for LLM context generation.

    Walks a repository, classifies every file into one of three tiers,
    and builds a :class:`RepoManifest` that fits within a configurable
    token budget.
    """

    def __init__(
        self,
        skip_dirs: set[str] | None = None,
        max_tokens: int = 150_000,
        max_file_size: int = 500_000,
    ):
        self.skip_dirs: set[str] = skip_dirs if skip_dirs is not None else DEFAULT_SKIP_DIRS
        self.max_tokens = max_tokens
        self.max_file_size = max_file_size

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def prepare(self, repo_path: Path) -> RepoManifest:
        """Walk *repo_path*, categorize files, and build a manifest.

        Steps:
        1. Walk all files, skip excluded dirs and binary files.
        2. Classify each file into tier 1, 2, or 3.
        3. Read tier 1 files (full content).
        4. Read tier 2 files and extract signatures.
        5. Build file tree string (indented listing of all files).
        6. Estimate total tokens.
        7. If over *max_tokens*, truncate tier 2 (remove smallest first).
        8. Return :class:`RepoManifest`.
        """
        repo_path = repo_path.resolve()
        repo_name = repo_path.name

        # 1. Discover files -------------------------------------------------
        all_files: list[Path] = []
        tier1_paths: list[Path] = []
        tier2_paths: list[Path] = []
        tier3_paths: list[Path] = []

        for file_path in sorted(repo_path.rglob("*")):
            if not file_path.is_file():
                continue

            # Skip excluded directories
            rel_parts = file_path.relative_to(repo_path).parts
            if any(part in self.skip_dirs for part in rel_parts):
                continue

            # Skip files larger than threshold
            try:
                if file_path.stat().st_size > self.max_file_size:
                    continue
            except OSError:
                continue

            # Skip binary files
            if self._is_binary(file_path):
                continue

            all_files.append(file_path)

            # 2. Classify
            tier = self._classify_file(file_path, repo_path)
            if tier == 1:
                tier1_paths.append(file_path)
            elif tier == 2:
                tier2_paths.append(file_path)
            else:
                tier3_paths.append(file_path)

        # 3. Read tier 1 files (full content) --------------------------------
        tier1_files: list[dict] = []
        for fp in tier1_paths:
            content = self._safe_read(fp)
            if content is not None:
                tier1_files.append({
                    "path": str(fp.relative_to(repo_path)),
                    "content": content,
                    "language": self._detect_language(fp),
                })

        # 4. Read tier 2 files and extract signatures ------------------------
        tier2_files: list[dict] = []
        for fp in tier2_paths:
            content = self._safe_read(fp)
            if content is not None:
                language = self._detect_language(fp)
                signatures = self._extract_signatures(content, language)
                tier2_files.append({
                    "path": str(fp.relative_to(repo_path)),
                    "signatures": signatures,
                    "language": language,
                })

        # 5. Build file tree -------------------------------------------------
        tier3_file_strs = [str(fp.relative_to(repo_path)) for fp in tier3_paths]
        file_tree = self._build_file_tree(repo_path, all_files)

        # 6. Estimate tokens -------------------------------------------------
        prompt_overhead = 2000
        tier1_tokens = sum(self._estimate_tokens(f["content"]) for f in tier1_files)
        tier2_tokens = sum(self._estimate_tokens(f["signatures"]) for f in tier2_files)
        tree_tokens = self._estimate_tokens(file_tree)
        total_tokens = prompt_overhead + tree_tokens + tier1_tokens + tier2_tokens

        # 7. Budget management -----------------------------------------------
        if total_tokens > self.max_tokens:
            # Sort tier 2 by token size ascending and demote smallest first
            tier2_with_size = [
                (self._estimate_tokens(f["signatures"]), i, f)
                for i, f in enumerate(tier2_files)
            ]
            tier2_with_size.sort(key=lambda x: x[0])

            new_tier2: list[dict] = []
            running = prompt_overhead + tree_tokens + tier1_tokens
            # Walk from largest to smallest so we keep the biggest / most
            # informative files and drop the small ones first.
            # Strategy: remove smallest files first (pop from front).
            kept: list[tuple[int, int, dict]] = []
            for entry in reversed(tier2_with_size):
                if running + entry[0] <= self.max_tokens:
                    running += entry[0]
                    kept.append(entry)
                else:
                    # Demote to tier 3
                    tier3_file_strs.append(entry[2]["path"])

            # Restore original ordering among kept files
            kept.sort(key=lambda x: x[1])
            tier2_files = [k[2] for k in kept]
            total_tokens = running

        # If STILL over (tier 1 alone is huge), truncate large tier 1 files
        if total_tokens > self.max_tokens:
            tier1_tokens_recalc = 0
            for f in tier1_files:
                lines = f["content"].splitlines(keepends=True)
                if len(lines) > 200:
                    f["content"] = "".join(lines[:200]) + "\n# ... (truncated)\n"
            tier1_tokens_recalc = sum(self._estimate_tokens(f["content"]) for f in tier1_files)
            total_tokens = prompt_overhead + tree_tokens + tier1_tokens_recalc + sum(
                self._estimate_tokens(f["signatures"]) for f in tier2_files
            )

        # 8. Return manifest -------------------------------------------------
        return RepoManifest(
            repo_name=repo_name,
            repo_path=str(repo_path),
            file_tree=file_tree,
            tier1_files=tier1_files,
            tier2_files=tier2_files,
            tier3_files=sorted(tier3_file_strs),
            total_files=len(all_files),
            estimated_tokens=total_tokens,
        )

    # ------------------------------------------------------------------
    # File classification
    # ------------------------------------------------------------------

    def _classify_file(self, file_path: Path, repo_root: Path) -> int:
        """Return tier (1, 2, or 3) for *file_path*.

        Tier 1 -- files that define WHAT the service is.
        Tier 2 -- source code files (signatures only).
        Tier 3 -- everything else of note.
        """
        rel = file_path.relative_to(repo_root)
        name_lower = file_path.name.lower()
        stem_lower = file_path.stem.lower()
        suffix_lower = file_path.suffix.lower()
        rel_parts = rel.parts

        # --- Tier 1 checks ---

        # README, CONTRIBUTING, CHANGELOG (any extension)
        if stem_lower.startswith(("readme", "contributing", "changelog")):
            return 1

        # Entry-point files
        if name_lower in ENTRY_POINT_NAMES:
            return 1

        # Config file names (case-insensitive)
        if name_lower in CONFIG_FILE_NAMES:
            return 1

        # Dockerfile variants (e.g. Dockerfile.prod)
        if stem_lower == "dockerfile" or name_lower.startswith("dockerfile."):
            return 1

        # docker-compose variants
        if name_lower.startswith("docker-compose"):
            return 1

        # Name-keyword matching (route, controller, handler, model, schema, etc.)
        if any(kw in stem_lower for kw in TIER1_NAME_KEYWORDS):
            # Only promote source code files -- not random .txt/.md that match
            if suffix_lower in SOURCE_EXTENSIONS:
                return 1

        # Config files (.yaml, .yml, .toml, .ini) in root or config/ directory
        if suffix_lower in CONFIG_EXTENSIONS:
            if len(rel_parts) == 1:
                # Root-level config file
                return 1
            if len(rel_parts) == 2 and rel_parts[0].lower() == "config":
                return 1

        # --- Tier 2 checks ---
        if suffix_lower in SOURCE_EXTENSIONS:
            return 2

        # --- Tier 3 (everything else) ---
        return 3

    # ------------------------------------------------------------------
    # File tree builder
    # ------------------------------------------------------------------

    def _build_file_tree(self, repo_path: Path, all_files: list[Path]) -> str:
        """Build an indented file tree string (like simplified ``tree`` output)."""
        if not all_files:
            return "(empty)\n"

        lines: list[str] = [f"{repo_path.name}/"]

        # Build a sorted list of relative paths
        rel_paths = sorted(str(fp.relative_to(repo_path)) for fp in all_files)

        # Track which directory prefixes we have already printed
        seen_dirs: set[str] = set()

        for rel in rel_paths:
            parts = rel.split(os.sep)

            # Print directory prefixes we haven't printed yet
            for depth in range(len(parts) - 1):
                dir_prefix = os.sep.join(parts[: depth + 1])
                if dir_prefix not in seen_dirs:
                    seen_dirs.add(dir_prefix)
                    indent = "  " * (depth + 1)
                    lines.append(f"{indent}{parts[depth]}/")

            # Print the file itself
            indent = "  " * len(parts)
            lines.append(f"{indent}{parts[-1]}")

        return "\n".join(lines) + "\n"

    # ------------------------------------------------------------------
    # Signature extraction
    # ------------------------------------------------------------------

    def _extract_signatures(self, content: str, language: str) -> str:
        """Extract a structural outline from source code.

        The goal is a compact representation that preserves the public API
        surface while stripping implementation bodies.  This uses a
        line-based heuristic approach -- not full AST parsing -- so it
        works reasonably across many languages.
        """
        if language == "python":
            return self._extract_python_signatures(content)
        if language in ("javascript", "typescript"):
            return self._extract_js_ts_signatures(content)
        if language in ("java", "go", "csharp", "rust"):
            return self._extract_curly_brace_signatures(content, language)
        # Generic fallback
        return self._extract_generic_signatures(content)

    # -- Python signatures --

    def _extract_python_signatures(self, content: str) -> str:
        """Extract Python structural outline.

        Keeps imports, class/def lines (with type hints), decorators,
        and the first docstring after each class/def.  Replaces function
        bodies with ``...``.  For class bodies, recursively extracts
        nested method signatures.
        """
        lines = content.splitlines()
        result: list[str] = []
        self._extract_python_block(lines, 0, -1, result)
        return "\n".join(result)

    def _extract_python_block(
        self,
        lines: list[str],
        start: int,
        parent_indent: int,
        result: list[str],
    ) -> int:
        """Extract Python signatures from a block at *parent_indent* level.

        Returns the index of the first line that exits the current block
        (i.e., has indent <= *parent_indent*).
        """
        i = start
        while i < len(lines):
            line = lines[i]
            stripped = line.lstrip()

            # Blank lines -- compress
            if not stripped:
                if result and result[-1].strip() != "":
                    result.append("")
                i += 1
                continue

            current_indent = len(line) - len(stripped)

            # If we've dedented back to or past the parent level, stop
            if parent_indent >= 0 and current_indent <= parent_indent:
                return i

            # Import lines
            if stripped.startswith(("import ", "from ")):
                result.append(line)
                i += 1
                continue

            # Decorator lines
            if stripped.startswith("@"):
                result.append(line)
                i += 1
                continue

            # class declarations -- recurse into the body
            if re.match(r"^\s*class\s+", line):
                result.append(line)
                i += 1

                # Grab continuation lines for multi-line class signature
                while i < len(lines) and not lines[i - 1].rstrip().endswith(":"):
                    result.append(lines[i])
                    i += 1

                # Docstring
                i = self._maybe_grab_docstring(lines, i, result)

                # Recurse into class body to extract method signatures
                i = self._extract_python_block(lines, i, current_indent, result)
                continue

            # def / async def declarations
            if re.match(r"^\s*(async\s+)?def\s+", line):
                result.append(line)
                i += 1

                # Grab continuation lines for multi-line signatures
                while i < len(lines) and not lines[i - 1].rstrip().endswith(":"):
                    result.append(lines[i])
                    i += 1

                # Docstring
                i = self._maybe_grab_docstring(lines, i, result)

                # Replace the body with ...
                body_indent = " " * (current_indent + 4)
                result.append(f"{body_indent}...")

                # Skip the actual body
                i = self._skip_python_block(lines, i, current_indent)
                continue

            # Comment lines
            if stripped.startswith("#"):
                result.append(line)
                i += 1
                continue

            # Top-level assignments (module constants)
            if re.match(r"^[A-Z_][A-Z0-9_]*\s*[:=]", stripped):
                result.append(line)
                i += 1
                continue

            # Skip everything else
            i += 1

        return i

    @staticmethod
    def _maybe_grab_docstring(lines: list[str], i: int, result: list[str]) -> int:
        """If the line at *i* starts a docstring, append it to *result*.

        Returns the updated index.
        """
        if i >= len(lines):
            return i
        doc_stripped = lines[i].lstrip()
        if doc_stripped.startswith(('"""', "'''")):
            quote = doc_stripped[:3]
            # Single-line docstring (e.g. """Foo.""")
            if doc_stripped.count(quote) >= 2:
                result.append(lines[i])
                return i + 1
            # Multi-line docstring
            result.append(lines[i])
            i += 1
            while i < len(lines):
                result.append(lines[i])
                if quote in lines[i]:
                    i += 1
                    break
                i += 1
        return i

    @staticmethod
    def _skip_python_block(lines: list[str], start: int, parent_indent: int) -> int:
        """Skip past a Python indented block starting at *start*.

        Returns the index of the first line that is at or below
        *parent_indent* level (i.e., no longer part of the block).
        """
        i = start
        while i < len(lines):
            line = lines[i]
            if line.strip() == "":
                i += 1
                continue
            current_indent = len(line) - len(line.lstrip())
            if current_indent <= parent_indent:
                return i
            i += 1
        return i

    # -- JavaScript / TypeScript signatures --

    def _extract_js_ts_signatures(self, content: str) -> str:
        """Extract JS/TS structural outline.

        Keeps imports/exports, class/function/const declarations, JSDoc
        comments, and interface/type declarations.  For classes, recurses
        into the body to extract method signatures.  Replaces method
        bodies with ``// ...``.
        """
        lines = content.splitlines()
        result: list[str] = []
        self._extract_js_ts_level(lines, 0, result, in_class=False)
        return "\n".join(result)

    def _extract_js_ts_level(
        self,
        lines: list[str],
        start: int,
        result: list[str],
        *,
        in_class: bool = False,
    ) -> int:
        """Extract JS/TS signatures from a sequence of lines.

        When *in_class* is True we are inside a class body and look for
        method/field declarations.  Returns the index after the closing
        ``}`` of the class (or end of file if at top level).
        """
        i = start
        brace_depth = 1 if in_class else 0

        while i < len(lines):
            line = lines[i]
            stripped = line.lstrip()

            # Blank lines (compress)
            if not stripped:
                if result and result[-1].strip() != "":
                    result.append("")
                i += 1
                continue

            # If inside a class body, watch for the closing brace
            if in_class:
                if stripped.startswith("}"):
                    result.append(line)
                    return i + 1

            # JSDoc / block comments
            if stripped.startswith("/**") or stripped.startswith("/*"):
                while i < len(lines):
                    result.append(lines[i])
                    if "*/" in lines[i]:
                        i += 1
                        break
                    i += 1
                continue

            # Single-line comments
            if stripped.startswith("//"):
                result.append(line)
                i += 1
                continue

            # Decorators (TypeScript/Angular style)
            if stripped.startswith("@"):
                result.append(line)
                i += 1
                continue

            if in_class:
                # --- Inside a class body: look for methods and fields ---

                # Method signatures:
                #   constructor(...)  |  async foo(...)  |  get/set prop(...)
                #   public/private/protected/static/abstract/override modifiers
                method_match = re.match(
                    r"^\s*"
                    r"(?:(?:public|private|protected|static|abstract|override|readonly)\s+)*"
                    r"(?:async\s+)?"
                    r"(?:get\s+|set\s+)?"
                    r"(?:constructor|\w+)"
                    r"\s*(?:<[^>]*>)?"   # optional generic params
                    r"\s*\(",
                    line,
                )
                if method_match:
                    result.append(line)
                    i += 1
                    # Multi-line parameter list
                    while i < len(lines) and "{" not in lines[i - 1] and ";" not in lines[i - 1]:
                        result.append(lines[i])
                        i += 1
                    # Skip method body
                    if i > start and "{" in lines[i - 1]:
                        indent = len(line) - len(stripped)
                        result.append(f"{' ' * (indent + 2)}// ...")
                        body_depth = lines[i - 1].count("{") - lines[i - 1].count("}")
                        while i < len(lines) and body_depth > 0:
                            body_depth += lines[i].count("{") - lines[i].count("}")
                            i += 1
                    continue

                # Field declarations  (e.g. `private name: string;`)
                if re.match(
                    r"^\s*(?:(?:public|private|protected|static|readonly|abstract|override)\s+)*"
                    r"\w+\s*[?!]?\s*[:=;]",
                    stripped,
                ):
                    result.append(line)
                    i += 1
                    continue

                # Anything else inside the class -- skip but track braces
                i += 1
                continue

            # --- Top-level declarations ---

            # Import / require lines
            if re.match(
                r"^\s*(import |export \{|export \* |"
                r"const \w+ = require\(|let \w+ = require\(|var \w+ = require\()",
                line,
            ):
                result.append(line)
                i += 1
                while i < len(lines):
                    prev = lines[i - 1].rstrip()
                    if prev.endswith(";") or (prev.endswith("}") and "from" in prev):
                        break
                    if lines[i].strip() == "":
                        break
                    result.append(lines[i])
                    i += 1
                continue

            # export default / export { ... } (non-import exports)
            if re.match(r"^\s*export\s+", line) and not re.match(
                r"^\s*export\s+(default\s+)?(class |function |async |interface |type |enum )", line
            ):
                result.append(line)
                i += 1
                continue

            # Class declaration -- recurse into body for method signatures
            if re.match(
                r"^\s*(export\s+)?(default\s+)?(abstract\s+)?class\s+",
                line,
            ):
                result.append(line)
                i += 1
                # Continuation lines until opening brace
                while i < len(lines) and "{" not in lines[i - 1]:
                    result.append(lines[i])
                    i += 1
                i = self._extract_js_ts_level(lines, i, result, in_class=True)
                continue

            # Interface / type alias -- keep full declaration body
            if re.match(
                r"^\s*(export\s+)?(default\s+)?(interface |type )",
                line,
            ):
                result.append(line)
                i += 1
                if "{" in lines[i - 1]:
                    depth = lines[i - 1].count("{") - lines[i - 1].count("}")
                    while i < len(lines) and depth > 0:
                        result.append(lines[i])
                        depth += lines[i].count("{") - lines[i].count("}")
                        i += 1
                continue

            # Function / enum declarations
            if re.match(
                r"^\s*(export\s+)?(default\s+)?(async\s+)?"
                r"(function\s+\w+|enum\s+\w+)",
                line,
            ):
                result.append(line)
                i += 1
                # Continuation until {
                while i < len(lines) and "{" not in lines[i - 1]:
                    result.append(lines[i])
                    i += 1
                if i > start and "{" in lines[i - 1]:
                    indent = len(line) - len(stripped)
                    result.append(f"{' ' * (indent + 2)}// ...")
                    i = self._skip_brace_block(lines, i, lines[i - 1])
                continue

            # const / let / var declarations (arrow functions, etc.)
            if re.match(r"^\s*(export\s+)?(const|let|var)\s+\w+", line):
                result.append(line)
                i += 1
                brace_count = line.count("{") - line.count("}")
                if brace_count > 0:
                    indent = len(line) - len(stripped)
                    result.append(f"{' ' * (indent + 2)}// ...")
                    while i < len(lines) and brace_count > 0:
                        brace_count += lines[i].count("{") - lines[i].count("}")
                        i += 1
                continue

            # Skip everything else at top level
            i += 1

        return i

    # -- Curly-brace languages (Java, Go, C#, Rust) --

    def _extract_curly_brace_signatures(self, content: str, language: str) -> str:
        """Extract signatures for Java, Go, C#, and Rust.

        Keeps import/package/use lines, class/struct/interface/enum
        declarations, and method/function signatures.  Replaces bodies
        with ``// ...``.
        """
        lines = content.splitlines()
        result: list[str] = []
        i = 0

        # Language-specific import keywords
        import_keywords = {
            "java": ("import ", "package "),
            "go": ("import ", "package "),
            "csharp": ("using ", "namespace "),
            "rust": ("use ", "mod ", "extern crate "),
        }
        imports = import_keywords.get(language, ("import ", "package ", "use "))

        # Type / struct / class declaration keywords (NOT func/fn -- handled below)
        decl_re = re.compile(
            r"^\s*"
            r"(?:pub(?:\(crate\))?\s+)?"
            r"(?:public\s+|private\s+|protected\s+|internal\s+|static\s+|final\s+|abstract\s+|override\s+|virtual\s+|async\s+|unsafe\s+)*"
            r"(class |interface |struct |enum |trait |impl |type \w+\s+(?:struct|interface|enum)\b)"
        )

        # Top-level function / method patterns (Go funcs, Rust fns)
        func_re = re.compile(
            r"^\s*(?:pub(?:\(crate\))?\s+)?(?:async\s+)?(?:unsafe\s+)?"
            r"(?:fn\s+\w+|func\s+)"
        )

        while i < len(lines):
            line = lines[i]
            stripped = line.lstrip()

            # Blank lines
            if not stripped:
                if result and result[-1].strip() != "":
                    result.append("")
                i += 1
                continue

            # Javadoc / block comments
            if stripped.startswith("/**") or stripped.startswith("/*"):
                while i < len(lines):
                    result.append(lines[i])
                    if "*/" in lines[i]:
                        i += 1
                        break
                    i += 1
                continue

            # Line comments
            if stripped.startswith("//") or stripped.startswith("#"):
                result.append(line)
                i += 1
                continue

            # Annotations / decorators
            if stripped.startswith("@") or stripped.startswith("#["):
                result.append(line)
                i += 1
                continue

            # Import / package / use lines
            if any(stripped.startswith(kw) for kw in imports):
                result.append(line)
                i += 1
                # Go multi-line import block: import ( ... )
                if language == "go" and "(" in line and ")" not in line:
                    while i < len(lines):
                        result.append(lines[i])
                        if ")" in lines[i]:
                            i += 1
                            break
                        i += 1
                continue

            # Top-level function / method (Go funcs, Rust fns)
            # Check BEFORE decl_re so `func` doesn't get caught by decl_re
            if func_re.match(line):
                # Keep the signature line(s) up to {
                result.append(line)
                i += 1
                while i < len(lines) and "{" not in lines[i - 1]:
                    result.append(lines[i])
                    i += 1
                # Skip the body
                indent = len(line) - len(stripped)
                result.append(f"{' ' * (indent + 2)}// ...")
                i = self._skip_brace_block_from(lines, i)
                continue

            # Type / class / struct / interface / enum / trait / impl
            if decl_re.match(line):
                result.append(line)
                i += 1
                # If there's an opening brace on this line, we keep going
                # inside the body to find method signatures
                if "{" in line:
                    i = self._extract_member_signatures(lines, i, result, language)
                else:
                    # Declaration might continue to next line with {
                    while i < len(lines) and "{" not in lines[i]:
                        result.append(lines[i])
                        i += 1
                    if i < len(lines):
                        result.append(lines[i])
                        i += 1
                        i = self._extract_member_signatures(lines, i, result, language)
                continue

            # Skip everything else
            i += 1

        return "\n".join(result)

    def _extract_member_signatures(
        self,
        lines: list[str],
        start: int,
        result: list[str],
        language: str,
    ) -> int:
        """Extract method/field signatures from inside a class/struct body.

        Reads lines starting at *start* (which should be just after the
        opening ``{`` of the type declaration).  Returns the index after
        the matching closing ``}``.
        """
        brace_depth = 1
        i = start

        while i < len(lines) and brace_depth > 0:
            line = lines[i]
            stripped = line.lstrip()

            # Track braces
            open_braces = line.count("{")
            close_braces = line.count("}")

            # Closing brace at depth 1 means end of class
            if brace_depth == 1 and stripped.startswith("}"):
                result.append(line)
                brace_depth -= close_braces
                brace_depth += open_braces
                i += 1
                continue

            if brace_depth == 1:
                # Annotations
                if stripped.startswith("@") or stripped.startswith("#["):
                    result.append(line)
                    i += 1
                    continue

                # Comments
                if stripped.startswith("//") or stripped.startswith("#"):
                    result.append(line)
                    i += 1
                    continue

                # Block comments
                if stripped.startswith("/**") or stripped.startswith("/*"):
                    while i < len(lines):
                        result.append(lines[i])
                        if "*/" in lines[i]:
                            i += 1
                            break
                        i += 1
                    continue

                # Method/function signatures or field declarations
                if open_braces > 0:
                    # This line opens a new block -- keep as signature, skip body
                    result.append(line)
                    indent = len(line) - len(stripped)
                    result.append(f"{' ' * (indent + 2)}// ...")
                    # Skip past the body
                    inner_depth = open_braces - close_braces
                    i += 1
                    while i < len(lines) and inner_depth > 0:
                        inner_depth += lines[i].count("{") - lines[i].count("}")
                        i += 1
                    # Add closing brace line if we stopped right after it
                    continue
                else:
                    # Field declaration or single-line statement
                    result.append(line)
                    i += 1
                    continue
            else:
                # We're inside a nested block -- skip
                brace_depth += open_braces - close_braces
                i += 1

        return i

    @staticmethod
    def _skip_brace_block(lines: list[str], start: int, opening_line: str) -> int:
        """Skip past a brace-delimited block.

        *start* should point to the first line AFTER *opening_line*.
        Returns the index of the first line after the closing ``}``.
        """
        depth = opening_line.count("{") - opening_line.count("}")
        i = start
        while i < len(lines) and depth > 0:
            depth += lines[i].count("{") - lines[i].count("}")
            i += 1
        return i

    @staticmethod
    def _skip_brace_block_from(lines: list[str], start: int) -> int:
        """Skip past a brace-delimited block starting from *start*.

        Assumes the opening ``{`` is already counted.  Continues until
        brace depth returns to 0.
        """
        depth = 1
        i = start
        while i < len(lines) and depth > 0:
            depth += lines[i].count("{") - lines[i].count("}")
            i += 1
        return i

    # -- Generic fallback --

    def _extract_generic_signatures(self, content: str) -> str:
        """Fallback signature extraction using broad keyword matching.

        Keeps any line that looks like a structural declaration, import,
        comment, or annotation.
        """
        structural_re = re.compile(
            r"^\s*("
            r"import |from |require\(|export |package |use |pub |"
            r"class |struct |type |interface |enum |"
            r"def |fn |func |function |"
            r"const |let |var |"
            r"public |private |protected |abstract |static "
            r")"
        )
        decorator_re = re.compile(r"^\s*@")
        comment_re = re.compile(r"^\s*(//|#|/\*)")

        lines = content.splitlines()
        result: list[str] = []

        for line in lines:
            stripped = line.lstrip()
            if not stripped:
                if result and result[-1].strip() != "":
                    result.append("")
                continue

            if structural_re.match(line) or decorator_re.match(line) or comment_re.match(line):
                result.append(line)

        return "\n".join(result)

    # ------------------------------------------------------------------
    # Utility methods
    # ------------------------------------------------------------------

    def _detect_language(self, file_path: Path) -> str:
        """Detect language from file extension."""
        suffix = file_path.suffix.lower()

        # Handle Dockerfile without extension
        if file_path.name.lower().startswith("dockerfile"):
            return "dockerfile"

        return EXT_TO_LANGUAGE.get(suffix, "unknown")

    def _estimate_tokens(self, text: str) -> int:
        """Rough token estimate: ``len(text) / 4``."""
        return len(text) // 4

    def _is_binary(self, file_path: Path) -> bool:
        """Check if *file_path* is a binary file.

        Uses two heuristics:
        1. Known binary extensions.
        2. Presence of null bytes in the first 8 KB.
        """
        # Known binary extensions
        if file_path.suffix.lower() in BINARY_EXTENSIONS:
            return True

        # Lock files
        if file_path.name.lower() in LOCK_FILES:
            return True

        # Read first 8 KB and check for null bytes
        try:
            with open(file_path, "rb") as f:
                chunk = f.read(8192)
            return b"\x00" in chunk
        except OSError:
            return True

    @staticmethod
    def _safe_read(file_path: Path) -> str | None:
        """Read a text file, returning ``None`` on failure."""
        try:
            return file_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            logger.warning("Could not read %s", file_path)
            return None
