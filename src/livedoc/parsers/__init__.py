"""Парсеры кода и документации."""

from livedoc.parsers.python_parser import parse_python_module
from livedoc.parsers.doc_parser import parse_doc_anchors

__all__ = ["parse_python_module", "parse_doc_anchors"]
