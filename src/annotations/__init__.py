"""Unified annotation data models, renderer, and editor utilities."""

from .editor import (
    cursor_for_handle,
    get_handle_names,
    get_handles,
    handle_at_pos,
    hit_test,
    selection_bounds,
)
from .models import Annotation
from .renderer import AnnotationRenderer, SourceProvider

__all__ = [
    "Annotation",
    "AnnotationRenderer",
    "SourceProvider",
    "cursor_for_handle",
    "get_handle_names",
    "get_handles",
    "handle_at_pos",
    "hit_test",
    "selection_bounds",
]
