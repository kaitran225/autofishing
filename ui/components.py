"""
Custom UI components for the AutoFisher application
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QScrollArea, QFrame, QSizePolicy, QToolButton, QGridLayout
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QPropertyAnimation, QEasingCurve, QRect
from PyQt6.QtGui import QIcon, QFont, QColor, QPalette
from utils.constants import (
    UI_DARK_BG, UI_PANEL_BG, UI_LIGHT_TEXT, UI_SECONDARY_TEXT,
    UI_ACCENT_COLOR, UI_ACCENT_DARK, UI_WOOD_DARK, UI_WOOD_MEDIUM, UI_WOOD_LIGHT
)

class CollapsibleSection(QWidget):
    """A collapsible section for the sidebar"""
    
    toggled = pyqtSignal(bool)  # Signal emitted when section is toggled
    
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setObjectName("collapsibleSection")
        self.setStyleSheet(f"""
            #collapsibleSection {{
                background-color: {UI_PANEL_BG};
                border: 1px solid {UI_WOOD_DARK};
                border-radius: 4px;
                margin: 2px 0px;
            }}
        """)
        
        self.is_expanded = False
        self.animation_duration = 300
        
        # Main layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        # Header widget
        self.header_widget = QFrame()
        self.header_widget.setStyleSheet(f"""
            QFrame {{
                background-color: {UI_WOOD_DARK};
                border-radius: 3px;
            }}
        """)
        self.header_layout = QHBoxLayout(self.header_widget)
        self.header_layout.setContentsMargins(10, 5, 5, 5)
        
        # Title
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet(f"""
            color: {UI_LIGHT_TEXT};
            font-weight: bold;
            font-size: 11pt;
        """)
        
        # Toggle button
        self.toggle_button = QToolButton()
        self.toggle_button.setArrowType(Qt.ArrowType.RightArrow)
        self.toggle_button.setStyleSheet(f"""
            QToolButton {{
                background-color: transparent;
                border: none;
                color: {UI_LIGHT_TEXT};
            }}
            QToolButton:hover {{
                background-color: {UI_WOOD_LIGHT}33;  /* 20% opacity */
            }}
        """)
        self.toggle_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_button.clicked.connect(self.toggle_content)
        
        # Add buttons to header layout
        self.header_layout.addWidget(self.title_label)
        self.header_layout.addStretch()
        self.header_layout.addWidget(self.toggle_button)
        
        # Content widget (container for actual content)
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(8, 8, 8, 8)
        self.content_layout.setSpacing(4)
        
        # Set initial collapsed state
        self.content_widget.setMaximumHeight(0)
        self.content_widget.setVisible(False)
        
        # Add to main layout
        self.main_layout.addWidget(self.header_widget)
        self.main_layout.addWidget(self.content_widget)
        
        # Set cursor for entire header
        self.header_widget.setCursor(Qt.CursorShape.PointingHandCursor)
        self.header_widget.mousePressEvent = self.header_clicked
    
    def header_clicked(self, event):
        """Handle header click to toggle section"""
        self.toggle_content()
        
    def toggle_content(self):
        """Toggle expanded/collapsed state"""
        self.is_expanded = not self.is_expanded
        
        # Update toggle button arrow
        if self.is_expanded:
            self.toggle_button.setArrowType(Qt.ArrowType.DownArrow)
            self.header_widget.setStyleSheet(f"""
                QFrame {{
                    background-color: {UI_ACCENT_DARK};
                    border-radius: 3px 3px 0 0;
                }}
            """)
            self.content_widget.setVisible(True)
        else:
            self.toggle_button.setArrowType(Qt.ArrowType.RightArrow)
            self.header_widget.setStyleSheet(f"""
                QFrame {{
                    background-color: {UI_WOOD_DARK};
                    border-radius: 3px;
                }}
            """)
        
        # Calculate content height
        content_height = self.content_layout.sizeHint().height() if self.is_expanded else 0
        
        # Create animation
        self.animation = QPropertyAnimation(self.content_widget, b"maximumHeight")
        self.animation.setDuration(self.animation_duration)
        self.animation.setStartValue(0 if self.is_expanded else self.content_layout.sizeHint().height())
        self.animation.setEndValue(content_height)
        self.animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        
        # Hide content widget after animation if we're collapsing
        if not self.is_expanded:
            self.animation.finished.connect(lambda: self.content_widget.setVisible(False))
            
        self.animation.start()
        
        # Emit signal
        self.toggled.emit(self.is_expanded)
    
    def add_widget(self, widget):
        """Add a widget to the content layout"""
        self.content_layout.addWidget(widget)
        
    def expand(self):
        """Force expand the section"""
        if not self.is_expanded:
            self.toggle_content()
    
    def collapse(self):
        """Force collapse the section"""
        if self.is_expanded:
            self.toggle_content()

class PopupSection(CollapsibleSection):
    """A section that can pop out into a floating window"""
    
    def __init__(self, title, parent=None):
        super().__init__(title, parent)
        
        # Add popup button to header
        self.popup_button = QToolButton()
        self.popup_button.setText("⇱")  # Unicode for pop-out
        self.popup_button.setToolTip("Detach to separate window")
        self.popup_button.setStyleSheet(f"""
            QToolButton {{
                background-color: transparent;
                border: none;
                color: {UI_LIGHT_TEXT};
                font-size: 12pt;
            }}
            QToolButton:hover {{
                background-color: {UI_WOOD_LIGHT}33;  /* 20% opacity */
            }}
        """)
        self.popup_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.popup_button.clicked.connect(self.toggle_popup)
        
        # Insert popup button before toggle button
        self.header_layout.insertWidget(self.header_layout.count() - 1, self.popup_button)
        
        # Create popup window (initially not shown)
        self.popup_window = None
        self.is_popped_out = False
        
    def toggle_popup(self):
        """Toggle between docked and popped out state"""
        if not self.is_popped_out:
            self.pop_out()
        else:
            self.pop_in()
    
    def pop_out(self):
        """Pop out to separate window"""
        if self.is_popped_out:
            return
            
        # Create popup window if it doesn't exist
        from PyQt6.QtWidgets import QDialog, QVBoxLayout
        
        # Create a new window
        self.popup_window = QDialog(self.parent())
        self.popup_window.setWindowTitle(self.title_label.text())
        self.popup_window.setStyleSheet(f"""
            background-color: {UI_PANEL_BG};
            color: {UI_LIGHT_TEXT};
        """)
        
        # Create layout
        popup_layout = QVBoxLayout(self.popup_window)
        
        # Move content widget to popup
        self.content_widget.setParent(self.popup_window)
        self.content_widget.setVisible(True)
        self.content_widget.setMaximumHeight(16777215)  # Effectively no maximum
        popup_layout.addWidget(self.content_widget)
        
        # Add button to return to sidebar
        dock_button = QPushButton("Return to Sidebar")
        dock_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {UI_WOOD_DARK};
                color: {UI_LIGHT_TEXT};
                border: none;
                border-radius: 4px;
                padding: 6px;
            }}
            QPushButton:hover {{
                background-color: {UI_WOOD_MEDIUM};
            }}
            QPushButton:pressed {{
                background-color: {UI_WOOD_DARK};
            }}
        """)
        dock_button.clicked.connect(self.pop_in)
        popup_layout.addWidget(dock_button)
        
        # Update button state
        self.popup_button.setText("⇲")  # Unicode for pop-in
        self.popup_button.setToolTip("Return to sidebar")
        
        # Mark section as popped out
        self.is_popped_out = True
        
        # Show window
        self.popup_window.setMinimumWidth(300)
        self.popup_window.setMinimumHeight(200)
        self.popup_window.resize(350, 300)
        self.popup_window.show()
        
        # Handle close event
        self.popup_window.closeEvent = self.on_popup_close
        
    def pop_in(self):
        """Return to sidebar"""
        if not self.is_popped_out or not self.popup_window:
            return
            
        # Move content widget back to this widget
        self.content_widget.setParent(self)
        self.main_layout.addWidget(self.content_widget)
        
        # Close and delete the popup window
        self.popup_window.close()
        self.popup_window = None
        
        # Update button state
        self.popup_button.setText("⇱")
        self.popup_button.setToolTip("Detach to separate window")
        
        # Mark as not popped out
        self.is_popped_out = False
        
        # Restore collapsed state if we were not expanded
        if not self.is_expanded:
            self.content_widget.setVisible(False)
            self.content_widget.setMaximumHeight(0)
        else:
            self.content_widget.setVisible(True)
            self.content_widget.setMaximumHeight(16777215)  # Effectively no maximum
    
    def on_popup_close(self, event):
        """Handle popup window close event"""
        self.pop_in()
        event.accept()

class CollapsibleSidebar(QWidget):
    """A collapsible sidebar that can be expanded and collapsed"""
    
    collapsed_changed = pyqtSignal(bool)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("collapsibleSidebar")
        self.is_collapsed = False
        self.expanded_width = 350
        self.collapsed_width = 50
        self.animation_duration = 200
        
        # Set up layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(3, 3, 3, 3)
        self.layout.setSpacing(2)
        
        # Create toggle button
        self.toggle_button = QPushButton("◀")  # Unicode left arrow
        self.toggle_button.setObjectName("sidebarToggle")
        self.toggle_button.setToolTip("Collapse sidebar")
        self.toggle_button.clicked.connect(self.toggle_collapsed)
        self.toggle_button.setStyleSheet(f"""
            #sidebarToggle {{
                background-color: {UI_WOOD_DARK};
                color: {UI_LIGHT_TEXT};
                border: none;
                border-radius: 4px;
                padding: 4px;
                font-size: 12pt;
                font-weight: bold;
            }}
            #sidebarToggle:hover {{
                background-color: {UI_WOOD_MEDIUM};
            }}
        """)
        
        # Create sections container inside scroll area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet(f"""
            QScrollArea {{
                background-color: transparent;
                border: none;
            }}
            QScrollBar:vertical {{
                background-color: {UI_PANEL_BG};
                width: 8px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {UI_WOOD_MEDIUM};
                min-height: 30px;
                border-radius: 4px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)
        
        self.sections_widget = QWidget()
        self.sections_layout = QVBoxLayout(self.sections_widget)
        self.sections_layout.setContentsMargins(0, 0, 0, 0)
        self.sections_layout.setSpacing(5)
        
        self.scroll_area.setWidget(self.sections_widget)
        
        # Add widgets to layout
        self.layout.addWidget(self.toggle_button, 0, Qt.AlignmentFlag.AlignRight)
        self.layout.addWidget(self.scroll_area, 1)
        
        # Set style for the sidebar
        self.setStyleSheet(f"""
            #collapsibleSidebar {{
                background-color: {UI_PANEL_BG};
                border-left: 1px solid {UI_WOOD_DARK};
            }}
        """)
        
        # Set initial minimum width
        self.setMinimumWidth(self.expanded_width)
        self.setMaximumWidth(self.expanded_width)
        
        # Store sections for later reference
        self.sections = []
    
    def add_section(self, section):
        """Add a collapsible section to the sidebar"""
        self.sections_layout.addWidget(section)
        self.sections.append(section)
        return section
    
    def toggle_collapsed(self):
        """Toggle between collapsed and expanded state"""
        self.is_collapsed = not self.is_collapsed
        
        # Create animation for width
        self.animation = QPropertyAnimation(self, b"minimumWidth")
        self.animation.setDuration(self.animation_duration)
        self.animation.setStartValue(self.width())
        self.animation.setEndValue(self.collapsed_width if self.is_collapsed else self.expanded_width)
        self.animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        
        # Create animation for maximum width as well
        self.animation_max = QPropertyAnimation(self, b"maximumWidth")
        self.animation_max.setDuration(self.animation_duration)
        self.animation_max.setStartValue(self.width())
        self.animation_max.setEndValue(self.collapsed_width if self.is_collapsed else self.expanded_width)
        self.animation_max.setEasingCurve(QEasingCurve.Type.InOutQuad)
        
        # Start animations
        self.animation.start()
        self.animation_max.start()
        
        # Update toggle button
        if self.is_collapsed:
            self.toggle_button.setText("▶")  # Unicode right arrow
            self.toggle_button.setToolTip("Expand sidebar")
            # Hide all sections content
            for section in self.sections:
                if hasattr(section, 'content_widget'):
                    section.content_widget.hide()
                if hasattr(section, 'title_label'):
                    section.title_label.hide()
                if hasattr(section, 'popup_button'):
                    section.popup_button.hide()
        else:
            self.toggle_button.setText("◀")  # Unicode left arrow
            self.toggle_button.setToolTip("Collapse sidebar")
            # Show all sections content (if expanded)
            for section in self.sections:
                if hasattr(section, 'title_label'):
                    section.title_label.show()
                if hasattr(section, 'popup_button'):
                    section.popup_button.show()
                if hasattr(section, 'content_widget') and section.is_expanded:
                    section.content_widget.show()
        
        # Emit signal
        self.collapsed_changed.emit(self.is_collapsed) 