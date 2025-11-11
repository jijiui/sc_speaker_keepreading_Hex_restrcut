"""Tests for application bootstrap helpers."""

from __future__ import annotations

import unittest

from PyQt6 import QtWidgets

if QtWidgets.QApplication.instance() is None:  # pragma: no cover
    QtWidgets.QApplication([])

from app import bootstrap


class HeadlessSpeechPortTests(unittest.TestCase):
    def test_records_and_clears_spoken_lines(self) -> None:
        port = bootstrap.HeadlessSpeechPort()
        port.speak("  ")
        port.speak("Hello")
        self.assertEqual(["Hello"], port.spoken)

        port.clear_queue()
        self.assertEqual([], port.spoken)

        # Should be safe to call stop multiple times.
        port.stop()
        port.stop()


class BootstrapFactoryTests(unittest.TestCase):
    def test_headless_config_injects_headless_speech_port(self) -> None:
        window = bootstrap.create_main_window(bootstrap.BootstrapConfig(headless=True))
        try:
            self.assertIsInstance(window.tts, bootstrap.HeadlessSpeechPort)
            window.load_timeline  # attribute exists
        finally:
            window.close()
            window.deleteLater()


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
