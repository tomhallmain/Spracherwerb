import sys
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QSplitter)
from PySide6.QtCore import Qt

from lib.lib.multi_display import SmartMainWindow
from ui.media_frame import MediaFrame
from ui.interaction_panel import InteractionPanel
from ui.config_panel import ConfigPanel
from ui.translations_window import TranslationsWindow
from ui.app_style import AppStyle
from ui.app_actions import AppActions
from utils.app_info_cache import app_info_cache


class MainWindow(SmartMainWindow):
    def __init__(self):
        super().__init__(restore_geometry=True)
        self.setWindowTitle("Spracherwerb")
        self.setMinimumSize(1200, 800)
        
        # Initialize AppActions
        self.app_actions = AppActions(
            # ... other callbacks ...
            open_translations_callback=self.open_translations_window
        )
        
        # Apply global styling
        self.setStyleSheet(AppStyle.get_global_stylesheet())
        self.setPalette(AppStyle.apply_theme_to_palette(self.palette()))
        
        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Create splitter for resizable panels
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #3a3a3a;
            }
        """)
        
        # Create panels
        self.config_panel = ConfigPanel(app_actions=self.app_actions)
        self.media_frame = MediaFrame()
        self.interaction_panel = InteractionPanel()
        
        # Add panels to splitter
        splitter.addWidget(self.config_panel)
        splitter.addWidget(self.media_frame)
        splitter.addWidget(self.interaction_panel)
        
        # Set initial sizes
        splitter.setSizes([250, 600, 350])
        
        # Add splitter to main layout
        main_layout.addWidget(splitter)
        
        # Create toggle button for config panel
        self.toggle_config = QPushButton("◀")
        self.toggle_config.setFixedSize(20, 20)
        self.toggle_config.clicked.connect(self.toggle_config_panel)
        self.toggle_config.setStyleSheet("""
            QPushButton {
                background-color: #2a2a2a;
                color: white;
                border: none;
                border-radius: 0;
            }
            QPushButton:hover {
                background-color: #3a3a3a;
            }
        """)
        
        # Add toggle button to layout
        main_layout.addWidget(self.toggle_config)
    
    def open_translations_window(self):
        """Open the translations window."""
        translations_window = TranslationsWindow(self)
        # Connect config panel's language change signal to translations window
        self.config_panel.languages_changed.connect(translations_window.update_language_display)
        translations_window.show()
    
    def toggle_config_panel(self):
        """Toggle visibility of the configuration panel"""
        if self.config_panel.isVisible():
            self.config_panel.hide()
            self.toggle_config.setText("▶")
        else:
            self.config_panel.show()
            self.toggle_config.setText("◀")
    
    def closeEvent(self, event):
        """Handle window close event - ensure app_info_cache is stored"""
        # Store the cache before closing
        try:
            app_info_cache.store()
        except Exception as e:
            from utils.logging_setup import get_logger
            logger = get_logger(__name__)
            logger.error(f"Error storing app_info_cache on window close: {e}")
        # Call parent closeEvent (which will also store if restore_geometry is enabled)
        super().closeEvent(event)


if __name__ == "__main__":
    # Load app_info_cache at startup (though it's already loaded in __init__, this is explicit)
    try:
        app_info_cache.load()
    except Exception as e:
        from utils.logging_setup import get_logger
        logger = get_logger(__name__)
        logger.warning(f"Error loading app_info_cache at startup: {e}")
    
    app = QApplication(sys.argv)
    
    # Ensure app_info_cache is stored when application is about to quit
    def store_cache_on_quit():
        try:
            app_info_cache.store()
        except Exception as e:
            from utils.logging_setup import get_logger
            logger = get_logger(__name__)
            logger.error(f"Error storing app_info_cache on application quit: {e}")
    
    app.aboutToQuit.connect(store_cache_on_quit)
    
    # Apply global application styling
    app.setStyleSheet(AppStyle.get_global_stylesheet())
    app.setPalette(AppStyle.apply_theme_to_palette(app.palette()))
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec()) 