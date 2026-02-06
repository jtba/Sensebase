"""Analyzer registry for managing language-specific analyzers."""

from pathlib import Path
from typing import Type

from rich.console import Console

from .base import Analyzer, AnalysisResult

console = Console()


class AnalyzerRegistry:
    """Registry of available analyzers."""
    
    def __init__(self):
        self._analyzers: dict[str, Analyzer] = {}
        self._extension_map: dict[str, list[Analyzer]] = {}
    
    def register(self, analyzer: Analyzer) -> None:
        """Register an analyzer."""
        self._analyzers[analyzer.language] = analyzer
        
        for ext in analyzer.extensions:
            if ext not in self._extension_map:
                self._extension_map[ext] = []
            self._extension_map[ext].append(analyzer)
    
    def get_analyzers_for_file(self, file_path: Path) -> list[Analyzer]:
        """Get all analyzers that can handle a file."""
        ext = file_path.suffix.lower()
        return self._extension_map.get(ext, [])
    
    def get_analyzer(self, language: str) -> Analyzer | None:
        """Get analyzer by language name."""
        return self._analyzers.get(language)
    
    def analyze_file(self, file_path: Path, content: str) -> AnalysisResult:
        """Analyze a file with all applicable analyzers."""
        result = AnalysisResult(
            repo_path=str(file_path.parent),
            repo_name=file_path.parent.name,
        )
        
        analyzers = self.get_analyzers_for_file(file_path)
        for analyzer in analyzers:
            try:
                file_result = analyzer.analyze_file(file_path, content)
                result.merge(file_result)
            except Exception as e:
                result.errors.append(f"{analyzer.language}: {e}")
        
        return result
    
    def analyze_repository(
        self,
        repo_path: Path,
        skip_dirs: list[str] | None = None,
        include_extensions: list[str] | None = None,
        max_file_size: int = 1_048_576,
    ) -> AnalysisResult:
        """Analyze an entire repository."""
        skip_dirs = set(skip_dirs or [])
        
        result = AnalysisResult(
            repo_path=str(repo_path),
            repo_name=repo_path.name,
        )
        
        for file_path in repo_path.rglob("*"):
            # Skip directories in exclusion list
            if any(skip in file_path.parts for skip in skip_dirs):
                continue
            
            if not file_path.is_file():
                continue
            
            # Check extension filter
            if include_extensions:
                if file_path.suffix.lower() not in include_extensions:
                    continue
            
            # Check file size
            try:
                if file_path.stat().st_size > max_file_size:
                    continue
            except OSError:
                continue
            
            # Check if we have analyzers for this file
            if not self.get_analyzers_for_file(file_path):
                continue
            
            result.file_count += 1
            
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                file_result = self.analyze_file(file_path, content)
                result.merge(file_result)
                result.analyzed_files.append(str(file_path.relative_to(repo_path)))
            except Exception as e:
                result.errors.append(f"{file_path}: {e}")
        
        return result


def create_default_registry() -> AnalyzerRegistry:
    """Create registry with all built-in analyzers."""
    from ..extractors.java import JavaAnalyzer
    from ..extractors.python import PythonAnalyzer
    from ..extractors.go import GoAnalyzer
    from ..extractors.javascript import JavaScriptAnalyzer
    from ..extractors.schema import SchemaAnalyzer
    from ..extractors.config import ConfigAnalyzer
    
    registry = AnalyzerRegistry()
    
    registry.register(JavaAnalyzer())
    registry.register(PythonAnalyzer())
    registry.register(GoAnalyzer())
    registry.register(JavaScriptAnalyzer())
    registry.register(SchemaAnalyzer())
    registry.register(ConfigAnalyzer())
    
    return registry
