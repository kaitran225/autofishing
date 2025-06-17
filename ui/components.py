"""
Custom UI components for the AutoFisher application
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QScrollArea, QFrame, QSizePolicy, QToolButton, QGridLayout
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QPropertyAnimation, QEasingCurve, QRect
from PyQt6.QtGui import QIcon, QFont, QColor, QPalette
import qtawesome as qta
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
        self.title = title
        
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
        self.header_layout.setContentsMargins(6, 2, 2, 2)
        
        # Icon (shown in collapsed sidebar mode)
        self.icon_label = QPushButton()
        icon = qta.icon(self.get_icon_name(), color=UI_LIGHT_TEXT)
        self.icon_label.setIcon(icon)
        self.icon_label.setIconSize(QSize(18, 18))
        self.icon_label.setFixedSize(26, 26)
        self.icon_label.setStyleSheet(f"""
            QPushButton {{
                background-color: {UI_WOOD_DARK};
                color: {UI_LIGHT_TEXT};
                border: 1px solid {UI_WOOD_MEDIUM};
                border-radius: 4px;
                padding: 2px;
                margin: 2px 4px;
            }}
            QPushButton:hover {{
                background-color: {UI_WOOD_MEDIUM};
            }}
        """)
        self.icon_label.setToolTip(title)
        self.icon_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.icon_label.clicked.connect(self.toggle_content)
        self.icon_label.hide()
        
        # Title
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet(f"""
            color: {UI_LIGHT_TEXT};
            font-weight: bold;
            font-size: 11pt;
        """)
        
        # Toggle button with Font Awesome icon
        self.toggle_button = QToolButton()
        self.toggle_button.setIcon(qta.icon('fa5s.chevron-right', color=UI_LIGHT_TEXT))
        self.toggle_button.setFixedSize(16, 16)
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
        self.header_layout.addWidget(self.icon_label)
        self.header_layout.addWidget(self.title_label)
        self.header_layout.addStretch()
        self.header_layout.addWidget(self.toggle_button)
        
        # Content widget (container for actual content)
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(4, 4, 4, 4)
        self.content_layout.setSpacing(2)
        
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
            self.toggle_button.setIcon(qta.icon('fa5s.chevron-down', color=UI_LIGHT_TEXT))
            self.header_widget.setStyleSheet(f"""
                QFrame {{
                    background-color: {UI_ACCENT_DARK};
                    border-radius: 3px 3px 0 0;
                }}
            """)
            self.content_widget.setVisible(True)
        else:
            self.toggle_button.setIcon(qta.icon('fa5s.chevron-right', color=UI_LIGHT_TEXT))
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
    
    def get_icon_name(self):
        """Generate a Font Awesome icon name based on the section title"""
        if not self.title:
            return "fa5s.cube"
            
        # Use Font Awesome icons based on common titles
        icon_map = {
            "Settings": "fa5s.cog",
            "Configuration": "fa5s.cog",
            "Config": "fa5s.cog",
            "Options": "fa5s.sliders-h",
            "Detection": "fa5s.eye",
            "Monitor": "fa5s.chart-line",
            "Statistics": "fa5s.chart-bar",
            "Stats": "fa5s.chart-pie",
            "Fishing": "fa5s.fish",
            "Actions": "fa5s.play",
            "Tools": "fa5s.tools",
            "Help": "fa5s.question-circle",
            "Info": "fa5s.info-circle",
            "Log": "fa5s.list",
            "Logs": "fa5s.scroll",
            "Game": "fa5s.gamepad",
            "Region": "fa5s.vector-square",
            "Stream": "fa5s.video",
            "Camera": "fa5s.camera",
            "Control": "fa5s.keyboard"
        }
        
        # Check if title contains any of the keywords
        for keyword, icon in icon_map.items():
            if keyword.lower() in self.title.lower():
                return icon
                
        # Extract the first letter for default case
        first_char = self.title[0].upper()
        
        # If we don't have a specific icon, use a generic one
        return "fa5s.square"

class PopupSection(CollapsibleSection):
    """A section that can slide out from the sidebar"""
    
    # Signal for when popup state changes
    popup_state_changed = pyqtSignal(bool)
    
    def __init__(self, title, parent=None):
        super().__init__(title, parent)
        
        # Add popup button to header
        self.popup_button = QToolButton()
        self.popup_button.setIcon(qta.icon('fa5s.external-link-alt', color=UI_LIGHT_TEXT))
        self.popup_button.setToolTip("Expand section")
        self.popup_button.setFixedSize(16, 16)
        self.popup_button.setStyleSheet(f"""
            QToolButton {{
                background-color: transparent;
                border: none;
            }}
            QToolButton:hover {{
                background-color: {UI_WOOD_LIGHT}33;  /* 20% opacity */
            }}
        """)
        self.popup_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.popup_button.clicked.connect(self.toggle_popup)
        
        # Insert popup button before toggle button
        self.header_layout.insertWidget(self.header_layout.count() - 1, self.popup_button)
        
        # Flag to track popped out state
        self.is_popped_out = False
        
        # Create slide-out container
        self.slide_container = QWidget(self)
        self.slide_container.setVisible(False)
        self.slide_container.setObjectName("slideContainer")
        self.slide_container.setStyleSheet(f"""
            #slideContainer {{
                background-color: {UI_PANEL_BG};
                border: 1px solid {UI_WOOD_DARK};
                border-radius: 4px;
                padding: 4px;
            }}
        """)
        
        # Layout for slide container
        self.slide_layout = QVBoxLayout(self.slide_container)
        self.slide_layout.setContentsMargins(10, 10, 10, 10)
        self.slide_layout.setSpacing(8)
        
        # Animation for slide effect
        self.slide_animation = QPropertyAnimation(self.slide_container, b"geometry")
        self.slide_animation.setDuration(300)
        self.slide_animation.setEasingCurve(QEasingCurve.Type.OutQuad)
            
    def toggle_popup(self):
        """Toggle between normal and slid-out state"""
        if not self.is_popped_out:
            self.pop_out()
        else:
            self.pop_in()
    
    def pop_out(self):
        """Slide out the section"""
        if self.is_popped_out:
            return
            
        # Get parent sidebar (assumes this is in a CollapsibleSidebar)
        sidebar = self.parent()
        while sidebar and not isinstance(sidebar, CollapsibleSidebar):
            sidebar = sidebar.parent()
            
        if not sidebar:
            return
        
        # Move content to slide container
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                self.slide_layout.addWidget(item.widget())
        
        # Position slide container next to sidebar
        sidebar_pos = sidebar.mapToGlobal(sidebar.rect().topRight())
        local_pos = self.mapFromGlobal(sidebar_pos)
        
        # Calculate start and end positions for animation
        start_rect = QRect(local_pos.x(), self.y(), 0, self.height())
        end_rect = QRect(local_pos.x(), self.y(), 350, self.height())
        
        # Set up animation
        self.slide_container.setGeometry(start_rect)
        self.slide_container.setVisible(True)
        self.slide_container.raise_()
        
        self.slide_animation.setStartValue(start_rect)
        self.slide_animation.setEndValue(end_rect)
        self.slide_animation.start()
        
        # Update button state
        self.popup_button.setIcon(qta.icon('fa5s.compress-arrows-alt', color=UI_LIGHT_TEXT))
        self.popup_button.setToolTip("Collapse expanded section")
        
        # Mark section as popped out
        self.is_popped_out = True
        
        # Emit signal that popup state has changed
        self.popup_state_changed.emit(True)
        
    def pop_in(self):
        """Slide the section back in"""
        if not self.is_popped_out:
            return
        
        # Animate slide in
        start_rect = self.slide_container.geometry()
        end_rect = QRect(start_rect.x(), start_rect.y(), 0, start_rect.height())
        
        self.slide_animation.setStartValue(start_rect)
        self.slide_animation.setEndValue(end_rect)
        self.slide_animation.finished.connect(self.finish_pop_in)
        self.slide_animation.start()
        
        # Update button state
        self.popup_button.setIcon(qta.icon('fa5s.external-link-alt', color=UI_LIGHT_TEXT))
        self.popup_button.setToolTip("Expand section")
        
        # Mark as not popped out
        self.is_popped_out = False
        
        # Emit signal that popup state has changed
        self.popup_state_changed.emit(False)
    
    def finish_pop_in(self):
        """Finish the pop-in animation by moving widgets back"""
        # Move content back to original container
        while self.slide_layout.count():
            item = self.slide_layout.takeAt(0)
            if item.widget():
                self.content_layout.addWidget(item.widget())
        
        # Hide slide container
        self.slide_container.setVisible(False)
        
        # Disconnect finished signal to avoid multiple calls
        self.slide_animation.finished.disconnect(self.finish_pop_in)

class CollapsibleSidebar(QWidget):
    """A collapsible sidebar that can be expanded and collapsed"""
    
    collapsed_changed = pyqtSignal(bool)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("collapsibleSidebar")
        self.is_collapsed = True
        self.expanded_width = 200
        self.collapsed_width = 40
        self.animation_duration = 200
        
        # Set up layout 
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(3, 8, 3, 8) 
        self.layout.setSpacing(6)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        
        # Create toggle button with icons - Now floating
        self.toggle_button = QPushButton()
        self.toggle_button.setIcon(qta.icon('fa5s.chevron-left', color=UI_LIGHT_TEXT))
        self.toggle_button.setObjectName("sidebarToggle")
        self.toggle_button.setToolTip("Collapse sidebar")
        self.toggle_button.clicked.connect(self.toggle_collapsed)
        self.toggle_button.setFixedSize(18, 18)
        self.toggle_button.setStyleSheet(f"""
            #sidebarToggle {{
                background-color: {UI_WOOD_DARK};
                color: {UI_LIGHT_TEXT};
                border: none;
                border-radius: 3px;
                padding: 0px;
                position: absolute;
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
        self.sections_layout.setSpacing(8)
        self.sections_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        
        self.scroll_area.setWidget(self.sections_widget)
        
        # Add scroll area to layout (toggle button is now floating)
        self.layout.addWidget(self.scroll_area, 1)
        
        # Set style for the sidebar
        self.setStyleSheet(f"""
            #collapsibleSidebar {{
                background-color: {UI_PANEL_BG};
                border-left: 1px solid {UI_WOOD_DARK};
            }}
        """)
        
        # Store sections for later reference
        self.sections = []
        
        # Set initial minimum width based on collapsed state
        if self.is_collapsed:
            self.setMinimumWidth(self.collapsed_width)
            self.setMaximumWidth(self.collapsed_width)
            self.toggle_button.setIcon(qta.icon('fa5s.chevron-right', color=UI_LIGHT_TEXT))
            self.toggle_button.setToolTip("Expand sidebar")
            self.toggle_button.setMaximumWidth(20)
            # Initialize in icon-only mode
            for section in self.sections:
                if hasattr(section, 'content_widget'):
                    section.content_widget.hide()
                if hasattr(section, 'title_label'):
                    section.title_label.hide()
                if hasattr(section, 'popup_button'):
                    section.popup_button.hide()
                if hasattr(section, 'toggle_button'):
                    section.toggle_button.hide()
                if hasattr(section, 'header_widget'):
                    section.header_widget.hide()
        else:
            self.setMinimumWidth(self.expanded_width)
            self.setMaximumWidth(self.expanded_width)
            
        # Position the toggle button to float at the top right corner
        self.toggle_button.setParent(self)  # Ensure button is direct child of sidebar
        self.toggle_button.show()  # Make sure it's visible
        
    def resizeEvent(self, event):
        """Handle resize events - used to position the floating toggle button"""
        super().resizeEvent(event)
        # Position button at the top right
        self.toggle_button.move(self.width() - self.toggle_button.width() - 3, 8)
    
    def add_section(self, section):
        """Add a collapsible section to the sidebar"""
        self.sections_layout.addWidget(section)
        self.sections.append(section)
        
        # If sidebar is collapsed, set up for icon-only display
        if self.is_collapsed and hasattr(section, 'icon_label'):
            section.icon_label.show()
            if hasattr(section, 'header_widget'):
                section.header_widget.hide()
            if hasattr(section, 'title_label'):
                section.title_label.hide()
                
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
        
        # Connect animation finished signal to update button position
        self.animation.finished.connect(lambda: self.toggle_button.move(self.width() - self.toggle_button.width() - 3, 8))
        
        # Update toggle button
        if self.is_collapsed:
            self.toggle_button.setIcon(qta.icon('fa5s.chevron-right', color=UI_LIGHT_TEXT))
            self.toggle_button.setToolTip("Expand sidebar")
            self.toggle_button.setMaximumWidth(20)
            # Hide all sections content and switch to icon mode
            for section in self.sections:
                if hasattr(section, 'content_widget'):
                    section.content_widget.hide()
                if hasattr(section, 'title_label'):
                    section.title_label.hide()
                if hasattr(section, 'popup_button'):
                    section.popup_button.hide()
                if hasattr(section, 'toggle_button'):
                    section.toggle_button.hide()
                if hasattr(section, 'icon_label'):
                    section.icon_label.show()
                # Hide the header in icon-only mode
                if hasattr(section, 'header_widget'):
                    section.header_widget.hide()
        else:
            self.toggle_button.setIcon(qta.icon('fa5s.chevron-left', color=UI_LIGHT_TEXT))
            self.toggle_button.setToolTip("Collapse sidebar")
            self.toggle_button.setMaximumWidth(16777215)
            # Show all sections content (if expanded)
            for section in self.sections:
                # Show the header widget first
                if hasattr(section, 'header_widget'):
                    section.header_widget.show()
                if hasattr(section, 'title_label'):
                    section.title_label.show()
                if hasattr(section, 'popup_button'):
                    section.popup_button.show()
                if hasattr(section, 'toggle_button'):
                    section.toggle_button.show()
                if hasattr(section, 'content_widget') and section.is_expanded:
                    section.content_widget.show()
                if hasattr(section, 'icon_label'):
                    section.icon_label.hide()
        
        # Emit signal
        self.collapsed_changed.emit(self.is_collapsed) 