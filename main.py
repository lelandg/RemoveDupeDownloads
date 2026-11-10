import os
import re
import shutil
import sys
import traceback
from datetime import datetime

from PySide6.QtCore import Qt, QSettings, QPoint, QSize
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QPushButton,
    QLineEdit, QLabel, QWidget, QSizePolicy, QTextEdit, QTableWidgetItem, QHeaderView,
    QTableWidget, QFileDialog
)


def get_modification_time(file_path):
    try:
        # Get the modification time as a timestamp
        mod_time = os.path.getmtime(file_path)

        # Convert the timestamp to a readable format
        readable_time = datetime.fromtimestamp(mod_time).strftime('%Y-%m-%d %H:%M:%S')
        return readable_time
    except FileNotFoundError:
        return f"File not found: {file_path}"
    except Exception as e:
        return f"Error getting modification time: {str(e)}"


class DuplicateFileDeleter(QMainWindow):
    def __init__(self):
        super().__init__()

        # Initialize settings
        self.settings = QSettings("DuplicateFileDeleter", "AppSettings")

        # Restore window size and position from settings
        self.resize(self.settings.value("windowSize", QSize(600, 400)))
        self.move(self.settings.value("windowPosition", QPoint(100, 100)))

        # Main widget and layout
        widget = QWidget()
        self.setCentralWidget(widget)
        main_layout = QVBoxLayout()

        # Label at the top
        self.label = QLabel("Delete Duplicate Downloads")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.label)

        # Folder browse layout
        browse_layout = QHBoxLayout()
        self.folder_line_edit = QLineEdit()
        self.folder_line_edit.setPlaceholderText("Select a folder...")
        browse_layout.addWidget(self.folder_line_edit)

        self.browse_button = QPushButton("Browse")
        self.browse_button.clicked.connect(self.browse_folder)
        browse_layout.addWidget(self.browse_button)

        main_layout.addLayout(browse_layout)

        # Results (matched files) listbox
        self.file_listbox = QTableWidget()
        self.file_listbox.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        # Connect signal to slot
        self.file_listbox.itemClicked.connect(self.highlight_entire_row)

        main_layout.addWidget(self.file_listbox)

        # Setting up the File Listbox as a table:
        self.file_listbox.setColumnCount(4)
        self.file_listbox.setHorizontalHeaderLabels(["Folder", "File Name", "Size", "Date Modified"])
        self.file_listbox.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.file_listbox.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.file_listbox.cellEntered.connect(self.show_tooltip)

        # Manually set fixed widths for "File Size" and "Date Modified" columns
        file_size_column_index = 2  # Assuming 'File Size' is the third column
        date_modified_column_index = 3  # Assuming 'Date Modified' is the fourth column
        self.file_listbox.setColumnWidth(file_size_column_index, 100)  # Set width (e.g., 100 pixels)
        self.file_listbox.setColumnWidth(date_modified_column_index, 150)  # Set width (e.g., 150 pixels)

        # Enable resizable columns
        header = self.file_listbox.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)  # Allows resizing via mouse
        header.setStretchLastSection(True)  # Optional: Stretch the last column to fill space

        # Delete button
        self.delete_button = QPushButton("Delete")
        self.delete_button.clicked.connect(self.delete_files)
        main_layout.addWidget(self.delete_button)

        self.status_window = QTextEdit()
        # Setting up the Status Window
        self.status_window.setReadOnly(True)
        self.status_window.setFixedHeight(200)  # Allow 10 lines of text visibility
        self.status_window.setContentsMargins(10, 10, 10, 10)
        main_layout.addWidget(self.status_window)

        # Set layout
        widget.setLayout(main_layout)

        # Restore GUI contents from settings
        self.total_file_size = 0
        self.restore_settings()
        if self.folder_line_edit.text():
            self.list_files(self.folder_line_edit.text(), r".* \(\d+\)$")

    def highlight_entire_row(self, clicked_item):
        """
        Slot: Called when an item is clicked.
        Ensures all items in the row are selected when one is clicked.
        """
        try:
            # Determine the index of the clicked item
            clicked_row = self.get_row_of_item(clicked_item)

            if clicked_row is not None:
                # Select all items in the same row
                row_items = self.get_items_in_row(clicked_row)
                for item in row_items:
                    if item:  # Ensure the item is not None
                        item.setSelected(True)
        except Exception as e:
            print(f"Error highlighting row: {str(e)}")
            print(traceback.format_exc())

    def get_row_of_item(self, item):
        """
        Given a clicked item, determine which row it belongs to based on its index.
        Assume 3 items per row (can be changed based on your logic).
        """
        print(f"Clicked item: {item.text()}")
        row = self.file_listbox.row(item)
        print(f"Row: {row}")
        return row

    def get_items_in_row(self, row):
        """
        Get all items in a given row.
        :param row: int, the row index to retrieve items from.
        :return: list of QTableWidgetItem objects in the given row.
        """
        items_per_row = self.file_listbox.columnCount()  # Number of columns in the table
        return [self.file_listbox.item(row, col) for col in range(items_per_row)]

    def show_tooltip(self, row, column):
        """
        Display tooltip with the content of the hovered cell.
        """
        if self.file_listbox.item(row, column):  # Check if an item exists in the cell
            # Get the item and set its tooltip with the cell content
            item = self.file_listbox.item(row, column)
            item.setToolTip(item.text())

    def browse_folder(self):
        # Open a folder selection dialog and set the selected folder to `self.folder_line_edit`
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        if not folder_path:  # If no folder is selected, stop execution
            self.status_window.append("No folder selected. Please try again.")
            return

        # Update the line edit widget with the selected folder path
        self.folder_line_edit.setText(folder_path)

        # Continue with the existing functionality
        if not os.path.isdir(folder_path):
            self.status_window.append("Invalid folder path. Please select a valid directory.")
            return

        self.status_window.clear()
        self.file_listbox.setRowCount(0)  # Reset the table
        self.total_file_size = 0

        self.status_window.append(f"Scanning folder: {folder_path}")
        self.list_files(folder_path, r".* \(\d+\)$")

        self.status_window.append(f"Scanning complete.\nTotal Size: {self.format_size(self.total_file_size)}")

    def list_files(self, folder_path, pattern=r".* \(\d+\)$"):
        self.deleted_folder = os.path.join(folder_path, "Deleted")
        self.status_window.append(f"Scanning folder: {folder_path}")
        self.status_window.update()
        pattern = re.compile(pattern)  # Regex to match files ending with ' (#)' where # is one or more digits
        for root, dirs, files in os.walk(folder_path):
            if root.endswith("Deleted"):  # Skip the "Deleted" folder
                continue
            for file in files:
                if not pattern.match(os.path.splitext(file)[0]):  # Check the base name (without extension)
                    continue

                file_path = os.path.join(root, file)
                try:
                    file_size = os.path.getsize(file_path)
                except Exception as e:
                    self.status_window.append(f"Error reading file: {file_path}. {str(e)}")
                    continue

                # Update Listbox with file name and size:
                row_position = self.file_listbox.rowCount()
                self.file_listbox.insertRow(row_position)
                folder_item = QTableWidgetItem(root)
                self.file_listbox.setItem(row_position, 0, folder_item)
                folder_item.setToolTip(root)

                file_item = QTableWidgetItem(file)
                self.file_listbox.setItem(row_position, 1, file_item)
                file_item.setToolTip(file)

                # file_size = self.format_size(file_size)
                self.file_listbox.setItem(row_position, 2, QTableWidgetItem(self.format_size(file_size)))
                modification_time = get_modification_time(file_path)
                time_item = QTableWidgetItem(modification_time)
                self.file_listbox.setItem(row_position, 3, time_item)
                time_item.setToolTip(modification_time)

                # Accumulate total size
                self.total_file_size += file_size

        # Update status on completion
        self.status_window.append(f"Total Files Scanned: {self.file_listbox.rowCount()}")

        # Ensure that the file_listbox is populated (assuming it's a QTableWidget)
        if not self.file_listbox.rowCount():
            return

        # Dynamically resize "File Name" column to fit the content
        file_name_column_index = 0  # Assuming 'File Name' is the first column
        self.file_listbox.horizontalHeader().setSectionResizeMode(file_name_column_index, QHeaderView.ResizeMode.ResizeToContents)

        # Dynamically resize "Folder" column to fit remaining window space
        folder_column_index = 1  # Assuming 'Folder' is the second column
        self.file_listbox.horizontalHeader().setSectionResizeMode(folder_column_index, QHeaderView.ResizeMode.Stretch)

        # Optional: Adjust the table widget to refresh and display properly
        self.file_listbox.resizeColumnsToContents()


    def format_size(self, size_in_bytes):
        """Helper function to format file sizes into KB, MB, etc."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_in_bytes < 1024.0:
                return f"{size_in_bytes:.2f} {unit}"
            size_in_bytes /= 1024.0
        return f"{size_in_bytes:.2f} PB"

    def get_file_paths_from_listbox(self):
        file_paths = []
        for row in range(self.file_listbox.rowCount()):  # Iterate through rows
            item = self.file_listbox.item(row, 0)  # Get the item in the first column
            if item:  # Ensure the item is not None
                file_paths.append(item.text())  # Add the file path to the list
        return file_paths

    def delete_files(self):
        """
        Delete the selected files from the listbox. If no files are selected, show a status message.
        """
        try:
            # Get selected rows from the listbox (assuming it's a QTableWidget)
            selected_items = self.file_listbox.selectedItems()

            rows = {item.row() for item in selected_items}
            if not selected_items:
                selected_items = [self.file_listbox.item(i, 0) for i in range(self.file_listbox.rowCount())]
                rows = {item.row() for item in selected_items}

                # Use a set to track file paths to delete, as selectedItems includes individual cells
            files_to_delete = set()
            for item in selected_items:
                row = item.row()
                # Assuming column 0 is folder and column 1 is file name
                folder_item = self.file_listbox.item(row, 0)
                file_item = self.file_listbox.item(row, 1)

                if folder_item and file_item:
                    folder_path = folder_item.text()
                    file_name = file_item.text()
                    file_path = os.path.join(folder_path, file_name)
                    files_to_delete.add(file_path)

            # Proceed with deletion
            deleted_files_count = 0
            for file_path in files_to_delete:
                # Move file to the Deleted folder
                deleted_folder = self.deleted_folder
                if not os.path.exists(deleted_folder):
                    os.makedirs(deleted_folder)

                destination = os.path.join(deleted_folder)
                target_name = os.path.join(deleted_folder, os.path.basename(file_path))
                n = 1
                while os.path.exists(target_name):
                    base, ext = os.path.splitext(target_name)
                    num_match = re.search(r' \((\d+)\)$', base)
                    if num_match:
                        n = int(num_match.group(1)) + 1
                        base = re.sub(r' \(\d+\)$', '', base)
                    target_name = re.sub(r' \(\d+\)$', '', base) + f" ({n})" + ext

                shutil.move(file_path, target_name)
                deleted_files_count += 1
                self.status_window.append(f"Moved file to Deleted folder: {file_path}")

            self.status_window.append(f"Total files moved: {deleted_files_count}")

            # Update the UI (e.g., remove rows corresponding to the deleted items)
            for row in sorted(rows, reverse=True):
                self.file_listbox.removeRow(row)

        except Exception as e:
            self.status_window.append(f"Error deleting files: {str(e)}")
            print(f"Error deleting files: {str(e)}")
            print(traceback.format_exc())

    def closeEvent(self, event):
        # Save GUI state to settings (folder path, window size/position, etc.)
        self.settings.setValue("windowSize", self.size())
        self.settings.setValue("windowPosition", self.pos())
        self.settings.setValue("selectedFolder", self.folder_line_edit.text())

        # Collect items in listbox
        listbox_items = [self.file_listbox.item(i, 0).text() for i in range(self.file_listbox.rowCount())]
        self.settings.setValue("fileListbox", listbox_items)

        super().closeEvent(event)

    def restore_settings(self):
        # Restore previous folder path
        self.folder_line_edit.setText(self.settings.value("selectedFolder", ""))

        # Restore files in listbox
        file_listbox_items = self.settings.value("fileListbox", [])
        if isinstance(file_listbox_items, list):
            self.file_listbox.setRowCount(0)  # Clear existing rows
            for file_entry in file_listbox_items:
                if isinstance(file_entry, list) and len(file_entry) == 2:
                    # Add row with file name and size
                    row_position = self.file_listbox.rowCount()
                    self.file_listbox.insertRow(row_position)
                    self.file_listbox.setItem(row_position, 0, QTableWidgetItem(file_entry[0]))
                    self.file_listbox.setItem(row_position, 1, QTableWidgetItem(file_entry[1]))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = DuplicateFileDeleter()
    window.show()
    sys.exit(app.exec())
