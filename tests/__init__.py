"""Test helpers for the PvZ timeline speaker."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtWidgets

_APP = QtWidgets.QApplication.instance()
if _APP is None:  # pragma: no cover - ensures widgets can be created
    _APP = QtWidgets.QApplication([])


def _return_ok(*_args, **_kwargs) -> QtWidgets.QMessageBox.StandardButton:
    return QtWidgets.QMessageBox.StandardButton.Ok


def _fake_file_dialog(*_args, **_kwargs) -> tuple[str, str]:
    return ("", "")


# Prevent modal dialog blocks during unit tests.
QtWidgets.QMessageBox.information = _return_ok  # type: ignore[assignment]
QtWidgets.QMessageBox.warning = _return_ok  # type: ignore[assignment]
QtWidgets.QMessageBox.critical = _return_ok  # type: ignore[assignment]
QtWidgets.QMessageBox.question = _return_ok  # type: ignore[assignment]

QtWidgets.QFileDialog.getOpenFileName = _fake_file_dialog  # type: ignore[assignment]
QtWidgets.QFileDialog.getSaveFileName = _fake_file_dialog  # type: ignore[assignment]
