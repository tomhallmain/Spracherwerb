import sys
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QSplitter)
from PySide6.QtCore import Qt

from ui.media_frame import MediaFrame
from ui.interaction_panel import InteractionPanel
from ui.config_panel import ConfigPanel
from ui.app_style import AppStyle

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Spracherwerb")
        self.setMinimumSize(1200, 800)
        
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
        self.config_panel = ConfigPanel()
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
    
    def toggle_config_panel(self):
        """Toggle visibility of the configuration panel"""
        if self.config_panel.isVisible():
            self.config_panel.hide()
            self.toggle_config.setText("▶")
        else:
            self.config_panel.show()
            self.toggle_config.setText("◀")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Apply global application styling
    app.setStyleSheet(AppStyle.get_global_stylesheet())
    app.setPalette(AppStyle.apply_theme_to_palette(app.palette()))
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec()) 