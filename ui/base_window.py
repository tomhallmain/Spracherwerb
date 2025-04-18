from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QLineEdit, QComboBox, QSlider
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from ui.app_style import AppStyle


class BaseWindow(QMainWindow):
    """Base window class for all secondary windows in the application."""
    
    # Signal emitted when window is closed
    window_closed = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.has_closed = False
        self.row_counter0 = 0
        self.row_counter1 = 0
        
        # Create central widget and main layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QHBoxLayout(self.central_widget)
        
        # Create sidebar and content area
        self.sidebar = QWidget()
        self.sidebar_layout = QVBoxLayout(self.sidebar)
        self.content_area = QWidget()
        self.content_layout = QVBoxLayout(self.content_area)
        
        # Add sidebar and content area to main layout
        self.main_layout.addWidget(self.sidebar)
        self.main_layout.addWidget(self.content_area)
        
        # Set default window properties
        self.setWindowTitle("Spracherwerb")
        self.setMinimumSize(800, 600)
        
        # Apply application styling
        self.setStyleSheet(AppStyle.get_global_stylesheet())
        self.setPalette(AppStyle.apply_theme_to_palette(self.palette()))
        
        # Connect close event
        self.closeEvent = self.on_closing
    
    def on_closing(self, event):
        """Handle window closing event."""
        self.has_closed = True
        self.window_closed.emit()
        event.accept()
    
    def apply_to_grid(self, widget, row=-1, column=0, increment_row_counter=True, 
                     alignment=None, padding=0, column_span=1):
        """Add a widget to the appropriate layout with specified parameters."""
        layout = self.sidebar_layout if column == 0 else self.content_layout
        
        if row == -1:
            row = self.row_counter0 if column == 0 else self.row_counter1
        
        # Set alignment if specified
        if alignment:
            layout.setAlignment(widget, alignment)
        
        # Add widget to layout
        layout.addWidget(widget)
        
        # Add spacing if specified
        if padding > 0:
            layout.addSpacing(padding)
        
        if increment_row_counter:
            if column == 0:
                self.row_counter0 += 1
            else:
                self.row_counter1 += 1
    
    def add_label(self, text, column=0, alignment=Qt.AlignLeft, padding=0, 
                 row=-1, column_span=1, increment_row_counter=True):
        """Create and add a label to the window."""
        label = QLabel(text)
        label.setFont(QFont("Arial", 10))
        self.apply_to_grid(
            label, 
            row=row, 
            column=column, 
            increment_row_counter=increment_row_counter,
            alignment=alignment,
            padding=padding,
            column_span=column_span
        )
        return label
    
    def add_button(self, text, callback, column=0, increment_row_counter=True):
        """Create and add a button to the window."""
        button = QPushButton(text)
        button.clicked.connect(callback)
        self.apply_to_grid(
            button, 
            column=column, 
            increment_row_counter=increment_row_counter
        )
        return button
    
    def add_entry(self, placeholder="", width=55, column=0, **kwargs):
        """Create and add a text entry field to the window."""
        entry = QLineEdit()
        entry.setPlaceholderText(placeholder)
        entry.setFixedWidth(width)
        entry.setFont(QFont("Arial", 10))
        
        # Apply any additional properties
        for key, value in kwargs.items():
            if hasattr(entry, key):
                setattr(entry, key, value)
        
        self.apply_to_grid(entry, column=column)
        return entry
    
    def add_combo_box(self, items, column=0, increment_row_counter=True):
        """Create and add a combo box to the window."""
        combo = QComboBox()
        combo.addItems(items)
        self.apply_to_grid(
            combo, 
            column=column, 
            increment_row_counter=increment_row_counter
        )
        return combo
    
    def add_slider(self, minimum=0, maximum=100, value=50, column=0, 
                  increment_row_counter=True):
        """Create and add a slider to the window."""
        slider = QSlider(Qt.Horizontal)
        slider.setMinimum(minimum)
        slider.setMaximum(maximum)
        slider.setValue(value)
        self.apply_to_grid(
            slider, 
            column=column, 
            increment_row_counter=increment_row_counter
        )
        return slider
    
    def remove_widget(self, widget):
        """Remove a widget from its layout."""
        if widget.parent() == self.sidebar:
            self.sidebar_layout.removeWidget(widget)
        else:
            self.content_layout.removeWidget(widget)
        widget.deleteLater()
        
        # Update row counters
        if widget.parent() == self.sidebar:
            self.row_counter0 -= 1
        else:
            self.row_counter1 -= 1
    
    def clear_layout(self, layout):
        """Clear all widgets from a layout."""
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
    
    def clear_sidebar(self):
        """Clear all widgets from the sidebar."""
        self.clear_layout(self.sidebar_layout)
        self.row_counter0 = 0
    
    def clear_content(self):
        """Clear all widgets from the content area."""
        self.clear_layout(self.content_layout)
        self.row_counter1 = 0

