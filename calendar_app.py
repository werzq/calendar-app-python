import sys
import sqlite3
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QCalendarWidget, QPushButton,
    QLineEdit, QListWidget, QListWidgetItem, QWidget, QMessageBox, QLabel, QComboBox,
    QInputDialog, QSizePolicy
)
from PyQt5.QtCore import Qt

# adapter & converter for DB (unified format of time stored)
def adapt_date(date):
    return date.strftime("%Y-%m-%d").encode("utf-8")

def convert_date(bytestring):
    return datetime.strptime(bytestring.decode("utf-8"), "%Y-%m-%d")

sqlite3.register_adapter(datetime, adapt_date)
sqlite3.register_converter("date", convert_date)

# DB functions (sqlite)
def execute_db_query(query, params=(), fetchone=False, commit=False):
    conn = None
    try:
        conn = sqlite3.connect('calendar_data.db', detect_types=sqlite3.PARSE_DECLTYPES)
        cursor = conn.cursor()
        cursor.execute(query, params)
        
        if commit:
            conn.commit()
        if fetchone:
            return cursor.fetchone()
        return cursor.fetchall()
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return None
    finally:
        if conn:
            conn.close()

def initialize_db():
    create_table_query = '''
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY,
        title TEXT NOT NULL,
        event_date DATE NOT NULL,
        category TEXT
    )
    '''
    execute_db_query(create_table_query, commit=True)

def add_event(title, event_date, category):
    insert_query = '''
    INSERT INTO events (title, event_date, category)
    VALUES (?, ?, ?)
    '''
    execute_db_query(insert_query, (title, event_date, category), commit=True)

def remove_event(event_id):
    delete_query = '''
    DELETE FROM events WHERE id = ?
    '''
    execute_db_query(delete_query, (event_id,), commit=True)

def update_event_title(event_id, new_title):
    update_query = '''
    UPDATE events
    SET title = ?
    WHERE id = ?
    '''
    execute_db_query(update_query, (new_title, event_id), commit=True)

def get_events():
    select_query = 'SELECT * FROM events ORDER BY event_date'
    return execute_db_query(select_query)

# formatting date (1 January, 2000)
def format_date(date):
    return date.strftime('%d %B, %Y')

# class for edit and remove for events
class EventWidget(QWidget):
    def __init__(self, event_title, event_id, category, parent=None):
        super().__init__(parent)
        self.event_title = event_title
        self.event_id = event_id
        self.category = category
        self.parent_app = parent
        
        layout = QHBoxLayout()
        
        title_label = QLabel(f"{event_title} ({category})")
        layout.addWidget(title_label)
        
        # fix for weird button sizes
        button_width = 100
        remove_button = QPushButton('Remove')
        remove_button.setFixedWidth(button_width)
        remove_button.clicked.connect(self.remove_event)
        layout.addWidget(remove_button)
        
        edit_button = QPushButton('Edit')
        edit_button.setFixedWidth(button_width)
        edit_button.clicked.connect(self.edit_event)
        layout.addWidget(edit_button)
        
        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)  # Ensure widget expands horizontally

    def edit_event(self):
        new_title, ok = QInputDialog.getText(self, 'Edit Event', 'New title:', text=self.event_title)
        if ok and new_title:
            update_event_title(self.event_id, new_title)
            self.parent_app.refresh_events()

    def remove_event(self):
        confirm = QMessageBox.question(self, 'Confirm Removal', 'Are you sure you want to remove this event?', QMessageBox.Yes | QMessageBox.No)
        if confirm == QMessageBox.Yes:
            remove_event(self.event_id)
            self.parent_app.refresh_events()

# main class for calendar app window
class CalendarApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Calendar App')

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
        # fix for weird button sizes
        button_width = 120
        self.add_event_button.setFixedWidth(button_width)
        self.add_event_button.clicked.connect(self.add_event)

        self.events_list = QListWidget(self)
        self.events_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)  # Ensure it fills available space

        # better horizontal layout for event input and button
        input_layout = QHBoxLayout()
        input_layout.addWidget(self.event_input)
        input_layout.addWidget(self.category_input)
        input_layout.addWidget(self.add_event_button)
        input_layout.addWidget(self.search_input)

        # main layout of window
        layout = QVBoxLayout()
        layout.addWidget(self.calendar)
        layout.addLayout(input_layout)
        layout.addWidget(self.events_list)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        self.selected_date = self.calendar.selectedDate()
        self.refresh_events()

    def date_selected(self, date):
        self.selected_date = date

    def add_event(self):
        title = self.event_input.text()
        category = self.category_input.currentText()
        event_date = self.selected_date.toString('yyyy-MM-dd')

        if title:
            add_event(title, event_date, category)
            self.event_input.clear()
            QMessageBox.information(self, 'Success', 'Event added successfully')
            self.refresh_events()
        else:
            QMessageBox.warning(self, 'Error', 'Event title is required')

    def refresh_events(self):
        search_text = self.search_input.text().lower()
        events = get_events()

        self.events_list.clear()
        grouped_events = {}
        
        for event in events:
            try:
                event_title = event[1].lower()
                event_date = format_date(event[2])
                category = event[3]
            except IndexError as e:
                print(f"Error processing event {event}: {e}")
                continue

            if search_text in event_title:
                if event_date not in grouped_events:
                    grouped_events[event_date] = []
                grouped_events[event_date].append((event_title, event[0], category))

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
