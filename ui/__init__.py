"""UI package for the Spracherwerb application."""

from ui.app_actions import AppActions
from ui.app_style import AppStyle
from ui.base_window import BaseWindow
from ui.config_panel import ConfigPanel
from ui.gutenberg_search_window import GutenbergSearchWindow
from ui.interaction_panel import InteractionPanel
from ui.media_frame import MediaFrame

__all__ = [
    'AppActions',
    'AppStyle',
    'BaseWindow',
    'ConfigPanel',
    'GutenbergSearchWindow',
    'InteractionPanel',
    'MediaFrame',
]
