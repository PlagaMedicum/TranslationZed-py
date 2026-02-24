"""Widgets for compact progress strip rendering in the sidebar."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPaintEvent
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QWidget

from .progress_metrics import StatusProgress, proofread_percent, translated_percent

_STATUS_COLORS = (
    QColor("#555a60"),  # untouched
    QColor("#b1772c"),  # for review
    QColor("#2f7d45"),  # translated
    QColor("#2c5f9e"),  # proofread
)
_TRACK_COLOR = QColor("#2a2a2a")
_DISABLED_TRACK_COLOR = QColor("#3a3a3a")


class SegmentedProgressBar(QWidget):
    """Render a compact horizontal status-distribution bar."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize segmented bar widget."""
        super().__init__(parent)
        self._progress = StatusProgress()
        self._loading = False
        self.setMinimumHeight(8)
        self.setMaximumHeight(8)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_progress(self, progress: StatusProgress | None, *, loading: bool) -> None:
        """Apply progress payload and trigger repaint."""
        self._progress = progress or StatusProgress()
        self._loading = bool(loading)
        self.update()

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802
        """Paint segmented bar from status distribution payload."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        rect = self.rect().adjusted(0, 0, -1, -1)
        if rect.width() <= 0 or rect.height() <= 0:
            return
        painter.fillRect(
            rect,
            _DISABLED_TRACK_COLOR if self._loading else _TRACK_COLOR,
        )
        total = self._progress.total
        if total <= 0:
            return
        counts = self._progress.as_tuple()
        x = rect.x()
        width = rect.width()
        for idx, count in enumerate(counts):
            if count <= 0:
                continue
            if idx == len(counts) - 1:
                segment_width = rect.right() - x + 1
            else:
                segment_width = int(round((count / total) * width))
            if segment_width <= 0:
                continue
            painter.fillRect(x, rect.y(), segment_width, rect.height(), _STATUS_COLORS[idx])
            x += segment_width
            if x > rect.right():
                break


class ProgressStripRow(QWidget):
    """Compact row with icon, segmented bar, and T/P percent label."""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        """Initialize one progress strip row."""
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.icon_label = QLabel(self)
        self.icon_label.setFixedWidth(16)
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.title_label = QLabel(title, self)
        self.title_label.setMinimumWidth(48)
        self.bar = SegmentedProgressBar(self)
        self.percent_label = QLabel("T:0% P:0%", self)
        self.percent_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.percent_label.setMinimumWidth(0)
        layout.addWidget(self.icon_label)
        layout.addSpacing(4)
        layout.addWidget(self.title_label)
        layout.addSpacing(10)
        layout.addWidget(self.bar, 1)
        layout.addSpacing(3)
        layout.addWidget(self.percent_label)

    def set_title_column_width(self, width: int) -> None:
        """Force a fixed title-column width for cross-row alignment."""
        self.title_label.setFixedWidth(max(0, int(width)))

    def set_percent_column_width(self, width: int) -> None:
        """Force a fixed percent-column width for cross-row alignment."""
        self.percent_label.setFixedWidth(max(0, int(width)))

    def set_progress(self, progress: StatusProgress | None, *, loading: bool = False) -> None:
        """Update row progress display."""
        payload = progress or StatusProgress()
        self.bar.set_progress(payload, loading=loading)
        if loading and payload.total <= 0:
            self.percent_label.setText("T:-- P:--")
            self.setToolTip("Calculating progress...")
            return
        translated = translated_percent(payload)
        proofread = proofread_percent(payload)
        self.percent_label.setText(f"T:{translated}% P:{proofread}%")
        self.setToolTip(f"T:{translated}%  P:{proofread}%")
