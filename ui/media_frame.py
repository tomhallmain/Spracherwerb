import os
import platform
from enum import Enum, auto
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPixmap, QImage
import vlc

class MediaType(Enum):
    """Enumeration of supported media types"""
    NONE = auto()
    IMAGE = auto()
    VIDEO = auto()

class MediaFrame(QWidget):
    """Display area for generated images and videos"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(400, 400)
        self.setStyleSheet("background-color: #2a2a2a;")
        
        # Create layout
        layout = QVBoxLayout(self)
        self.setLayout(layout)
        
        # Image display area
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("background-color: #1a1a1a;")
        layout.addWidget(self.image_label)
        
        # VLC player setup
        self.vlc_instance = vlc.Instance()
        self.vlc_media_player = self.vlc_instance.media_player_new()
        self.vlc_media = None
        self.current_media_type = MediaType.NONE
        
    def display_image(self, image_path):
        """Display an image in the media frame"""
        if not os.path.exists(image_path):
            self.image_label.setText("Image not found")
            return
            
        # Stop any playing video
        if self.current_media_type == MediaType.VIDEO:
            self.vlc_media_player.stop()
            
        # Load and display image
        pixmap = QPixmap(image_path)
        scaled_pixmap = pixmap.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.image_label.setPixmap(scaled_pixmap)
        self.current_media_type = MediaType.IMAGE
        
    def display_video(self, video_path):
        """Display a video in the media frame"""
        if not os.path.exists(video_path):
            self.image_label.setText("Video not found")
            return
            
        # Clear any displayed image
        self.image_label.clear()
        
        # Set up VLC player
        self.vlc_media = self.vlc_instance.media_new(video_path)
        self.vlc_media_player.set_media(self.vlc_media)
        
        # Set the window ID where to render VLC's video output
        if platform.system() == 'Windows':
            self.vlc_media_player.set_hwnd(self.winId())
        else:
            self.vlc_media_player.set_xwindow(self.winId())
            
        # Start playback
        if self.vlc_media_player.play() == -1:
            self.image_label.setText("Failed to play video")
            return
            
        self.current_media_type = MediaType.VIDEO
        
    def clear(self):
        """Clear the media frame"""
        if self.current_media_type == MediaType.VIDEO:
            self.vlc_media_player.stop()
        self.image_label.clear()
        self.current_media_type = MediaType.NONE
        
    def resizeEvent(self, event):
        """Handle window resize events"""
        super().resizeEvent(event)
        if self.current_media_type == MediaType.IMAGE and self.image_label.pixmap():
            # Rescale the image to fit the new size
            pixmap = self.image_label.pixmap()
            scaled_pixmap = pixmap.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.image_label.setPixmap(scaled_pixmap)
            
    def closeEvent(self, event):
        """Clean up resources when closing"""
        if self.current_media_type == MediaType.VIDEO:
            self.vlc_media_player.stop()
        super().closeEvent(event)
