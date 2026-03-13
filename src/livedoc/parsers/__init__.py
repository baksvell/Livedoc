"""Code and documentation parsers."""

from livedoc.parsers.python_parser import parse_python_module
from livedoc.parsers.typescript_parser import parse_typescript_module
from livedoc.parsers.go_parser import parse_go_module
from livedoc.parsers.doc_parser import parse_doc_anchors

__all__ = ["parse_python_module", "parse_typescript_module", "parse_go_module", "parse_doc_anchors"]
