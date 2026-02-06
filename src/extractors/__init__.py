"""Language-specific extractors."""

from .java import JavaAnalyzer
from .python import PythonAnalyzer
from .go import GoAnalyzer
from .javascript import JavaScriptAnalyzer
from .schema import SchemaAnalyzer
from .config import ConfigAnalyzer

__all__ = [
    "JavaAnalyzer",
    "PythonAnalyzer", 
    "GoAnalyzer",
    "JavaScriptAnalyzer",
    "SchemaAnalyzer",
    "ConfigAnalyzer",
]

# Lazy import for LLM extractor (requires anthropic API)
def get_llm_extractor():
    from .llm_extractor import LLMExtractor, LLMAnalyzer
    return LLMExtractor, LLMAnalyzer
