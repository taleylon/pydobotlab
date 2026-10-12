"""Custom widgets for the pydobotlab control panel.

Two headline widgets:

* :class:`JogPad` - a round DobotLab-style joystick split into four labelled
  segments. Holding a segment emits ``jog(JOGCmd)``; releasing emits
  ``stop()``, so the panel can call ``dobot.jog(cmd, mode)`` /
  ``dobot.jog_stop()``.
* :class:`CoordReadout` - a vertical stack of (label, value) rows for one
  coordinate system. Used twice in the panel: once for ``X / Y / Z / R``
  next to the Cartesian jog pads, once for ``J1..J4`` next to the joint
  jog pads.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QWidget,
)

from pydobotlab import __version__
from pydobotlab.protocol import JOGCmd

# Segment names. A pad uses exactly one of these two sets:
#   diagonal - the disc is cut by an X, giving top / right / bottom / left
#              wedges (the X/Y and Z/R pads);
#   quadrant - the disc is cut by a +, giving four quarters (the J1/J2 and
#              J3/J4 pads).
DIAGONAL_SEGMENTS = ("top", "right", "bottom", "left")
QUADRANT_SEGMENTS = ("top_left", "top_right", "bottom_left", "bottom_right")

# Unit direction from the disc centre to each segment's label (y points down).
SEGMENT_DIRECTIONS: dict[str, tuple[float, float]] = {
    "top": (0, -1),
    "right": (1, 0),
    "bottom": (0, 1),
    "left": (-1, 0),
    "top_left": (-0.707, -0.707),
    "top_right": (0.707, -0.707),
    "bottom_left": (-0.707, 0.707),
    "bottom_right": (0.707, 0.707),
}

HUB_RADIUS_FRACTION = 0.28  # the inert centre circle, as a share of the disc radius


def segment_at(offset_x: float, offset_y: float, segment_names: tuple[str, ...]) -> str:
    """Segment containing the point ``(offset_x, offset_y)`` from the disc centre."""
    if segment_names == DIAGONAL_SEGMENTS:
        if abs(offset_x) > abs(offset_y):
            return "right" if offset_x > 0 else "left"
        return "bottom" if offset_y > 0 else "top"
    vertical = "bottom" if offset_y > 0 else "top"
    horizontal = "right" if offset_x > 0 else "left"
    return f"{vertical}_{horizontal}"


def segment_polygon(name: str, centre: QPointF, reach: float) -> QPolygonF:
    """Region of ``name``, extended past the disc so it can be clipped to the circle."""
    cx, cy = centre.x(), centre.y()
    corners = {
        "top": [(0, 0), (-1, -1), (1, -1)],
        "bottom": [(0, 0), (-1, 1), (1, 1)],
        "left": [(0, 0), (-1, -1), (-1, 1)],
        "right": [(0, 0), (1, -1), (1, 1)],
        "top_left": [(0, 0), (-1, 0), (-1, -1), (0, -1)],
        "top_right": [(0, 0), (1, 0), (1, -1), (0, -1)],
        "bottom_left": [(0, 0), (-1, 0), (-1, 1), (0, 1)],
        "bottom_right": [(0, 0), (1, 0), (1, 1), (0, 1)],
    }[name]
    return QPolygonF([QPointF(cx + dx * reach, cy + dy * reach) for dx, dy in corners])


def version_label() -> QLabel:
    """``pydobotlab v<version>``, for the right end of a window's status bar."""
    label = QLabel(f"pydobotlab v{__version__}")
    label.setObjectName("version")
    return label


class JogPad(QWidget):
    """Round joystick with four labelled segments, like DobotLab's jog pads.

    ``segments`` maps each segment name to ``(label, JOGCmd)``. Use the four
    :data:`DIAGONAL_SEGMENTS` names or the four :data:`QUADRANT_SEGMENTS`
    names. Emits ``jog(int)`` while a segment is held and ``stop()`` on
    release.
    """

    jog = Signal(int)
    stop = Signal()

    def __init__(
        self,
        title: str,
        segments: dict[str, tuple[str, JOGCmd]],
        *,
        parent=None,
    ) -> None:
        super().__init__(parent)
        names = tuple(segments)
        if set(names) == set(DIAGONAL_SEGMENTS):
            self._segment_names = DIAGONAL_SEGMENTS
        elif set(names) == set(QUADRANT_SEGMENTS):
            self._segment_names = QUADRANT_SEGMENTS
        else:
            raise ValueError(
                f"segments must be {DIAGONAL_SEGMENTS} or {QUADRANT_SEGMENTS}, got {names}"
            )
        self._segments = segments
        self.setToolTip(title)
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(150, 150)
        self._hovered: str | None = None
        self._pressed: str | None = None

    def sizeHint(self) -> QSize:
        return QSize(180, 180)

    # -- geometry --------------------------------------------------------------

    def disc(self) -> tuple[QPointF, float]:
        radius = min(self.width(), self.height()) / 2 - 2
        return QPointF(self.width() / 2, self.height() / 2), radius

    def segment_under(self, position: QPointF) -> str | None:
        """Segment at ``position``, or ``None`` outside the disc or on the centre hub."""
        centre, radius = self.disc()
        offset_x, offset_y = position.x() - centre.x(), position.y() - centre.y()
        distance = (offset_x**2 + offset_y**2) ** 0.5
        if distance > radius or distance < radius * HUB_RADIUS_FRACTION:
            return None
        return segment_at(offset_x, offset_y, self._segment_names)

    # -- mouse -------------------------------------------------------------------

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.LeftButton:
            return
        segment = self.segment_under(event.position())
        if segment is None:
            return
        self._pressed = segment
        self.jog.emit(int(self._segments[segment][1]))
        self.update()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.release_pressed_segment()

    def mouseMoveEvent(self, event) -> None:
        hovered = self.segment_under(event.position())
        if hovered != self._hovered:
            self._hovered = hovered
            self.update()

    def leaveEvent(self, event) -> None:
        self._hovered = None
        self.update()

    def release_pressed_segment(self) -> None:
        if self._pressed is not None:
            self._pressed = None
            self.stop.emit()
            self.update()

    def changeEvent(self, event) -> None:
        # Disabled mid-press (alarm lock, disconnect): the release will never
        # arrive, so stop the jog now.
        if event.type() == QEvent.EnabledChange and not self.isEnabled():
            self.release_pressed_segment()
        super().changeEvent(event)

    # -- painting ----------------------------------------------------------------

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        centre, radius = self.disc()
        enabled = self.isEnabled()

        disc_path = QPainterPath()
        disc_path.addEllipse(centre, radius, radius)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#2b3039" if enabled else "#22262d"))
        painter.drawPath(disc_path)

        for name in (self._pressed, self._hovered):
            if name is None or not enabled:
                continue
            wedge = QPainterPath()
            wedge.addPolygon(segment_polygon(name, centre, radius * 2))
            wedge.closeSubpath()
            painter.setBrush(QColor("#1a3a55" if name == self._pressed else "#343a46"))
            painter.drawPath(wedge.intersected(disc_path))

        # Dividers between the segments.
        painter.setPen(QPen(QColor("#1b1e24"), 2))
        reach = radius
        if self._segment_names == DIAGONAL_SEGMENTS:
            offset = reach * 0.7071
            painter.drawLine(
                QPointF(centre.x() - offset, centre.y() - offset),
                QPointF(centre.x() + offset, centre.y() + offset),
            )
            painter.drawLine(
                QPointF(centre.x() - offset, centre.y() + offset),
                QPointF(centre.x() + offset, centre.y() - offset),
            )
        else:
            painter.drawLine(
                QPointF(centre.x() - reach, centre.y()), QPointF(centre.x() + reach, centre.y())
            )
            painter.drawLine(
                QPointF(centre.x(), centre.y() - reach), QPointF(centre.x(), centre.y() + reach)
            )

        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor("#1b1e24"), 2))
        painter.drawEllipse(centre, radius, radius)

        hub_radius = radius * HUB_RADIUS_FRACTION
        painter.setPen(QPen(QColor("#1b1e24"), 1))
        painter.setBrush(QColor("#23272f"))
        painter.drawEllipse(centre, hub_radius, hub_radius)

        font = QFont(self.font())
        font.setPointSizeF(max(8.0, radius / 11))
        font.setBold(True)
        painter.setFont(font)
        for name, (label, _command) in self._segments.items():
            direction_x, direction_y = SEGMENT_DIRECTIONS[name]
            label_centre = QPointF(
                centre.x() + direction_x * radius * 0.64, centre.y() + direction_y * radius * 0.64
            )
            if not enabled:
                painter.setPen(QColor("#555a66"))
            elif name == self._pressed:
                painter.setPen(QColor("#ffffff"))
            else:
                painter.setPen(QColor("#aab2c2"))
            painter.drawText(
                QRectF(label_centre.x() - 30, label_centre.y() - 12, 60, 24),
                Qt.AlignCenter,
                label,
            )
        painter.end()


class CoordReadout(QFrame):
    """Vertical stack of (label, value) rows for one coordinate system.

    Used twice in the panel - once for Cartesian (X/Y/Z/R) sitting next to
    the X/Y and Z/R jog pads, once for joints (J1..J4) sitting next to the
    J1/J2 and J3/J4 jog pads. Matches the original DobotLab layout where
    each coord system's numeric readout shares a row with its jog controls.
    """

    def __init__(self, labels: list[str], parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        layout = QGridLayout(self)
        layout.setContentsMargins(12, 14, 12, 14)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(8)

        self._values: dict[str, QLabel] = {}
        for row, name in enumerate(labels):
            label = QLabel(name)
            label.setObjectName("poseLabel")
            value_label = QLabel("0.00")
            value_label.setObjectName("poseValue")
            value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            layout.addWidget(label, row, 0)
            layout.addWidget(value_label, row, 1)
            self._values[name] = value_label

    def update_values(self, values: dict[str, float]) -> None:
        for name, value in values.items():
            label = self._values.get(name)
            if label is not None:
                label.setText(f"{value:7.2f}")


class JumpParamsCard(QFrame):
    """Inline editor for the Jump-mode parameters ``(zlimit, height)``.

    Hidden behind a menu in DobotLab; we surface it on the panel so a
    student can see and tweak the lift envelope at a glance.

    Emits ``valuesChanged(zlimit, height)`` on edit; ``update_values()``
    rewrites both fields without re-emitting (used when the arm reports a
    change made by another client).
    """

    valuesChanged = Signal(float, float)  # zlimit, height (mm)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("card")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(8)

        title = QLabel("Jump")
        title.setStyleSheet("color:#aab2c2; font-weight:600;")
        layout.addWidget(title)

        layout.addWidget(self.create_parameter_label("zlimit"))
        self._zlimit = QDoubleSpinBox()
        self._zlimit.setRange(0.0, 200.0)
        self._zlimit.setDecimals(1)
        self._zlimit.setSingleStep(5.0)
        self._zlimit.setSuffix(" mm")
        self._zlimit.setValue(100.0)
        layout.addWidget(self._zlimit)

        layout.addSpacing(16)
        layout.addWidget(self.create_parameter_label("height"))
        self._height = QDoubleSpinBox()
        self._height.setRange(0.0, 200.0)
        self._height.setDecimals(1)
        self._height.setSingleStep(5.0)
        self._height.setSuffix(" mm")
        self._height.setValue(20.0)
        layout.addWidget(self._height)

        layout.addStretch(1)

        self._zlimit.editingFinished.connect(self.emit_values_changed)
        self._height.editingFinished.connect(self.emit_values_changed)

    @staticmethod
    def create_parameter_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet("color:#aab2c2;")
        return label

    def emit_values_changed(self) -> None:
        self.valuesChanged.emit(float(self._zlimit.value()), float(self._height.value()))

    def update_values(self, zlimit: float, height: float) -> None:
        for spin, value in ((self._zlimit, zlimit), (self._height, height)):
            spin.blockSignals(True)
            try:
                spin.setValue(float(value))
            finally:
                spin.blockSignals(False)
