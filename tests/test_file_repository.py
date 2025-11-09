"""Tests for FileTimelineRepository parsing flows from CSV/Excel sources."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Dict, List

import unittest

from app.infra.file_repository import FileTimelineRepository, _HAS_PANDAS

if _HAS_PANDAS:
    import pandas as pd  # type: ignore


class FileTimelineRepositoryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = FileTimelineRepository()

    def _write_text(self, text: str, suffix: str) -> Path:
        fd = tempfile.NamedTemporaryFile("w", delete=False, suffix=suffix, encoding="utf-8")
        try:
            fd.write(text)
            fd.flush()
        finally:
            fd.close()
        path = Path(fd.name)
        self.addCleanup(lambda: path.unlink(missing_ok=True))
        return path

    def test_load_csv_single_flow(self) -> None:
        path = self._write_text("时间,动作\n0:10,侦查\n0:20,补水晶\n", ".csv")
        flows = self.repo.load(path)
        self.assertEqual(list(flows.keys()), [path.stem])
        events = flows[path.stem]
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0].action, "侦查")
        self.assertEqual(events[1].time_ms, 20_000)

    @unittest.skipUnless(_HAS_PANDAS, "pandas/openpyxl required for Excel test")
    def test_load_excel_multi_sheet(self) -> None:
        df_a = pd.DataFrame({"时间": ["0:15"], "动作": ["一水晶"]})
        df_b = pd.DataFrame({"时间": ["0:30"], "动作": ["网关"]})
        temp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
        temp.close()
        with pd.ExcelWriter(temp.name, engine="openpyxl") as writer:  # type: ignore[arg-type]
            df_a.to_excel(writer, sheet_name="FlowA", index=False)
            df_b.to_excel(writer, sheet_name="FlowB", index=False)
        flows = self.repo.load(Path(temp.name))
        path = Path(temp.name)
        self.addCleanup(lambda: path.unlink(missing_ok=True))
        keys = list(flows.keys())
        self.assertTrue(any(key.endswith("/FlowA") for key in keys))
        self.assertTrue(any(key.endswith("/FlowB") for key in keys))
        total_events = sum(len(v) for v in flows.values())
        self.assertEqual(total_events, 2)


if __name__ == "__main__":
    unittest.main()
