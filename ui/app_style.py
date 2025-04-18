from PySide6.QtGui import QColor, QPalette
from PySide6.QtCore import Qt
from utils.config import config

class AppStyle:
    """Application-wide styling configuration for PySide6"""
    
    # Theme configuration
    IS_DARK_THEME = config.enable_dark_mode
    
    # Color definitions
    class Colors:
        # Dark theme colors (using configured colors)
        DARK_BG = config.background_color
        DARK_FG = config.foreground_color
        DARK_ACCENT = "#2a2a2a"  # Slightly lighter than background
        DARK_HIGHLIGHT = "#3a3a3a"  # Even lighter for hover states
        DARK_TEXT = config.foreground_color
        DARK_DISABLED = "#666666"
        
        # Light theme colors (kept as fallback)
        LIGHT_BG = "#ffffff"
        LIGHT_FG = "#000000"
        LIGHT_ACCENT = "#f0f0f0"
        LIGHT_HIGHLIGHT = "#e0e0e0"
        LIGHT_TEXT = "#333333"
        LIGHT_DISABLED = "#999999"
        
        # Common colors
        PRIMARY = "#0078d4"
        SUCCESS = "#107c10"
        WARNING = "#ffb900"
        ERROR = "#d13438"
    
    @classmethod
    def get_theme_colors(cls):
        """Get the current theme's color palette"""
        if cls.IS_DARK_THEME:
            return {
                'bg': cls.Colors.DARK_BG,
                'fg': cls.Colors.DARK_FG,
                'accent': cls.Colors.DARK_ACCENT,
                'highlight': cls.Colors.DARK_HIGHLIGHT,
                'text': cls.Colors.DARK_TEXT,
                'disabled': cls.Colors.DARK_DISABLED
            }
        else:
            return {
                'bg': cls.Colors.LIGHT_BG,
                'fg': cls.Colors.LIGHT_FG,
                'accent': cls.Colors.LIGHT_ACCENT,
                'highlight': cls.Colors.LIGHT_HIGHLIGHT,
                'text': cls.Colors.LIGHT_TEXT,
                'disabled': cls.Colors.LIGHT_DISABLED
            }
    
    @classmethod
    def get_global_stylesheet(cls):
        """Get the global QSS stylesheet for the application"""
        colors = cls.get_theme_colors()
        
        return f"""
            QWidget {{
                background-color: {colors['bg']};
                color: {colors['text']};
            }}
            
            QPushButton {{
                background-color: {colors['accent']};
                color: {colors['text']};
                border: 1px solid {colors['highlight']};
                padding: 5px 10px;
                border-radius: 4px;
            }}
            
            QPushButton:hover {{
                background-color: {colors['highlight']};
            }}
            
            QPushButton:pressed {{
                background-color: {colors['accent']};
            }}
            
            QPushButton:disabled {{
                background-color: {colors['disabled']};
                color: {colors['text']};
            }}
            
            QLineEdit, QTextEdit {{
                background-color: {colors['accent']};
                color: {colors['text']};
                border: 1px solid {colors['highlight']};
                padding: 5px;
                border-radius: 4px;
            }}
            
            QLabel {{
                color: {colors['text']};
            }}
            
            QScrollBar:vertical {{
                background-color: {colors['accent']};
                width: 12px;
                margin: 0px;
            }}
            
            QScrollBar::handle:vertical {{
                background-color: {colors['highlight']};
                min-height: 20px;
                border-radius: 6px;
            }}
            
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            
            QProgressBar {{
                border: 1px solid {colors['highlight']};
                border-radius: 4px;
                text-align: center;
            }}
            
            QProgressBar::chunk {{
                background-color: {cls.Colors.PRIMARY};
            }}
        """
    
    @classmethod
    def apply_theme_to_palette(cls, palette: QPalette):
        """Apply the current theme to a QPalette"""
        colors = cls.get_theme_colors()
        
        palette.setColor(QPalette.Window, QColor(colors['bg']))
        palette.setColor(QPalette.WindowText, QColor(colors['text']))
        palette.setColor(QPalette.Base, QColor(colors['accent']))
        palette.setColor(QPalette.AlternateBase, QColor(colors['highlight']))
        palette.setColor(QPalette.Text, QColor(colors['text']))
        palette.setColor(QPalette.Button, QColor(colors['accent']))
        palette.setColor(QPalette.ButtonText, QColor(colors['text']))
        palette.setColor(QPalette.Link, QColor(cls.Colors.PRIMARY))
        palette.setColor(QPalette.Highlight, QColor(cls.Colors.PRIMARY))
        palette.setColor(QPalette.HighlightedText, QColor(colors['text']))
        
        return palette