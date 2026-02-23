"""Delegate for drawing compact progress bars in the project file tree."""

from __future__ import annotations

from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem

from .fs_model import TREE_PROGRESS_COUNTS_ROLE

_STATUS_COLORS = (
    QColor("#555a60"),  # untouched
    QColor("#b1772c"),  # for review
    QColor("#2f7d45"),  # translated
    QColor("#2c5f9e"),  # proofread
)
_TRACK_COLOR = QColor("#2a2a2a")


class TreeProgressDelegate(QStyledItemDelegate):
    """Draw thin status-distribution bars for selected tree rows."""

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:  # noqa: N802
        """Paint base item and append thin progress bar if payload is available."""
        super().paint(painter, option, index)
        payload = index.data(TREE_PROGRESS_COUNTS_ROLE)
        if not isinstance(payload, (tuple, list)) or len(payload) != 4:
            return
        counts = tuple(max(0, int(value)) for value in payload)
        total = sum(counts)
        if total <= 0:
            return
        rect = option.rect.adjusted(8, option.rect.height() - 4, -8, -1)
        if rect.width() <= 0 or rect.height() <= 0:
            return
        painter.save()
        painter.fillRect(rect, _TRACK_COLOR)
        width = rect.width()
        x = rect.x()
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
        painter.restore()

