"""Message boxes that always show plain text.

Qt guesses whether text is HTML. Names and errors come from devices and files, so a name such as
<img src=//host/a> would be rendered, and on Windows that path makes the PC connect to the host and
send the user's password hash. Every message with values in it goes through here instead of the
QMessageBox.information/warning/question/critical shortcuts.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox

Button = QMessageBox.StandardButton


def box(parent, icon, title, text, buttons=Button.Ok) -> QMessageBox:
	b = QMessageBox(icon, title, text, buttons, parent)
	b.setTextFormat(Qt.TextFormat.PlainText)
	return b


def info(parent, title, text):
	box(parent, QMessageBox.Icon.Information, title, text).exec()


def warn(parent, title, text):
	box(parent, QMessageBox.Icon.Warning, title, text).exec()


def error(parent, title, text):
	box(parent, QMessageBox.Icon.Critical, title, text).exec()


def ask(parent, title, text) -> bool:
	b = box(parent, QMessageBox.Icon.Question, title, text, Button.Yes | Button.No)
	b.setDefaultButton(Button.No)
	return b.exec() == Button.Yes
