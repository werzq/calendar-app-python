import sys
import sqlite3
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QCalendarWidget, QPushButton,
    QLineEdit, QListWidget, QListWidgetItem, QWidget, QMessageBox, QLabel, QComboBox,
    QInputDialog, QSizePolicy, QAction, QDialog, QFormLayout, QCheckBox, QDateEdit
)
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import Qt, QDate, QSize

# Adapter & converter for DB (unified time format)
def adapt_date(date):
    return date.strftime("%Y-%m-%d").encode("utf-8")

def convert_date(bytestring):
    return datetime.strptime(bytestring.decode("utf-8"), "%Y-%m-%d")

sqlite3.register_adapter(datetime, adapt_date)
sqlite3.register_converter("date", convert_date)

# DB functions (sqlite)
def execute_query(query, params=(), fetchone=False, commit=False):
    try:
        with sqlite3.connect('calendar_data.db', detect_types=sqlite3.PARSE_DECLTYPES) as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            if commit:
                conn.commit()
            return cursor.fetchone() if fetchone else cursor.fetchall()
    except sqlite3.Error as e:
        print(f"Database error: {e}")

def initialize_db():
    create_table_query = '''
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY,
        title TEXT NOT NULL,
        event_date DATE NOT NULL,
        category TEXT
    )
    '''
    execute_query(create_table_query, commit=True)

def add_event(title, event_date, category):
    insert_query = '''
    INSERT INTO events (title, event_date, category)
    VALUES (?, ?, ?)
    '''
    execute_query(insert_query, (title, event_date, category), commit=True)

def remove_event(event_id):
    delete_query = '''
    DELETE FROM events WHERE id = ?
    '''
    execute_query(delete_query, (event_id,), commit=True)

def update_event_title(event_id, new_title):
    update_query = '''
    UPDATE events
    SET title = ?
    WHERE id = ?
    '''
    execute_query(update_query, (new_title, event_id), commit=True)

def get_events():
    select_query = 'SELECT * FROM events ORDER BY event_date'
    return execute_query(select_query)

# date formatter (1 January, 2000)
def format_date(date):
    return date.strftime('%d %B, %Y')

# event manager
class EventWidget(QWidget):
    def __init__(self, event_title, event_id, category, parent=None):
        super().__init__(parent)
        self.event_title = event_title
        self.event_id = event_id
        self.category = category
        self.parent_app = parent
        
        layout = QHBoxLayout()
        layout.addWidget(QLabel(f"{event_title} ({category})"))
        
        for text, slot in [('Remove', self.remove_event), ('Edit', self.edit_event)]:
            button = QPushButton(text)
            button.setFixedWidth(100)
            button.clicked.connect(slot)
            layout.addWidget(button)
        
        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)  # Expand horizontally, like our to-do list

    def edit_event(self):
        new_title, ok = QInputDialog.getText(self, 'Edit Event', 'New title:', text=self.event_title)
        if ok and new_title:
            update_event_title(self.event_id, new_title)
            self.parent_app.refresh_events()

    def remove_event(self):
        if QMessageBox.question(self, 'Confirm Removal', 'Are you sure you want to remove this event?', QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            remove_event(self.event_id)
            self.parent_app.refresh_events()

# class for handling Advanced Searches
class AdvancedSearchDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Advanced Search')

        layout = QVBoxLayout(self)

        self.category_checkbox = QCheckBox('Category')
        self.category_input = QComboBox()
        self.category_input.addItems(['Work', 'Personal', 'Education', 'Important', 'Other'])

        self.date_range_checkbox = QCheckBox('Date Range')
        self.from_date_input = QDateEdit(calendarPopup=True)
        self.from_date_input.setDate(QDate.currentDate())
        self.to_date_input = QDateEdit(calendarPopup=True)
        self.to_date_input.setDate(QDate.currentDate())

        form_layout = QFormLayout()
        form_layout.addRow(self.category_checkbox, self.category_input)
        form_layout.addRow(self.date_range_checkbox)
        
        date_layout = QHBoxLayout()
        date_layout.addWidget(QLabel('From:'))
        date_layout.addWidget(self.from_date_input)
        date_layout.addWidget(QLabel('To:'))
        date_layout.addWidget(self.to_date_input)
        form_layout.addRow(date_layout)

        layout.addLayout(form_layout)

        self.apply_button = QPushButton('Apply')
        self.apply_button.clicked.connect(self.apply_filters)
        layout.addWidget(self.apply_button)

        self.filters = {}

    def apply_filters(self):
        self.filters = {}
        if self.category_checkbox.isChecked():
            self.filters['category'] = self.category_input.currentText()
        if self.date_range_checkbox.isChecked():
            self.filters['from_date'] = self.from_date_input.date().toPyDate()
            self.filters['to_date'] = self.to_date_input.date().toPyDate()
        self.accept()

# main class
class CalendarApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Calendar App')
        
        self.toolbar = self.addToolBar('Main Toolbar')
        self.add_toolbar_buttons()

        self.calendar = QCalendarWidget(self)
        self.calendar.setGridVisible(True)
        self.calendar.clicked.connect(self.date_selected)

        self.event_input = QLineEdit(self)
        self.event_input.setPlaceholderText('Event title')

        self.category_input = QComboBox(self)
        self.category_input.addItems(['Work', 'Personal', 'Education', 'Important', 'Other'])

        self.search_input = QLineEdit(self)
        self.search_input.setPlaceholderText('Search events...')
        self.search_input.textChanged.connect(self.refresh_events)

        self.add_event_button = QPushButton('Add Event', self)
        self.add_event_button.setFixedWidth(120)
        self.add_event_button.clicked.connect(self.add_event)

        self.events_list = QListWidget(self)
        self.events_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)  # fix for proper window size

        # better horizontal layout for button and input box
        input_layout = QHBoxLayout()
        for widget in [self.event_input, self.category_input, self.add_event_button, self.search_input]:
            input_layout.addWidget(widget)

        # main window layout
        layout = QVBoxLayout()
        layout.addWidget(self.calendar)
        layout.addLayout(input_layout)
        layout.addWidget(self.events_list)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        self.selected_date = self.calendar.selectedDate()
        self.refresh_events()

    def add_toolbar_buttons(self):
        self.toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.toolbar.setIconSize(QSize(20, 20))

        refresh_action = QAction(QIcon('icons/refresh.png'), 'Refresh', self)
        refresh_action.triggered.connect(self.refresh_events)
        self.toolbar.addAction(refresh_action)

        advanced_search_action = QAction(QIcon('icons/search.png'), 'Advanced Search', self)
        advanced_search_action.triggered.connect(self.show_advanced_search)
        self.toolbar.addAction(advanced_search_action)

        about_action = QAction(QIcon('icons/info.png'), 'About', self)
        about_action.triggered.connect(self.show_about_dialog)
        self.toolbar.addAction(about_action)

    def show_about_dialog(self):
        about_message = """
        <h1 style='text-align: center'>Calendar App</h1>
        <h2>Features</h2>
        <ul>
            <li>Add, edit, and remove events</li>
            <li>Search for events by title</li>
            <li>Advanced search with filters by category and date range</li>
        </ul>
        <hr>
        <h2>Technologies Used</h2>
        <ul>
            <li>Python</li>
            <li>PyQt5</li>
            <li>SQLite</li>
        </ul>
        <p><i>Icons by <b>RemixIcons</b> @ <a href="https://remixicon.com/">https://remixicon.com</a></i></p>
        <hr>
        <p><i>This application is designed to help you manage your events and schedules effectively.</i></p>
        """
        QMessageBox.about(self, 'About Calendar App', about_message)

    def show_advanced_search(self):
        dialog = AdvancedSearchDialog(self)
        if dialog.exec_():
            self.apply_advanced_search(dialog.filters)

    def apply_advanced_search(self, filters):
        events = get_events()
        self.events_list.clear()
        grouped_events = {}

        for event in events:
            event_title, event_date, category = event[1].lower(), event[2].date(), event[3]
            if 'category' in filters and filters['category'] != category:
                continue
            if 'from_date' in filters and event_date < filters['from_date']:
                continue
            if 'to_date' in filters and event_date > filters['to_date']:
                continue
            event_date_str = format_date(event[2])
            grouped_events.setdefault(event_date_str, []).append((event_title, event[0], category))

        for date, titles in grouped_events.items():
            date_item = QListWidgetItem(date)
            date_item.setFlags(date_item.flags() & ~Qt.ItemIsSelectable)
            self.events_list.addItem(date_item)
            for title, event_id, category in titles:
                event_widget = EventWidget(title, event_id, category, self)
                item = QListWidgetItem(self.events_list)
                item.setSizeHint(event_widget.sizeHint())
                self.events_list.setItemWidget(item, event_widget)

    def date_selected(self, date):
        self.selected_date = date

    def add_event(self):
        title = self.event_input.text()
        category = self.category_input.currentText()
        event_date = self.selected_date.toString('yyyy-MM-dd')

        if title:
            add_event(title, event_date, category)
            self.event_input.clear()
            QMessageBox.information(self, 'Success', 'Event added successfully!')
            self.refresh_events()
        else:
            QMessageBox.warning(self, 'Error', 'Event title is required!')

    def refresh_events(self):
        search_text = self.search_input.text().lower()
        events = get_events()

        self.events_list.clear()
        grouped_events = {}

        for event in events:
            try:
                event_title, event_date, category = event[1].lower(), format_date(event[2]), event[3]
                if search_text in event_title:
                    grouped_events.setdefault(event_date, []).append((event_title, event[0], category))
            except IndexError as e:
                print(f"Error processing event {event}: {e}")

        for date, titles in grouped_events.items():
            date_item = QListWidgetItem(date)
            date_item.setFlags(date_item.flags() & ~Qt.ItemIsSelectable)
            self.events_list.addItem(date_item)
            for title, event_id, category in titles:
                event_widget = EventWidget(title, event_id, category, self)
                item = QListWidgetItem(self.events_list)
                item.setSizeHint(event_widget.sizeHint())
                self.events_list.setItemWidget(item, event_widget)

# main entry point
if __name__ == '__main__':
    initialize_db()
    app = QApplication(sys.argv)
    window = CalendarApp()
    window.show()
    sys.exit(app.exec_())