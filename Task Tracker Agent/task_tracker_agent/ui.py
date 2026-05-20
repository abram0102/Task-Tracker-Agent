from __future__ import annotations

import random

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSlider,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from task_tracker_agent.database import Database
from task_tracker_agent.models import ParsedTask, Task
from task_tracker_agent.services.openai_service import OpenAIService


APP_STYLE = """
QMainWindow, QWidget#appRoot {
    background: #f4fbfb;
    color: #173536;
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Helvetica Neue", Arial;
}

QLabel#brand {
    color: #173536;
    font-size: 18px;
    font-weight: 700;
}

QLabel#heroTitle {
    color: #102c2d;
    font-size: 34px;
    font-weight: 800;
}

QLabel#heroSubtitle {
    color: #5f7778;
    font-size: 15px;
}

QLabel#sectionTitle {
    color: #173536;
    font-size: 16px;
    font-weight: 700;
}

QLabel#metaText, QLabel#bodyText {
    color: #587273;
    font-size: 13px;
}

QFrame#inputCard, QFrame#taskSurface, QFrame#dialogCard, QFrame#settingsCard {
    background: rgba(255, 255, 255, 0.92);
    border: 1px solid rgba(10, 186, 181, 0.18);
    border-radius: 28px;
}

QWidget#contentShell {
    background: transparent;
}

QFrame#taskCard {
    background: #ffffff;
    border: 1px solid rgba(10, 186, 181, 0.16);
    border-radius: 20px;
}

QFrame#suggestionCard {
    background: #f8ffff;
    border: 1px solid rgba(10, 186, 181, 0.16);
    border-radius: 22px;
}

QFrame#taskCard[selected="true"] {
    background: #dff7f5;
    border: 1px solid #0abab5;
}

QLabel#chip {
    background: #eefafa;
    border: 1px solid rgba(10, 186, 181, 0.18);
    border-radius: 13px;
    color: #426465;
    font-size: 12px;
    font-weight: 650;
    padding: 6px 10px;
}

QPlainTextEdit, QLineEdit {
    background: #ffffff;
    border: 1px solid rgba(23, 53, 54, 0.10);
    border-radius: 16px;
    color: #173536;
    font-size: 15px;
    padding: 12px;
    selection-background-color: #81d8d0;
}

QPlainTextEdit:focus, QLineEdit:focus {
    border: 1px solid #0abab5;
}

QPlainTextEdit#taskInput {
    border-radius: 24px;
    font-size: 20px;
    padding: 22px;
}

QPlainTextEdit#suggestionsBox {
    background: transparent;
    border: none;
    color: #315758;
    font-size: 15px;
    padding: 4px;
}

QPushButton {
    background: #ffffff;
    border: 1px solid rgba(23, 53, 54, 0.10);
    border-radius: 18px;
    color: #173536;
    font-size: 14px;
    font-weight: 650;
    padding: 10px 18px;
}

QPushButton:hover {
    background: #eefafa;
    border-color: rgba(10, 186, 181, 0.35);
}

QPushButton#primaryButton {
    background: #0abab5;
    border: 1px solid #0abab5;
    color: #ffffff;
    font-size: 15px;
    padding: 13px 24px;
}

QPushButton#primaryButton:hover {
    background: #08a7a2;
}

QPushButton#destructiveButton {
    background: #8b1e1e;
    border: 1px solid #8b1e1e;
    color: #ffffff;
    font-size: 15px;
    padding: 13px 24px;
}

QPushButton#destructiveButton:hover {
    background: #741818;
}

QPushButton#primaryButton:disabled, QPushButton:disabled {
    background: #d8e8e8;
    border-color: #d8e8e8;
    color: #8ba0a1;
}

QListWidget {
    background: transparent;
    border: none;
    outline: none;
    font-size: 13px;
}

QListWidget::item {
    background: #ffffff;
    border: 1px solid rgba(10, 186, 181, 0.14);
    border-radius: 16px;
    color: #173536;
    margin: 5px 0;
    padding: 12px;
}

QListWidget::item:selected {
    background: #dff7f5;
    border: 1px solid #0abab5;
}
"""


def priority_label(score: int) -> str:
    if score >= 85:
        return "Urgent"
    if score >= 70:
        return "High"
    if score >= 40:
        return "Medium"
    return "Low"


def priority_color(score: int) -> QColor:
    anchors = [
        (0, QColor("#0b5d3b")),
        (45, QColor("#d5a928")),
        (100, QColor("#8b1e1e")),
    ]
    for index, (stop, color) in enumerate(anchors):
        if score <= stop:
            prev_stop, prev_color = anchors[index - 1]
            ratio = (score - prev_stop) / max(stop - prev_stop, 1)
            red = prev_color.red() + (color.red() - prev_color.red()) * ratio
            green = prev_color.green() + (color.green() - prev_color.green()) * ratio
            blue = prev_color.blue() + (color.blue() - prev_color.blue()) * ratio
            return QColor(round(red), round(green), round(blue))
    return anchors[-1][1]


def add_shadow(widget: QWidget, blur: int = 36, y_offset: int = 16) -> None:
    shadow = QGraphicsDropShadowEffect(widget)
    shadow.setBlurRadius(blur)
    shadow.setOffset(0, y_offset)
    shadow.setColor(QColor(16, 53, 54, 38))
    widget.setGraphicsEffect(shadow)


class PriorityBar(QWidget):
    value_changed = Signal(int)

    def __init__(self, value: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.value = value
        self.setMinimumHeight(78)

        self.slider = QSlider(Qt.Horizontal, self)
        self.slider.setRange(0, 100)
        self.slider.setValue(value)
        self.slider.valueChanged.connect(self.set_value)
        self.slider.setStyleSheet(
            """
            QSlider { background: transparent; }
            QSlider::groove:horizontal {
                background: transparent;
                height: 28px;
            }
            QSlider::handle:horizontal {
                background: rgba(255, 255, 255, 0.94);
                border: 2px solid rgba(23, 53, 54, 0.28);
                width: 28px;
                height: 28px;
                margin: -9px 0;
                border-radius: 14px;
            }
            QSlider::handle:horizontal:hover {
                border: 2px solid #0abab5;
            }
            """
        )
        self.value_label = QLabel(self)
        self.value_label.setAlignment(Qt.AlignCenter)
        self.value_label.setStyleSheet(
            """
            background: rgba(255, 255, 255, 0.94);
            border: 1px solid rgba(23, 53, 54, 0.10);
            border-radius: 12px;
            color: #173536;
            font-size: 12px;
            font-weight: 800;
            padding: 2px 8px;
            """
        )
        self._sync_value_label()

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        self.slider.setGeometry(0, 28, self.width(), 32)
        self._sync_value_label()
        super().resizeEvent(event)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        bar_rect = QRectF(0, 34, self.width(), 18)
        gradient = QLinearGradient(QPointF(bar_rect.left(), 0), QPointF(bar_rect.right(), 0))
        gradient.setColorAt(0.0, QColor("#0b5d3b"))
        gradient.setColorAt(0.45, QColor("#d5a928"))
        gradient.setColorAt(1.0, QColor("#8b1e1e"))

        painter.setPen(QPen(QColor(255, 255, 255, 190), 1))
        painter.setBrush(gradient)
        painter.drawRoundedRect(bar_rect, 9, 9)

        handle_x = self._handle_center_x()
        painter.setPen(QPen(QColor(23, 53, 54, 28), 1))
        painter.setBrush(QColor(255, 255, 255, 248))
        painter.drawEllipse(QPointF(handle_x, 43), 15, 15)
        painter.setPen(QPen(priority_color(self.value), 3))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(QPointF(handle_x, 43), 10, 10)
        painter.end()
        event.accept()

    def set_value(self, value: int) -> None:
        self.value = value
        self._sync_value_label()
        self.value_changed.emit(value)
        self.update()

    def _handle_center_x(self) -> float:
        if self.width() <= 0:
            return 0
        return 14 + (self.width() - 28) * (self.value / 100)

    def _sync_value_label(self) -> None:
        if not hasattr(self, "value_label"):
            return
        text = f"{priority_label(self.value)} · {self.value}%"
        self.value_label.setText(text)
        self.value_label.adjustSize()
        label_width = self.value_label.width()
        x = int(self._handle_center_x() - label_width / 2)
        x = max(0, min(x, max(self.width() - label_width, 0)))
        self.value_label.move(x, 0)


class ConfirmTaskDialog(QDialog):
    def __init__(
        self,
        parsed: ParsedTask,
        parent: QWidget | None = None,
        heading: str = "Review task",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Confirm Task")
        self.parsed = parsed
        self.setModal(True)
        self.setFixedSize(680, 640)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet(APP_STYLE)

        card = QFrame()
        card.setObjectName("dialogCard")
        add_shadow(card, blur=44, y_offset=18)

        title = QLabel(heading)
        title.setObjectName("heroTitle")
        title.setStyleSheet("font-size: 24px;")
        subtitle = QLabel("Make a quick adjustment, then save it to your tracker.")
        subtitle.setObjectName("heroSubtitle")
        subtitle.setWordWrap(True)

        self.title_input = QLineEdit(parsed.title)
        self.start_input = QLineEdit(parsed.start_time or "")
        self.location_input = QLineEdit(parsed.location or "")
        self.people_input = QLineEdit(", ".join(parsed.people))
        self.category_input = QLineEdit(parsed.category)
        self.priority_input = PriorityBar(parsed.priority_score)
        self.reason_input = QPlainTextEdit(parsed.priority_reason)
        self.reason_input.setFixedHeight(92)
        self.description_input = QPlainTextEdit(parsed.description)
        self.description_input.setFixedHeight(82)

        fields = QGridLayout()
        fields.setHorizontalSpacing(14)
        fields.setVerticalSpacing(12)
        fields.setColumnStretch(0, 1)
        fields.setColumnStretch(1, 1)
        fields.addWidget(self._field("Title", self.title_input), 0, 0)
        fields.addWidget(self._field("Time", self.start_input), 0, 1)
        fields.addWidget(self._field("Place", self.location_input), 1, 0)
        fields.addWidget(self._field("People", self.people_input), 1, 1)
        fields.addWidget(self._field("Type", self.category_input), 2, 0)
        fields.addWidget(self._field("Priority", self.priority_input), 2, 1)

        notes = QGridLayout()
        notes.setHorizontalSpacing(14)
        notes.setColumnStretch(0, 1)
        notes.setColumnStretch(1, 1)
        notes.addWidget(self._field("Why", self.reason_input), 0, 0)
        notes.addWidget(self._field("Notes", self.description_input), 0, 1)

        save_button = QPushButton("Save Task")
        save_button.setObjectName("primaryButton")
        cancel_button = QPushButton("Cancel")
        save_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        button_row.addWidget(cancel_button)
        button_row.addWidget(save_button)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(36, 34, 36, 30)
        card_layout.setSpacing(16)
        card_layout.addWidget(title)
        card_layout.addWidget(subtitle)
        card_layout.addLayout(fields)
        card_layout.addLayout(notes)
        card_layout.addStretch(1)
        card_layout.addLayout(button_row)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.addWidget(card)

    def _field(self, label_text: str, editor: QWidget) -> QWidget:
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        label = QLabel(label_text)
        label.setObjectName("metaText")
        layout.addWidget(label)
        layout.addWidget(editor)
        return box

    def to_parsed_task(self) -> ParsedTask:
        score = self.priority_input.value
        if score >= 85:
            label = "urgent"
        elif score >= 70:
            label = "high"
        elif score >= 40:
            label = "medium"
        else:
            label = "low"

        return ParsedTask(
            title=self.title_input.text().strip() or "Untitled task",
            raw_input=self.parsed.raw_input,
            description=self.description_input.toPlainText().strip(),
            start_time=self.start_input.text().strip() or None,
            end_time=self.parsed.end_time,
            location=self.location_input.text().strip() or None,
            people=[person.strip() for person in self.people_input.text().split(",") if person.strip()],
            category=self.category_input.text().strip() or "personal",
            priority_score=score,
            priority_label=label,
            priority_reason=self.reason_input.toPlainText().strip(),
            suggestion_types=self.parsed.suggestion_types,
        )


class ConfirmDeleteDialog(QDialog):
    def __init__(self, task: Task, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Delete Task")
        self.setModal(True)
        self.setFixedSize(460, 300)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet(APP_STYLE)

        card = QFrame()
        card.setObjectName("dialogCard")
        add_shadow(card, blur=42, y_offset=16)

        title = QLabel("Delete this task?")
        title.setObjectName("heroTitle")
        title.setStyleSheet("font-size: 25px;")
        body = QLabel(
            f"“{task.title}” will be permanently removed. Use Achieved if you want to keep it in Past."
        )
        body.setObjectName("heroSubtitle")
        body.setWordWrap(True)

        cancel_button = QPushButton("Cancel")
        delete_button = QPushButton("Delete")
        delete_button.setObjectName("destructiveButton")
        cancel_button.clicked.connect(self.reject)
        delete_button.clicked.connect(self.accept)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(cancel_button)
        buttons.addWidget(delete_button)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(30, 30, 30, 26)
        layout.setSpacing(16)
        layout.addWidget(title)
        layout.addWidget(body)
        layout.addStretch(1)
        layout.addLayout(buttons)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.addWidget(card)


class SettingsDialog(QDialog):
    def __init__(self, db: Database, ai: OpenAIService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.db = db
        self.ai = ai
        self.setWindowTitle("Priority Rules")
        self.setFixedSize(560, 520)
        self.setStyleSheet(APP_STYLE)

        card = QFrame()
        card.setObjectName("settingsCard")
        add_shadow(card, blur=32, y_offset=12)

        title = QLabel("Priority rules")
        title.setObjectName("heroTitle")
        title.setStyleSheet("font-size: 25px;")

        status = "OpenAI connected" if self.ai.is_configured else "Local fallback mode"
        api_label = QLabel(status)
        api_label.setObjectName("heroSubtitle")

        self.rule_input = QPlainTextEdit()
        self.rule_input.setPlaceholderText(
            "Example: Anything related to my child's school is always high priority."
        )
        self.rule_input.setFixedHeight(96)

        add_rule_button = QPushButton("Add Rule")
        add_rule_button.setObjectName("primaryButton")
        add_rule_button.clicked.connect(self.add_priority_rule)

        self.rules_list = QListWidget()
        self.refresh_rules()

        layout = QVBoxLayout(card)
        layout.setContentsMargins(30, 28, 30, 28)
        layout.setSpacing(14)
        layout.addWidget(title)
        layout.addWidget(api_label)
        layout.addWidget(self.rule_input)
        layout.addWidget(add_rule_button)
        layout.addWidget(self.rules_list, 1)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.addWidget(card)

    def add_priority_rule(self) -> None:
        text = self.rule_input.toPlainText().strip()
        if not text:
            QMessageBox.information(self, "Task Tracker Agent", "Type a rule first.")
            return
        self.db.add_priority_rule(name=text[:48], rule_text=text)
        self.rule_input.clear()
        self.refresh_rules()

    def refresh_rules(self) -> None:
        self.rules_list.clear()
        for rule in self.db.list_priority_rules():
            self.rules_list.addItem(rule)


class PriorityOrb(QWidget):
    def __init__(self, score: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.score = score
        self.setFixedSize(62, 62)

    def set_score(self, score: int) -> None:
        self.score = score
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        color = priority_color(self.score)

        painter.setPen(QPen(QColor(255, 255, 255, 230), 2))
        painter.setBrush(color)
        painter.drawEllipse(QPointF(26, 26), 20, 20)

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(255, 255, 255, 245))
        painter.drawEllipse(QPointF(43, 43), 17, 17)

        painter.setPen(QPen(QColor("#173536")))
        font = painter.font()
        font.setPointSize(8)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(QRectF(27, 31, 32, 24), Qt.AlignCenter, f"{self.score}%")
        painter.end()
        event.accept()


class ConfettiOverlay(QWidget):
    finished = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.particles: list[tuple[float, float, float, float, QColor]] = []
        self.tick = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._step)
        self.hide()

    def start(self) -> None:
        if self.parentWidget():
            self.setGeometry(self.parentWidget().rect())
        width = max(self.width(), 1)
        height = max(self.height(), 1)
        colors = [QColor("#0abab5"), QColor("#d5a928"), QColor("#8b1e1e"), QColor("#ffffff")]
        self.particles = []
        for _ in range(34):
            self.particles.append(
                (
                    width * 0.5,
                    height * 0.52,
                    random.uniform(-5.5, 5.5),
                    random.uniform(-7.0, -2.0),
                    random.choice(colors),
                )
            )
        self.tick = 0
        self.show()
        self.raise_()
        self.timer.start(28)

    def _step(self) -> None:
        self.tick += 1
        next_particles = []
        for x, y, vx, vy, color in self.particles:
            next_particles.append((x + vx, y + vy, vx * 0.96, vy + 0.45, color))
        self.particles = next_particles
        self.update()
        if self.tick >= 24:
            self.timer.stop()
            self.hide()
            self.finished.emit()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        for x, y, _vx, _vy, color in self.particles:
            painter.setPen(Qt.NoPen)
            painter.setBrush(color)
            painter.drawEllipse(QPointF(x, y), 4, 4)
        painter.end()
        event.accept()


class TaskCard(QFrame):
    selected = Signal(int)
    achieved_requested = Signal(int)

    def __init__(self, task: Task, show_achieved_button: bool = True, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.task = task
        self.setObjectName("taskCard")
        self.setProperty("selected", False)
        self.setCursor(Qt.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(12)

        orb = PriorityOrb(task.priority_score)
        orb.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(orb)

        text_column = QVBoxLayout()
        text_column.setSpacing(4)
        title = QLabel(task.title)
        title.setObjectName("sectionTitle")
        title.setWordWrap(True)
        title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        meta = QLabel(task.start_time or task.category)
        meta.setObjectName("metaText")
        meta.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        text_column.addWidget(title)
        text_column.addWidget(meta)
        layout.addLayout(text_column, 1)

        if show_achieved_button:
            achieved_button = QPushButton("Achieved")
            achieved_button.setObjectName("primaryButton")
            achieved_button.clicked.connect(lambda: self.achieved_requested.emit(self.task.id))
            layout.addWidget(achieved_button)

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self.selected.emit(self.task.id)
            event.accept()
            return
        super().mousePressEvent(event)

    def set_selected(self, selected: bool) -> None:
        if self.property("selected") == selected:
            return
        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()


class MainWindow(QMainWindow):
    def __init__(self, db: Database, ai: OpenAIService) -> None:
        super().__init__()
        self.db = db
        self.ai = ai
        self.tasks: list[Task] = []
        self.task_cards: dict[int, TaskCard] = {}
        self.selected_task_id: int | None = None
        self.current_view = "recent"

        self.setWindowTitle("Task Tracker Agent")
        self.resize(1180, 780)
        self.setStyleSheet(APP_STYLE)
        self.setCentralWidget(self._build_main_view())

        self.refresh_tasks()

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        compact = self.width() < 980
        margin = 18 if compact else 28
        if hasattr(self, "outer_layout"):
            self.outer_layout.setContentsMargins(margin, margin, margin, 28)
        if hasattr(self, "detail_card"):
            self.detail_card.setMinimumWidth(420 if compact else 560)
        if hasattr(self, "task_surface"):
            self.task_surface.setMaximumHeight(620 if compact else 520)
        super().resizeEvent(event)

    def _build_main_view(self) -> QWidget:
        root = QWidget()
        root.setObjectName("appRoot")
        self.outer_layout = QVBoxLayout(root)
        self.outer_layout.setContentsMargins(28, 28, 28, 34)
        self.outer_layout.setSpacing(0)

        shell = QWidget()
        shell.setObjectName("contentShell")
        shell.setMaximumWidth(1280)
        shell.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.outer_layout.addWidget(shell, 0, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)

        page = QVBoxLayout(shell)
        page.setContentsMargins(0, 0, 0, 0)
        page.setSpacing(24)

        top_bar = QHBoxLayout()
        brand = QLabel("Task Tracker Agent")
        brand.setObjectName("brand")
        settings_button = QPushButton("Priority Rules")
        settings_button.clicked.connect(self.open_settings)
        top_bar.addWidget(brand)
        top_bar.addStretch(1)
        top_bar.addWidget(settings_button)

        input_card = QFrame()
        input_card.setObjectName("inputCard")
        input_card.setMaximumHeight(330)
        add_shadow(input_card, blur=40, y_offset=18)
        input_layout = QVBoxLayout(input_card)
        input_layout.setContentsMargins(34, 30, 34, 28)
        input_layout.setSpacing(16)

        hero_title = QLabel("Drop a task here.")
        hero_title.setObjectName("heroTitle")
        hero_subtitle = QLabel(
            "Write naturally, or use voice input to add a task. The agent will pull out time, "
            "people, context, and priority."
        )
        hero_subtitle.setObjectName("heroSubtitle")
        hero_subtitle.setWordWrap(True)

        self.input_box = QPlainTextEdit()
        self.input_box.setObjectName("taskInput")
        self.input_box.setPlaceholderText("Dinner with my girlfriend this Sunday at 6pm")
        self.input_box.setFixedHeight(122)

        self.parse_button = QPushButton("Parse Task")
        self.parse_button.setObjectName("primaryButton")
        self.parse_button.clicked.connect(self.parse_task)
        self.voice_button = QPushButton("Voice Input")
        self.voice_button.clicked.connect(self.voice_input)

        input_footer = QHBoxLayout()
        self.input_status = QLabel("")
        self.input_status.setObjectName("metaText")
        input_footer.addWidget(self.input_status)
        input_footer.addStretch(1)
        input_footer.addWidget(self.voice_button)
        input_footer.addWidget(self.parse_button)

        input_layout.addWidget(hero_title)
        input_layout.addWidget(hero_subtitle)
        input_layout.addWidget(self.input_box)
        input_layout.addLayout(input_footer)

        self.task_surface = QFrame()
        self.task_surface.setObjectName("taskSurface")
        self.task_surface.setVisible(False)
        self.task_surface.setMinimumHeight(360)
        self.task_surface.setMaximumHeight(520)

        surface_layout = QHBoxLayout(self.task_surface)
        surface_layout.setContentsMargins(26, 24, 26, 24)
        surface_layout.setSpacing(22)

        recent_column = QVBoxLayout()
        recent_wrap = QWidget()
        recent_wrap.setMinimumWidth(320)
        recent_wrap.setMaximumWidth(430)
        recent_wrap.setLayout(recent_column)
        list_header = QHBoxLayout()
        self.recent_button = QPushButton("Recent")
        self.past_button = QPushButton("Past")
        self.recent_button.setObjectName("primaryButton")
        self.recent_button.clicked.connect(lambda: self.switch_task_view("recent"))
        self.past_button.clicked.connect(lambda: self.switch_task_view("past"))
        list_header.addWidget(self.recent_button)
        list_header.addWidget(self.past_button)
        list_header.addStretch(1)
        self.task_list = QVBoxLayout()
        self.task_list.setSpacing(10)
        recent_column.addLayout(list_header)
        recent_column.addLayout(self.task_list)
        recent_column.addStretch(1)

        self.detail_card = QFrame()
        self.detail_card.setObjectName("taskCard")
        self.detail_card.setMinimumWidth(560)
        detail_layout = QVBoxLayout(self.detail_card)
        detail_layout.setContentsMargins(28, 26, 28, 26)
        detail_layout.setSpacing(16)

        detail_header = QHBoxLayout()
        detail_header.setSpacing(16)
        self.detail_orb = PriorityOrb(50)
        self.detail_title = QLabel("Select a task")
        self.detail_title.setObjectName("sectionTitle")
        self.detail_title.setStyleSheet("font-size: 26px; font-weight: 800;")
        title_column = QVBoxLayout()
        title_column.setSpacing(8)
        title_column.addWidget(self.detail_title)
        self.detail_chips = QHBoxLayout()
        self.detail_chips.setSpacing(8)
        title_column.addLayout(self.detail_chips)
        detail_header.addWidget(self.detail_orb)
        detail_header.addLayout(title_column, 1)

        self.detail_reason = QLabel("")
        self.detail_reason.setObjectName("bodyText")
        self.detail_reason.setWordWrap(True)
        suggestions_label = QLabel("AI Suggestions")
        suggestions_label.setObjectName("sectionTitle")
        suggestion_card = QFrame()
        suggestion_card.setObjectName("suggestionCard")
        suggestion_layout = QVBoxLayout(suggestion_card)
        suggestion_layout.setContentsMargins(18, 16, 18, 16)
        self.suggestions_box = QPlainTextEdit()
        self.suggestions_box.setObjectName("suggestionsBox")
        self.suggestions_box.setReadOnly(True)
        self.suggestions_box.setFixedHeight(128)
        self.suggestions_box.setPlaceholderText("Select a task to see suggestions.")
        suggestion_layout.addWidget(self.suggestions_box)
        self.suggestions_button = QPushButton("Refresh Suggestions")
        self.suggestions_button.setObjectName("primaryButton")
        self.suggestions_button.setEnabled(False)
        self.suggestions_button.clicked.connect(self.generate_suggestions)
        action_row = QHBoxLayout()
        self.edit_button = QPushButton("Edit")
        self.delete_button = QPushButton("Delete")
        self.edit_button.setEnabled(False)
        self.delete_button.setEnabled(False)
        self.edit_button.clicked.connect(self.edit_selected_task)
        self.delete_button.clicked.connect(self.delete_selected_task)
        action_row.addWidget(self.edit_button)
        action_row.addWidget(self.delete_button)
        action_row.addStretch(1)

        detail_layout.addLayout(detail_header)
        detail_layout.addWidget(self.detail_reason)
        detail_layout.addLayout(action_row)
        detail_layout.addWidget(suggestions_label)
        detail_layout.addWidget(suggestion_card)
        detail_layout.addWidget(self.suggestions_button)
        detail_layout.addStretch(1)

        surface_layout.addWidget(recent_wrap, 0)
        surface_layout.addWidget(self.detail_card, 1)

        page.addLayout(top_bar)
        page.addWidget(input_card)
        page.addWidget(self.task_surface, 1)
        return root

    def open_settings(self) -> None:
        dialog = SettingsDialog(self.db, self.ai, self)
        dialog.exec()

    def voice_input(self) -> None:
        QMessageBox.information(
            self,
            "Voice Input",
            "Voice input can add tasks too. The button is now in the workflow; next we will connect "
            "Mac microphone recording and OpenAI transcription so spoken tasks fill this box automatically.",
        )

    def parse_task(self) -> None:
        raw_input = self.input_box.toPlainText().strip()
        if not raw_input:
            self.input_status.setText("Type a task first.")
            return

        self.parse_button.setEnabled(False)
        self.parse_button.setText("Parsing...")
        self.input_status.setText("Reading the task...")
        QApplication.processEvents()

        try:
            parsed = self.ai.parse_task(raw_input, self.db.list_priority_rules())
        except Exception as exc:
            QMessageBox.critical(self, "OpenAI Error", str(exc))
            return
        finally:
            self.parse_button.setEnabled(True)
            self.parse_button.setText("Parse Task")

        if self.ai.last_warning:
            self.input_status.setText("Using local fallback while OpenAI quota is unavailable.")
        else:
            self.input_status.setText("Task parsed. Review it before saving.")

        dialog = ConfirmTaskDialog(parsed, self)
        if dialog.exec() == QDialog.Accepted:
            task_id = self.db.create_task(dialog.to_parsed_task())
            self.input_box.clear()
            self.input_status.setText("Saved.")
            self.refresh_tasks()
            self.select_task(task_id)

    def refresh_tasks(self) -> None:
        recent_tasks = self.db.list_tasks()
        past_tasks = self.db.list_past_tasks()
        self.tasks = recent_tasks if self.current_view == "recent" else past_tasks
        while self.task_list.count():
            item = self.task_list.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.task_cards = {}
        self.task_surface.setVisible(bool(recent_tasks or past_tasks))
        self.recent_button.setObjectName("primaryButton" if self.current_view == "recent" else "")
        self.past_button.setObjectName("primaryButton" if self.current_view == "past" else "")
        for button in (self.recent_button, self.past_button):
            button.style().unpolish(button)
            button.style().polish(button)
        task_ids = {task.id for task in self.tasks}
        if self.selected_task_id not in task_ids:
            self.selected_task_id = None
        for task in self.tasks:
            card = TaskCard(task, show_achieved_button=self.current_view == "recent")
            card.selected.connect(self.show_task)
            card.achieved_requested.connect(self.achieve_task)
            self.task_list.addWidget(card)
            self.task_cards[task.id] = card
            card.set_selected(task.id == self.selected_task_id)
        if not self.tasks:
            empty = QLabel("No recent tasks." if self.current_view == "recent" else "No past tasks yet.")
            empty.setObjectName("metaText")
            self.task_list.addWidget(empty)
        has_selection = self.selected_task_id is not None
        self.suggestions_button.setEnabled(has_selection)
        self.edit_button.setEnabled(has_selection)
        self.delete_button.setEnabled(has_selection)
        if self.selected_task_id is None and self.tasks:
            self.select_task(self.tasks[0].id)
        if not self.tasks:
            self.clear_detail()

    def switch_task_view(self, view: str) -> None:
        self.current_view = view
        self.selected_task_id = None
        self.refresh_tasks()

    def clear_detail(self) -> None:
        self.detail_title.setText("Select a task")
        self.detail_orb.set_score(50)
        self._set_detail_chips([])
        self.detail_reason.clear()
        self.suggestions_box.clear()
        self.suggestions_button.setEnabled(False)
        self.edit_button.setEnabled(False)
        self.delete_button.setEnabled(False)

    def select_task(self, task_id: int) -> None:
        self.show_task(task_id)

    def show_task(self, task_id: int) -> None:
        self.selected_task_id = task_id
        for card_id, card in self.task_cards.items():
            card.set_selected(card_id == task_id)
        self.suggestions_button.setEnabled(True)
        self.edit_button.setEnabled(True)
        self.delete_button.setEnabled(True)
        task = self.db.get_task(task_id)
        if not task:
            return
        self.detail_title.setText(task.title)
        self.detail_orb.set_score(task.priority_score)
        people = ", ".join(task.people) if task.people else "None"
        self._set_detail_chips(
            [
                f"{priority_label(task.priority_score)} {task.priority_score}%",
                f"Time: {task.start_time or 'Not set'}",
                f"Place: {task.location or 'Not set'}",
                f"People: {people}",
                f"Type: {task.category}",
            ]
        )
        if "fallback parser" in task.priority_reason.lower() or "quota" in task.priority_reason.lower():
            self.detail_reason.setText(
                "Parsed in local mode. Add a time/place if needed, then use the suggestions below as a planning starting point."
            )
        else:
            self.detail_reason.setText(task.priority_reason)
        self.suggestions_box.setPlainText(self._format_suggestions(self._local_suggestions(task)))

    def _set_detail_chips(self, chips: list[str]) -> None:
        while self.detail_chips.count():
            item = self.detail_chips.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for text in chips:
            chip = QLabel(text)
            chip.setObjectName("chip")
            self.detail_chips.addWidget(chip)
        self.detail_chips.addStretch(1)

    def _format_suggestions(self, suggestions: list[str]) -> str:
        return "\n".join(f"- {suggestion}" for suggestion in suggestions)

    def _local_suggestions(self, task: Task) -> list[str]:
        text = f"{task.title} {task.category} {task.raw_input}".lower()
        if any(word in text for word in ["girlfriend", "dinner", "date", "restaurant"]):
            return [
                "Choose a quiet, reservation-friendly restaurant and keep one backup option nearby.",
                "Confirm the exact time and neighborhood before making the reservation.",
                "Set a leave-by reminder once you know the restaurant and travel time.",
                "Add a small prep note: dress code, parking, and whether you want dessert or drinks after dinner.",
            ]
        if any(word in text for word in ["school", "teacher", "child", "kid"]):
            return [
                "Check the school email or portal for any forms, deadlines, or supplies.",
                "Add a prep checklist so the task can be completed without rereading the original message.",
                "Keep this high priority until the school-related action is fully done.",
            ]
        if any(word in text for word in ["doctor", "medical", "appointment"]):
            return [
                "Confirm the appointment time, address, and whether any forms are required.",
                "Prepare insurance information, medication list, and questions in advance.",
                "Add travel buffer so you are not rushed before the appointment.",
            ]
        return [
            "Clarify the next concrete action needed to move this task forward.",
            "Add a time, place, or person if this task should be prioritized more accurately.",
            "Decide whether this belongs in today, this week, or a later planning bucket.",
        ]

    def generate_suggestions(self) -> None:
        if self.selected_task_id is None:
            return
        task = self.db.get_task(self.selected_task_id)
        if not task:
            return

        self.suggestions_button.setEnabled(False)
        self.suggestions_button.setText("Thinking...")
        QApplication.processEvents()

        try:
            suggestions = self.ai.suggest_actions(task)
            self.suggestions_box.setPlainText(self._format_suggestions(suggestions))
            if self.ai.last_warning:
                self.input_status.setText("Suggestions used local fallback because OpenAI quota is unavailable.")
        except Exception as exc:
            QMessageBox.critical(self, "Suggestion Error", str(exc))
        finally:
            self.suggestions_button.setEnabled(True)
            self.suggestions_button.setText("Refresh Suggestions")

    def edit_selected_task(self) -> None:
        if self.selected_task_id is not None:
            self.edit_task(self.selected_task_id)

    def edit_task(self, task_id: int) -> None:
        task = self.db.get_task(task_id)
        if not task:
            return
        parsed = ParsedTask(
            title=task.title,
            raw_input=task.raw_input,
            description=task.description,
            start_time=task.start_time,
            end_time=task.end_time,
            location=task.location,
            people=task.people,
            category=task.category,
            priority_score=task.priority_score,
            priority_label=task.priority_label,
            priority_reason=task.priority_reason,
        )
        dialog = ConfirmTaskDialog(parsed, self, heading="Edit task")
        if dialog.exec() == QDialog.Accepted:
            self.db.update_task(task_id, dialog.to_parsed_task())
            self.refresh_tasks()
            self.select_task(task_id)

    def achieve_task(self, task_id: int) -> None:
        card = self.task_cards.get(task_id)
        if not card:
            return
        self.show_task(task_id)
        overlay = ConfettiOverlay(card)
        card.confetti_overlay = overlay
        overlay.finished.connect(lambda: self._finish_achieve_task(task_id))
        overlay.finished.connect(lambda: setattr(card, "confetti_overlay", None))
        overlay.start()

    def _finish_achieve_task(self, task_id: int) -> None:
        self.db.mark_task_achieved(task_id)
        self.input_status.setText("Moved to Past.")
        self.selected_task_id = None
        self.refresh_tasks()

    def delete_selected_task(self) -> None:
        if self.selected_task_id is not None:
            self.delete_task(self.selected_task_id)

    def delete_task(self, task_id: int) -> None:
        task = self.db.get_task(task_id)
        if not task:
            return
        dialog = ConfirmDeleteDialog(task, self)
        if dialog.exec() != QDialog.Accepted:
            return
        self.db.delete_task(task_id)
        self.selected_task_id = None
        self.clear_detail()
        self.refresh_tasks()
