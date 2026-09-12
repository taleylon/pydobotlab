"""Custom widgets for the pydobotlab control panel.

Two headline widgets:

* :class:`JogPad` - four buttons in a + cross pattern that emit
  ``jog(JOGCmd)`` while held and ``stop()`` on release, so the panel can
  call ``dobot.jog(cmd, mode)`` / ``dobot.jog_stop()``.
* :class:`CoordReadout` - a vertical stack of (label, value) rows for one
  coordinate system. Used twice in the panel: once for ``X / Y / Z / R``
  next to the Cartesian jog pads, once for ``J1..J4`` next to the joint
  jog pads.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)

from pydobotlab.protocol import JOGCmd


class JogButton(QPushButton):
    """A round jog button that emits its associated :class:`JOGCmd` while held."""

    pressedCmd = Signal(int)  # emits JOGCmd on press
    releasedCmd = Signal()  # emits on release (no payload)

    def __init__(self, label: str, cmd: JOGCmd, *, small: bool = False, parent=None) -> None:
        super().__init__(label, parent)
        self.setObjectName("jogSmall" if small else "jog")
        self._cmd = int(cmd)
        # autoRepeat off - we want one press/release per click-and-hold cycle.
        self.setAutoRepeat(False)
        self.setFocusPolicy(Qt.NoFocus)
        self.pressed.connect(self.emit_jog_command)
        self.released.connect(self.releasedCmd.emit)

    def emit_jog_command(self) -> None:
        self.pressedCmd.emit(self._cmd)


class JogPad(QFrame):
    """Four jog buttons in a + cross.

    Emits ``jog(int)`` while a button is held; emits ``stop()`` on release.
    The four ``(label, JOGCmd)`` pairs go in (top, bottom, left, right) order.
    """

    jog = Signal(int)
    stop = Signal()

    def __init__(
        self,
        title: str,
        top: tuple[str, JOGCmd],
        bottom: tuple[str, JOGCmd],
        left: tuple[str, JOGCmd],
        right: tuple[str, JOGCmd],
        *,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 8, 12, 12)
        outer.setSpacing(6)

        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("color:#aab2c2; font-weight:600;")
        outer.addWidget(title_label)

        grid = QGridLayout()
        grid.setSpacing(4)
        grid.setContentsMargins(0, 0, 0, 0)
        outer.addLayout(grid, stretch=1)

        for (label, cmd), (row, column) in zip(
            [top, bottom, left, right],
            [(0, 1), (2, 1), (1, 0), (1, 2)],
            strict=True,
        ):
            button = JogButton(label, cmd)
            button.pressedCmd.connect(self.jog)
            button.releasedCmd.connect(self.stop)
            grid.addWidget(button, row, column, alignment=Qt.AlignCenter)

        # Empty centre cell to give the + shape some breathing room.
        spacer = QLabel()
        spacer.setMinimumSize(56, 56)
        grid.addWidget(spacer, 1, 1)


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
