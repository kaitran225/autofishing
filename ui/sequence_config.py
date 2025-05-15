"""
Fishing sequence configuration dialog
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QSpinBox, QDoubleSpinBox, QGridLayout, QGroupBox, QListWidget,
    QListWidgetItem, QMessageBox, QTabWidget, QWidget
)
from PyQt6.QtCore import Qt, pyqtSignal
from typing import Dict, List, Any


class ActionItem(QListWidgetItem):
    """Custom list widget item for representing fishing actions"""
    
    def __init__(self, action_data: Dict[str, Any]):
        self.action_data = action_data
        display_text = self._format_display_text(action_data)
        super().__init__(display_text)
        
    def _format_display_text(self, action_data: Dict[str, Any]) -> str:
        """Format the display text based on action type"""
        action_type = action_data.get("action", "")
        
        if action_type == "press":
            key = action_data.get("key", "").upper()
            delay = action_data.get("delay", 0.0)
            return f"Press {key} key" + (f" (delay: {delay}s)" if delay > 0 else "")
            
        elif action_type == "wait":
            delay = action_data.get("delay", 1.0)
            return f"Wait {delay} seconds"
            
        elif action_type == "watch":
            delay = action_data.get("delay", 30.0)
            return f"Watch for bite (max {delay}s)"
            
        return "Unknown action"
        
    def update_display(self):
        """Update the display text after changes"""
        self.setText(self._format_display_text(self.action_data))


class SequenceConfigDialog(QDialog):
    """Dialog for configuring the fishing action sequence"""
    
    sequence_updated = pyqtSignal(list)
    
    def __init__(self, parent=None, current_sequence=None):
        super().__init__(parent)
        
        # Initialize with default sequence if none provided
        self.action_sequence = current_sequence or []
        
        # Setup UI
        self.setWindowTitle("Fishing Sequence Configuration")
        self.resize(600, 400)
        
        # Apply parent's theme if available
        if parent and hasattr(parent, "colors"):
            self.colors = parent.colors
            self._apply_theme()
        else:
            # Default colors if parent theme not available
            self.colors = {
                'bg_dark': '#1E1E1E',
                'bg_medium': '#252526',
                'bg_light': '#2D2D30',
                'text': '#E0E0E0',
                'highlight': '#4CAF50',
                'button_bg': '#3E3E3E',
                'border': '#555555',
            }
            self._apply_theme()
            
        # Create tabs
        self.tab_widget = QTabWidget()
        
        # Sequence editor tab
        self.editor_tab = QWidget()
        self._setup_editor_tab()
        
        # Presets tab
        self.presets_tab = QWidget()
        self._setup_presets_tab()
        
        # Help tab
        self.help_tab = QWidget()
        self._setup_help_tab()
        
        # Add tabs to widget
        self.tab_widget.addTab(self.editor_tab, "Sequence Editor")
        self.tab_widget.addTab(self.presets_tab, "Presets")
        self.tab_widget.addTab(self.help_tab, "Help")
        
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(self.tab_widget)
        
        # Button layout
        button_layout = QHBoxLayout()
        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self.save_sequence)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.cancel_button)
        
        main_layout.addLayout(button_layout)
        
        # Populate the sequence if provided
        self._populate_sequence_list()
        
    def _apply_theme(self):
        """Apply theme colors to dialog"""
        self.setStyleSheet(f"""
            QDialog {{ background-color: {self.colors['bg_dark']}; color: {self.colors['text']}; }}
            QLabel {{ color: {self.colors['text']}; }}
            QPushButton {{ 
                background-color: {self.colors['button_bg']}; 
                color: {self.colors['text']}; 
                border: 1px solid {self.colors['border']};
                padding: 5px;
                border-radius: 3px;
            }}
            QPushButton:hover {{ background-color: {self.colors['bg_light']}; }}
            QListWidget, QComboBox, QSpinBox, QDoubleSpinBox {{
                background-color: {self.colors['bg_medium']};
                color: {self.colors['text']};
                border: 1px solid {self.colors['border']};
            }}
            QGroupBox {{ 
                border: 1px solid {self.colors['border']}; 
                margin-top: 10px; 
                padding-top: 15px;
            }}
            QGroupBox::title {{ 
                color: {self.colors['text']}; 
                subcontrol-origin: margin; 
                left: 10px; 
            }}
            QTabWidget::pane {{ 
                border: 1px solid {self.colors['border']}; 
                background-color: {self.colors['bg_medium']}; 
            }}
            QTabBar::tab {{ 
                background-color: {self.colors['bg_medium']}; 
                color: {self.colors['text']}; 
                padding: 6px 10px; 
                border: 1px solid {self.colors['border']}; 
                border-bottom: none; 
                border-top-left-radius: 4px; 
                border-top-right-radius: 4px; 
            }}
            QTabBar::tab:selected {{ 
                background-color: {self.colors['bg_light']}; 
                border-bottom: none; 
            }}
        """)
        
    def _setup_editor_tab(self):
        """Setup the sequence editor tab"""
        layout = QVBoxLayout(self.editor_tab)
        
        # Sequence display
        sequence_group = QGroupBox("Action Sequence")
        sequence_layout = QVBoxLayout(sequence_group)
        
        self.sequence_list = QListWidget()
        self.sequence_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.sequence_list.itemSelectionChanged.connect(self._update_action_form)
        
        sequence_layout.addWidget(self.sequence_list)
        
        # Button bar
        sequence_buttons = QHBoxLayout()
        
        self.add_action_button = QPushButton("Add")
        self.add_action_button.clicked.connect(self._add_action)
        
        self.edit_action_button = QPushButton("Edit")
        self.edit_action_button.clicked.connect(self._edit_action)
        self.edit_action_button.setEnabled(False)
        
        self.remove_action_button = QPushButton("Remove")
        self.remove_action_button.clicked.connect(self._remove_action)
        self.remove_action_button.setEnabled(False)
        
        self.move_up_button = QPushButton("Move Up")
        self.move_up_button.clicked.connect(self._move_action_up)
        self.move_up_button.setEnabled(False)
        
        self.move_down_button = QPushButton("Move Down")
        self.move_down_button.clicked.connect(self._move_action_down)
        self.move_down_button.setEnabled(False)
        
        sequence_buttons.addWidget(self.add_action_button)
        sequence_buttons.addWidget(self.edit_action_button)
        sequence_buttons.addWidget(self.remove_action_button)
        sequence_buttons.addWidget(self.move_up_button)
        sequence_buttons.addWidget(self.move_down_button)
        
        sequence_layout.addLayout(sequence_buttons)
        
        # Action editor
        action_group = QGroupBox("Action Editor")
        action_layout = QGridLayout(action_group)
        
        # Action type
        action_layout.addWidget(QLabel("Action Type:"), 0, 0)
        self.action_type_combo = QComboBox()
        self.action_type_combo.addItems(["press", "wait", "watch"])
        self.action_type_combo.currentTextChanged.connect(self._update_form_for_action_type)
        action_layout.addWidget(self.action_type_combo, 0, 1)
        
        # Key (for press action)
        action_layout.addWidget(QLabel("Key:"), 1, 0)
        self.key_combo = QComboBox()
        self.key_combo.addItems(["f", "esc", "space", "enter", "1", "2", "3", "4", "5"])
        self.key_combo.setEditable(True)
        action_layout.addWidget(self.key_combo, 1, 1)
        
        # Delay
        action_layout.addWidget(QLabel("Delay (seconds):"), 2, 0)
        self.delay_spin = QDoubleSpinBox()
        self.delay_spin.setRange(0.0, 60.0)
        self.delay_spin.setSingleStep(0.5)
        self.delay_spin.setValue(1.0)
        action_layout.addWidget(self.delay_spin, 2, 1)
        
        # Apply button
        self.apply_action_button = QPushButton("Apply Changes")
        self.apply_action_button.clicked.connect(self._apply_action_changes)
        self.apply_action_button.setEnabled(False)
        action_layout.addWidget(self.apply_action_button, 3, 0, 1, 2)
        
        # Add to layout
        layout.addWidget(sequence_group)
        layout.addWidget(action_group)
        
        # Initialize form for default action type
        self._update_form_for_action_type("press")
        
    def _setup_presets_tab(self):
        """Setup the presets tab"""
        layout = QVBoxLayout(self.presets_tab)
        
        # Preset options
        presets_group = QGroupBox("Preset Sequences")
        presets_layout = QVBoxLayout(presets_group)
        
        # Basic preset
        basic_btn = QPushButton("Basic Fishing (Cast → Wait → Catch → Close)")
        basic_btn.clicked.connect(lambda: self._load_preset("basic"))
        
        # Advanced preset
        advanced_btn = QPushButton("Advanced (Cast → Watch for bite → Catch → Collect → Wait)")
        advanced_btn.clicked.connect(lambda: self._load_preset("advanced"))
        
        # Quick preset
        quick_btn = QPushButton("Quick Fishing (Faster timing)")
        quick_btn.clicked.connect(lambda: self._load_preset("quick"))
        
        presets_layout.addWidget(basic_btn)
        presets_layout.addWidget(advanced_btn)
        presets_layout.addWidget(quick_btn)
        presets_layout.addStretch()
        
        layout.addWidget(presets_group)
        layout.addStretch()
        
    def _setup_help_tab(self):
        """Setup the help tab"""
        layout = QVBoxLayout(self.help_tab)
        
        help_label = QLabel("""
        <h3>Fishing Sequence Help</h3>
        
        <p>The fishing sequence consists of a series of actions that will be executed
        when a fish is detected. Each action has a type and parameters:</p>
        
        <ul>
            <li><b>press</b>: Simulates pressing a key on the keyboard
                <ul>
                    <li>Key: The key to press (e.g., f, esc, space)</li>
                    <li>Delay: Time to wait after pressing the key</li>
                </ul>
            </li>
            <li><b>wait</b>: Pauses the sequence for a specified time
                <ul>
                    <li>Delay: Number of seconds to wait</li>
                </ul>
            </li>
            <li><b>watch</b>: Waits for a fish bite for up to the specified time
                <ul>
                    <li>Delay: Maximum time to wait for fish bite</li>
                </ul>
            </li>
        </ul>
        
        <p>Example sequence:</p>
        <ol>
            <li>Press F key (to cast the fishing rod)</li>
            <li>Wait 3 seconds</li>
            <li>Watch for bite (max 30 seconds)</li>
            <li>Press F key (to catch the fish)</li>
            <li>Wait 3 seconds</li>
            <li>Press ESC key (to close dialog)</li>
            <li>Wait 2 seconds</li>
        </ol>
        """)
        
        help_label.setWordWrap(True)
        help_label.setTextFormat(Qt.TextFormat.RichText)
        help_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        layout.addWidget(help_label)
        
    def _update_action_form(self):
        """Update action form based on selected action"""
        selected_items = self.sequence_list.selectedItems()
        
        if not selected_items:
            self.edit_action_button.setEnabled(False)
            self.remove_action_button.setEnabled(False)
            self.move_up_button.setEnabled(False)
            self.move_down_button.setEnabled(False)
            self.apply_action_button.setEnabled(False)
            return
            
        # Enable buttons
        self.edit_action_button.setEnabled(True)
        self.remove_action_button.setEnabled(True)
        
        # Enable/disable move buttons based on position
        current_row = self.sequence_list.row(selected_items[0])
        self.move_up_button.setEnabled(current_row > 0)
        self.move_down_button.setEnabled(current_row < self.sequence_list.count() - 1)
        
        # Fill form with selected action data
        selected_item = selected_items[0]
        if isinstance(selected_item, ActionItem):
            action_data = selected_item.action_data
            
            # Set action type
            action_type = action_data.get("action", "press")
            self.action_type_combo.setCurrentText(action_type)
            
            # Set key (for press action)
            if action_type == "press":
                key = action_data.get("key", "")
                if key in [self.key_combo.itemText(i) for i in range(self.key_combo.count())]:
                    self.key_combo.setCurrentText(key)
                else:
                    self.key_combo.setCurrentText("")
                    
            # Set delay
            delay = action_data.get("delay", 1.0)
            self.delay_spin.setValue(delay)
            
            # Enable apply button
            self.apply_action_button.setEnabled(True)
            
    def _update_form_for_action_type(self, action_type):
        """Update form fields based on the selected action type"""
        # Show/hide fields based on action type
        self.key_combo.setVisible(action_type == "press")
        self.key_combo.setEnabled(action_type == "press")
        
    def _populate_sequence_list(self):
        """Populate the sequence list with current actions"""
        self.sequence_list.clear()
        
        for action_data in self.action_sequence:
            item = ActionItem(action_data)
            self.sequence_list.addItem(item)
            
    def _add_action(self):
        """Add a new action to the sequence"""
        # Create action data based on form values
        action_type = self.action_type_combo.currentText()
        action_data = {
            "action": action_type,
            "delay": self.delay_spin.value()
        }
        
        # Add key for press action
        if action_type == "press":
            action_data["key"] = self.key_combo.currentText()
            
        # Add to list
        item = ActionItem(action_data)
        self.sequence_list.addItem(item)
        
        # Update internal sequence
        self._update_sequence_from_list()
        
    def _edit_action(self):
        """Edit the selected action"""
        # Enable form for editing
        self.apply_action_button.setEnabled(True)
        
    def _apply_action_changes(self):
        """Apply changes to the selected action"""
        selected_items = self.sequence_list.selectedItems()
        if not selected_items:
            return
            
        selected_item = selected_items[0]
        if not isinstance(selected_item, ActionItem):
            return
            
        # Update action data
        action_type = self.action_type_combo.currentText()
        selected_item.action_data["action"] = action_type
        selected_item.action_data["delay"] = self.delay_spin.value()
        
        # Update key for press action
        if action_type == "press":
            selected_item.action_data["key"] = self.key_combo.currentText()
        elif "key" in selected_item.action_data:
            del selected_item.action_data["key"]
            
        # Update display
        selected_item.update_display()
        
        # Update internal sequence
        self._update_sequence_from_list()
        
    def _remove_action(self):
        """Remove the selected action"""
        selected_items = self.sequence_list.selectedItems()
        if not selected_items:
            return
            
        # Remove from list
        row = self.sequence_list.row(selected_items[0])
        self.sequence_list.takeItem(row)
        
        # Update internal sequence
        self._update_sequence_from_list()
        
    def _move_action_up(self):
        """Move the selected action up in the sequence"""
        selected_items = self.sequence_list.selectedItems()
        if not selected_items:
            return
            
        current_row = self.sequence_list.row(selected_items[0])
        if current_row <= 0:
            return
            
        # Move item
        item = self.sequence_list.takeItem(current_row)
        self.sequence_list.insertItem(current_row - 1, item)
        self.sequence_list.setCurrentItem(item)
        
        # Update internal sequence
        self._update_sequence_from_list()
        
    def _move_action_down(self):
        """Move the selected action down in the sequence"""
        selected_items = self.sequence_list.selectedItems()
        if not selected_items:
            return
            
        current_row = self.sequence_list.row(selected_items[0])
        if current_row >= self.sequence_list.count() - 1:
            return
            
        # Move item
        item = self.sequence_list.takeItem(current_row)
        self.sequence_list.insertItem(current_row + 1, item)
        self.sequence_list.setCurrentItem(item)
        
        # Update internal sequence
        self._update_sequence_from_list()
        
    def _update_sequence_from_list(self):
        """Update internal sequence from list widget items"""
        self.action_sequence = []
        
        for i in range(self.sequence_list.count()):
            item = self.sequence_list.item(i)
            if isinstance(item, ActionItem):
                self.action_sequence.append(item.action_data)
                
    def _load_preset(self, preset_name):
        """Load a preset sequence"""
        if preset_name == "basic":
            self.action_sequence = [
                {"action": "press", "key": "f", "delay": 0.0},
                {"action": "wait", "delay": 3.0},
                {"action": "press", "key": "f", "delay": 0.5},
                {"action": "wait", "delay": 2.0},
                {"action": "press", "key": "esc", "delay": 0.5},
                {"action": "wait", "delay": 1.0},
            ]
        elif preset_name == "advanced":
            self.action_sequence = [
                {"action": "press", "key": "f", "delay": 0.0},
                {"action": "wait", "delay": 3.0},
                {"action": "watch", "delay": 30.0},
                {"action": "press", "key": "f", "delay": 0.5},
                {"action": "wait", "delay": 3.0},
                {"action": "press", "key": "esc", "delay": 0.5},
                {"action": "wait", "delay": 2.0},
            ]
        elif preset_name == "quick":
            self.action_sequence = [
                {"action": "press", "key": "f", "delay": 0.0},
                {"action": "wait", "delay": 1.5},
                {"action": "watch", "delay": 20.0},
                {"action": "press", "key": "f", "delay": 0.3},
                {"action": "wait", "delay": 1.5},
                {"action": "press", "key": "esc", "delay": 0.3},
                {"action": "wait", "delay": 1.0},
            ]
            
        # Update UI
        self._populate_sequence_list()
        
        # Switch to editor tab
        self.tab_widget.setCurrentIndex(0)
        
    def save_sequence(self):
        """Save the configured sequence and close dialog"""
        if not self.action_sequence:
            QMessageBox.warning(self, "Empty Sequence", 
                               "The fishing sequence cannot be empty. Please add at least one action.")
            return
            
        # Emit signal with updated sequence
        self.sequence_updated.emit(self.action_sequence)
        
        # Accept dialog (close with success)
        self.accept() 