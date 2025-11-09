#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
============================================================
PvZ 时间轴播报器（桌面端 / Python + PyQt6）
============================================================

用途
----
将“时间—动作”的时间轴（CSV/TXT/Excel）导入后，支持：
1) 双击选择流程 → 进入播报界面；
2) 开始/暂停/重置 计时；
3) 在“提前 N 秒”和正点各播一次相同文本（无“即将：X”前缀）；
4) 表格高亮当前/下一条事件；
5) 全局提前播报开关（统一提前秒数，已不支持按行定制）。

依赖（必要/可选）
-----------------
- 必要：
  - Python 3.9+
  - PyQt6
- 可选：
  - pyttsx3（离线 TTS 语音播报；若缺失则使用打印/蜂鸣作为降级）
  - pandas + openpyxl（读取 Excel .xlsx/.xls，多 Sheet == 多流程）

安装示例
--------
    pip install PyQt6 pyttsx3
    # 如需导入 Excel：
    pip install pandas openpyxl

运行
----
    python "pv_z_时间轴播报器（python_py_qt_6_）.py"

文件格式
--------
- **CSV/TXT**：推荐表头 `人口,时间,动作,备注`，其中 `人口`、`备注` 可留空；兼容旧版 `time,action[,lead]`。
  - 时间支持：`mm:ss`、`mm:ss.mmm`、或纯秒数 `ss`
  - 动作：需要播报/显示的文本（如“网关”“一水晶”）
  - 人口（可选）：支持任意字符串（如 `16/19`，`32` 等）
  - 备注（可选）：补充说明，将在动作列一并展示
  - lead（已废弃）：可保留列但程序会忽略该值，只使用全局提前秒
- **Excel**：每个 Sheet 视为一个独立流程，列名要求与 CSV 相同。

设计要点
--------
- 使用 QTimer 每 100ms tick 一次；
- 每次 tick：推进 elapsed_ms → 更新时钟 → 检测“提前播报/正点播报”；
- 为防止同一 tick 同时播多个事件，采取 “一次 tick 最多一条播报” 策略；
- TTS 独立线程（QThread）串行播报；若无 pyttsx3，使用控制台输出 + Qt 蜂鸣退化。

扩展建议（TODO）
----------------
- 热键自定义、倒计时进度条、计时偏移（例如开局后 X 秒再启动）、
  录制功能（将实时点击记录回写为 CSV）、多语种/多语音支持等。

作者注
------
- 代码内中文注释极其详细；适合直接阅读与二次开发。
"""

from __future__ import annotations

import csv
import io
import sys
import threading
import queue
from pathlib import Path
from typing import Dict, List, Optional

# -------------------------------
# 可选依赖的“安全导入”（失败不报错，后面做功能降级）
# -------------------------------
try:
    import pyttsx3  # 离线 TTS 引擎
    _HAS_TTS = True
except Exception:  # 未安装或初始化失败
    pyttsx3 = None
    _HAS_TTS = False

try:
    import pandas as pd  # 读取 Excel 使用
    _HAS_PANDAS = True
except Exception:
    pd = None
    _HAS_PANDAS = False

# PyQt6 为必需依赖，如缺失应直接报错提示安装
from PyQt6 import QtCore, QtGui, QtWidgets
import time
from opencv_timer_agent import OcrTimerAgent, Roi, parse_roi_string
from core.domain import TimelineEvent, parse_time_to_ms, format_ms_to_clock

# -----------------------------------------------------------
# 表头辅助：兼容中文/英文列名
# -----------------------------------------------------------

def _normalize_header(name: str) -> str:
    text = str(name or "").replace("\ufeff", "").strip().lower()
    return "".join(text.split())


_HEADER_ALIASES = {
    "time": ["time", "时间"],
    "action": ["action", "动作"],
    "population": ["人口", "supply", "population"],
    "note": ["备注", "说明", "备注信息", "注释", "remark", "note", "notes"],
}


def _resolve_header(norm_map: Dict[str, str], key: str) -> Optional[str]:
    for alias in _HEADER_ALIASES.get(key, []):
        norm = _normalize_header(alias)
        if norm in norm_map:
            return norm_map[norm]
    return None

# -----------------------------------------------------------
# 文本读取（CSV/TXT）自动识别编码 + 分隔符嗅探
# -----------------------------------------------------------

def _read_text_autoenc(path: Path) -> tuple[str, str, bool]:
    """以多种编码尝试读取文本，返回 (text, encoding, warned)。

    - 优先尝试常见编码：utf-8, utf-8-sig, gbk/cp936, big5, shift_jis/cp932, cp1252, latin-1
    - 若均失败，则使用 latin-1 强行解码并返回 warned=True（提示可能出现乱码）
    """
    tried = [
        "utf-8", "utf-8-sig",
        "gbk", "cp936",
        "big5",
        "shift_jis", "cp932",
        "cp1252",  # Windows “ANSI”，0x96 常为 – (EN DASH)
        "latin-1",
    ]
    data = path.read_bytes()
    for enc in tried:
        try:
            return data.decode(enc), enc, False
        except Exception:
            pass
    # 兜底：latin-1 强解，返回 warned=True
    return data.decode("latin-1", errors="replace"), "latin-1", True


def _open_csv_stringio_guess(text: str):
    """使用 csv.Sniffer 自动嗅探分隔符，返回 (reader, dialect)。"""
    import csv as _csv
    # 取前 4KB 用于嗅探
    sample = text[:4096]
    try:
        dialect = _csv.Sniffer().sniff(sample, delimiters=",;	|")
    except Exception:
        # 默认按逗号
        dialect = _csv.excel
    return _csv, dialect

# ===========================================================
# 表格模型：将事件列表绑定到 QTableView
# ===========================================================

class TimelineModel(QtCore.QAbstractTableModel):
    """时间轴表格模型（只读）。

    列：人口（可选）｜时间｜动作｜备注（可选）
    - 时间：m:ss 或 m:ss.xx（由 time_ms 格式化）
    - 动作：action 文本
    - 备注：note 列，若无备注可省略
    """

    def __init__(self, events: List[TimelineEvent], parent=None):
        super().__init__(parent)
        # 统一以时间排序，保证渲染与滚动逻辑正确
        self.events = sorted(events, key=lambda e: e.time_ms)
        self._parent = parent
        def _has_value(getter):
            for ev in self.events:
                val = getter(ev)
                if isinstance(val, str):
                    if val.strip():
                        return True
                elif val:
                    return True
            return False
        self.has_population = _has_value(lambda e: e.population)
        self.has_note = _has_value(lambda e: e.note)
        self._columns: List[str] = []
        if self.has_population:
            self._columns.append("population")
        self._columns.append("time")
        self._columns.append("action")
        if self.has_note:
            self._columns.append("note")

    # 表格行数
    def rowCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()) -> int:
        return len(self.events)

    # 表格列数（固定 3 列）
    def columnCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()) -> int:
        return len(self._columns)

    # 数据提供
    def data(self, index: QtCore.QModelIndex, role: QtCore.Qt.ItemDataRole = QtCore.Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        ev = self.events[index.row()]
        col_key = self._columns[index.column()]

        # 主显示文本
        if role == QtCore.Qt.ItemDataRole.DisplayRole:
            if col_key == "population":
                return ev.population or ""
            if col_key == "time":
                return format_ms_to_clock(ev.time_ms)
            if col_key == "action":
                return ev.action
            if col_key == "note":
                return ev.note or ""

        # 对齐：时间列居中
        if role == QtCore.Qt.ItemDataRole.TextAlignmentRole:
            if col_key in {"time", "population"}:
                return int(QtCore.Qt.AlignmentFlag.AlignCenter)

        return None

    # 头部文本
    def headerData(self, section: int, orientation: QtCore.Qt.Orientation, role: QtCore.Qt.ItemDataRole = QtCore.Qt.ItemDataRole.DisplayRole):
        if orientation == QtCore.Qt.Orientation.Horizontal:
            if self._parent and getattr(self._parent, "act_mini", None) and self._parent.act_mini.isChecked():
                return None
        if role == QtCore.Qt.ItemDataRole.DisplayRole:
            if orientation == QtCore.Qt.Orientation.Horizontal:
                key = self._columns[section]
                names = {
                    "time": "时间",
                    "action": "动作",
                    "population": "人口",
                    "note": "备注",
                }
                return names.get(key, key)
            return str(section + 1)
        return None


# ===========================================================
# 语音播报线程：串行消费播报队列
# ===========================================================

class TTSWorker(QtCore.QThread):
    """独立于 UI 的播报线程。

    优先级：
    1) pyttsx3（跨平台，使用系统语音）
    2) Windows SAPI（需要 pywin32；仅 Windows）
    3) 打印 + 蜂鸣（最后兜底）

    - 自动选择 **中文语音**（若检测到 zh/chs/cmn 标记）；若找不到则保持默认语音。
    - 使用队列串行播报，避免多条语音重叠。
    """

    def __init__(self, parent: Optional[QtCore.QObject] = None):
        super().__init__(parent)
        self._queue: "queue.Queue[str]" = queue.Queue()
        self._stop = threading.Event()
        self._engine = None  # pyttsx3.Engine | None
        self._use_sapi = False
        self._sapi_voice = None  # win32com SAPI voice 对象

    def _init_pyttsx3(self):
        """尝试初始化 pyttsx3，并尽量切到中文语音。"""
        if not _HAS_TTS:
            return False
        try:
            eng = pyttsx3.init()
            # 尝试略微加快语速
            try:
                rate = eng.getProperty('rate')
                eng.setProperty('rate', int(rate * 1.05))
            except Exception:
                pass
            # 寻找中文语音（依据 id/name 中是否包含 zh/cmn/chs/cn 等标记）
            try:
                voices = eng.getProperty('voices') or []
                def _is_cn(v):
                    s = f"{getattr(v, 'id', '')} {getattr(v, 'name', '')} {getattr(v, 'languages', '')}".lower()
                    return any(tag in s for tag in ['zh', 'cmn', 'chi', 'chs', 'cn'])
                cn = [v for v in voices if _is_cn(v)]
                if cn:
                    eng.setProperty('voice', cn[0].id)
            except Exception:
                pass
            self._engine = eng
            return True
        except Exception:
            self._engine = None
            return False

    def _init_sapi(self):
        """尝试初始化 Windows SAPI 语音（需要 pywin32）。"""
        try:
            import win32com.client  # type: ignore
            sp = win32com.client.Dispatch("SAPI.SpVoice")
            # 选择中文语音
            try:
                tokens = sp.GetVoices()
                for i in range(tokens.Count):
                    v = tokens.Item(i)
                    desc = v.GetDescription()
                    if any(tag in desc.lower() for tag in ['zh', 'cmn', 'chi', 'chs', 'cn', 'chinese']):
                        sp.Voice = v
                        break
            except Exception:
                pass
            self._sapi_voice = sp
            self._use_sapi = True
            return True
        except Exception:
            self._sapi_voice = None
            self._use_sapi = False
            return False

    def run(self):
        # 先试 pyttsx3；失败再试 Windows SAPI；都失败则降级
        if sys.platform.startswith('win'):
            ok = self._init_sapi()
            if not ok:
                self._init_pyttsx3()
        else:
            self._init_pyttsx3()

        while not self._stop.is_set():
            try:
                text = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue
            if text is None:
                break

            try:
                if self._engine is not None:
                    # 批量聚合：单次 runAndWait 处理多条，降低卡死概率
                    batch = [text]
                    try:
                        while True:
                            nxt = self._queue.get_nowait()
                            if nxt is None:
                                # 保留终止信号
                                self._queue.put(None)
                                break
                            batch.append(nxt)
                    except queue.Empty:
                        pass
                    for t in batch:
                        try:
                            print(f"[TTS] say: {t}")
                        except Exception:
                            pass
                        self._engine.say(t)
                    self._engine.runAndWait()
                elif self._use_sapi and self._sapi_voice is not None:
                    self._sapi_voice.Speak(text)
                else:
                    # 最后兜底：打印 + 蜂鸣
                    print(f"[TTS 模拟] {text}")
                    QtWidgets.QApplication.beep()
            except Exception:
                # 任意播报异常时，继续循环，避免卡死
                print(f"[TTS 播报异常] {text}")
                QtWidgets.QApplication.beep()

    def speak(self, text: str):
        if text and text.strip():
            try:
                print(f"[TTS] enqueue: {text}")
            except Exception:
                pass
            self._queue.put(text)

    def stop(self):
        self._stop.set()
        self._queue.put(None)
        self.wait(500)

    def clear_queue(self):
        """清空待播报队列（重置时调用）。"""
        try:
            while True:
                item = self._queue.get_nowait()
                if item is None:
                    # 保留线程终止信号
                    self._queue.put(None)
                    break
        except queue.Empty:
            pass


# ===========================================================
# 主窗口：文件加载、流程选择、计时控制与播报逻辑
# ===========================================================

class MainWindow(QtWidgets.QMainWindow):
    """应用主窗口。

    左侧：文件/流程列表 + 控制区（开始/暂停/重置 + 提前秒数设置）；
    右侧：大时钟 + 事件表；
    菜单：打开文件、导出示例 CSV、置顶窗口、退出。
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("时间轴播报器（PvZ 战术计时）")
        self.resize(1000, 620)

        # ---- 运行时状态 ----
        self.flows: Dict[str, List[TimelineEvent]] = {}  # 流程名 → 事件列表
        self.current_flow_name: Optional[str] = None     # 当前激活流程名
        self.model: Optional[TimelineModel] = None       # 表格模型
        self.elapsed_ms: int = 0                         # 已用时间（毫秒）
        self.prev_ms: int = 0                            # 上一次采样时间（毫秒）
        self.running: bool = False                       # 运行状态\n        self._last_tick: float = 0.0                     # 上一次 tick 的单调时钟

        # 100ms 刷新时钟与播报判定
        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self._on_tick)

        # 全局“提前播报秒数”（当前版本仅支持统一提前量）
        self.global_lead_ms = 2000  # 默认 2 秒

        # 语音线程
        self.tts = TTSWorker(self)
        self.tts.start()

        # 构建 UI
        self._build_ui()
        self._mini_mode = False
        self._before_mini_geometry: Optional[QtCore.QRect] = None
        self._prev_window_flags: Optional[QtCore.Qt.WindowFlags] = None
        self._left_visible_before_mini = True
        self._dragging = False
        self._drag_offset = QtCore.QPoint()

        central = self.centralWidget()
        if central is not None:
            central.installEventFilter(self)
        for w in (
            getattr(self, "left_panel", None),
            getattr(self, "right_panel", None),
            getattr(self.table, "viewport", lambda: None)(),
            getattr(self, "mini_toolbar", None),
        ):
            if w is not None:
                w.installEventFilter(self)

    # ---------- 生命周期 ----------
    def closeEvent(self, event: QtGui.QCloseEvent):
        # 退出时优雅停止 TTS 线程
        try:
            self.tts.stop()
        except Exception:
            pass
        super().closeEvent(event)

    # ---------- UI 构建 ----------
    def _build_ui(self):
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        layout.addWidget(self.splitter)

        # 左列：大时钟 + 文件/流程列表 + 控制区
        self.left_panel = QtWidgets.QWidget()
        left = QtWidgets.QVBoxLayout(self.left_panel)
        left.setContentsMargins(8, 8, 8, 8)
        left.setSpacing(6)
        self.splitter.addWidget(self.left_panel)

        clock_font = QtGui.QFont()
        clock_font.setPointSize(26)
        clock_font.setBold(True)
        self.clock_lbl = QtWidgets.QLabel("0:00")
        self.clock_lbl.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        self.clock_lbl.setFont(clock_font)
        left.addWidget(self.clock_lbl)

        # 打开文件按钮
        open_btn = QtWidgets.QPushButton("打开时间轴文件（CSV/TXT/Excel）")
        open_btn.clicked.connect(self.open_file)
        left.addWidget(open_btn)

        # 流程列表（支持 Excel 多 Sheet）
        self.flow_list = QtWidgets.QListWidget()
        self.flow_list.itemDoubleClicked.connect(self.on_flow_double_clicked)
        left.addWidget(self.flow_list, 1)

        # 控制按钮：开始/暂停/重置
        controls = QtWidgets.QHBoxLayout()
        self.start_btn = QtWidgets.QPushButton("开始")
        self.start_btn.clicked.connect(self.start)
        self.pause_btn = QtWidgets.QPushButton("暂停")
        self.pause_btn.clicked.connect(self.pause)
        self.reset_btn = QtWidgets.QPushButton("重置")
        self.reset_btn.clicked.connect(self.reset)
        controls.addWidget(self.start_btn)
        controls.addWidget(self.pause_btn)
        controls.addWidget(self.reset_btn)
        # 始终置顶开关（与菜单项联动）
        self.top_chk = QtWidgets.QCheckBox("置顶")
        self.top_chk.setToolTip("窗口始终置顶（快捷键: T）")
        self.top_chk.toggled.connect(self._sync_on_top_from_checkbox)
        controls.addWidget(self.top_chk)
        left.addLayout(controls)
        # 同步 OCR 启停（按钮点击后 0ms 调度）
        try:
            self.start_btn.clicked.connect(lambda: QtCore.QTimer.singleShot(0, self._sync_ocr_agent_enabled))
            self.pause_btn.clicked.connect(lambda: QtCore.QTimer.singleShot(0, self._sync_ocr_agent_enabled))
            self.reset_btn.clicked.connect(lambda: QtCore.QTimer.singleShot(0, self._sync_ocr_agent_enabled))
            # 重置时清空“检测到游戏时间”显示
            self.reset_btn.clicked.connect(lambda: self.ocr_seen_lbl.setText("-"))
        except Exception:
            pass

        # ---- 自动计时（OCR）控件 ----
        ocr_row1 = QtWidgets.QHBoxLayout()
        self.auto_chk = QtWidgets.QCheckBox("自动计时")
        ocr_row1.addWidget(self.auto_chk)
        ocr_row1.addWidget(QtWidgets.QLabel("检测到游戏时间："))
        self.ocr_seen_lbl = QtWidgets.QLabel("-")
        self.ocr_seen_lbl.setMinimumWidth(80)
        ocr_row1.addWidget(self.ocr_seen_lbl, 1)
        left.addLayout(ocr_row1)

        ocr_row2 = QtWidgets.QHBoxLayout()
        self.roi_edit = QtWidgets.QLineEdit()
        self.roi_edit.setPlaceholderText("x,y,w,h")
        self.roi_btn = QtWidgets.QPushButton("框选区域")
        ocr_row2.addWidget(self.roi_edit, 1)
        ocr_row2.addWidget(self.roi_btn)
        left.addLayout(ocr_row2)

        # 提前播报秒数（全局，可被每行覆写）
        lead_layout = QtWidgets.QHBoxLayout()
        lead_layout.addWidget(QtWidgets.QLabel("提前播报（秒）："))
        self.lead_spin = QtWidgets.QDoubleSpinBox()
        self.lead_spin.setRange(0.0, 30.0)
        self.lead_spin.setDecimals(1)
        self.lead_spin.setSingleStep(0.5)
        self.lead_spin.setValue(self.global_lead_ms / 1000.0)
        self.lead_spin.valueChanged.connect(self._on_lead_changed)
        lead_layout.addWidget(self.lead_spin)
        # 播报选项：整点/提前
        self.on_time_chk = QtWidgets.QCheckBox("整点播报")
        self.on_time_chk.setChecked(True)
        lead_layout.addWidget(self.on_time_chk)
        self.early_chk = QtWidgets.QCheckBox("提前播报")
        lead_layout.addWidget(self.early_chk)
        left.addLayout(lead_layout)

        # 状态文本
        self.status_lbl = QtWidgets.QLabel("未加载时间轴")
        left.addWidget(self.status_lbl)

        # 右列：大时钟 + 表格
        self.right_panel = QtWidgets.QWidget()
        right = QtWidgets.QVBoxLayout(self.right_panel)
        right.setContentsMargins(8, 8, 8, 8)
        right.setSpacing(6)
        self.splitter.addWidget(self.right_panel)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self._last_splitter_sizes: Optional[List[int]] = None

        # 极简模式工具条（默认隐藏）
        self.mini_toolbar = QtWidgets.QWidget()
        mini_layout = QtWidgets.QHBoxLayout(self.mini_toolbar)
        mini_layout.setContentsMargins(0, 0, 0, 0)
        mini_layout.setSpacing(4)
        self.mini_countdown_lbl = QtWidgets.QLabel("--")
        mini_layout.addWidget(self.mini_countdown_lbl)
        mini_layout.addStretch()
        self.mini_restore_btn = QtWidgets.QToolButton()
        self.mini_restore_btn.setText("恢复")
        self.mini_restore_btn.setAutoRaise(True)
        self.mini_restore_btn.clicked.connect(lambda: self.act_mini.setChecked(False))
        mini_layout.addWidget(self.mini_restore_btn)
        self.mini_close_btn = QtWidgets.QToolButton()
        self.mini_close_btn.setText("关闭")
        self.mini_close_btn.setAutoRaise(True)
        self.mini_close_btn.clicked.connect(self.close)
        mini_layout.addWidget(self.mini_close_btn)
        self.mini_size_grip = QtWidgets.QSizeGrip(self.mini_toolbar)
        mini_layout.addWidget(self.mini_size_grip, 0, QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignBottom)
        self.mini_toolbar.hide()
        right.addWidget(self.mini_toolbar)

        # 事件表格
        self.table = QtWidgets.QTableView()
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        right.addWidget(self.table, 1)

        # 快捷键：空格切换开始/暂停，R 重置，O 打开文件，T 置顶
        QtGui.QShortcut(QtGui.QKeySequence("Space"), self, activated=self._toggle_run)
        QtGui.QShortcut(QtGui.QKeySequence("R"), self, activated=self.reset)
        QtGui.QShortcut(QtGui.QKeySequence("O"), self, activated=self.open_file)
        QtGui.QShortcut(QtGui.QKeySequence("T"), self, activated=self._toggle_always_on_top)
        QtGui.QShortcut(QtGui.QKeySequence("Esc"), self, activated=self._leave_mini_if_needed)

        # 菜单栏
        bar = self.menuBar()
        file_menu = bar.addMenu("文件")

        act_open = QtGui.QAction("打开…", self)
        act_open.triggered.connect(self.open_file)
        file_menu.addAction(act_open)

        act_sample = QtGui.QAction("导出示例 CSV…", self)
        act_sample.triggered.connect(self.export_sample_csv)
        file_menu.addAction(act_sample)

        act_quit = QtGui.QAction("退出", self)
        act_quit.triggered.connect(self.close)
        file_menu.addAction(act_quit)

        view_menu = bar.addMenu("视图")
        self.act_mini = QtGui.QAction("极简小窗模式", self, checkable=True)
        self.act_mini.toggled.connect(self._set_mini_mode)
        view_menu.addAction(self.act_mini)
        view_menu.addSeparator()
        self.act_toggle_left = QtGui.QAction("显示左侧控制区", self, checkable=True, checked=True)
        self.act_toggle_left.toggled.connect(self._set_left_panel_visible)
        view_menu.addAction(self.act_toggle_left)
        self.act_top = QtGui.QAction("窗口置顶", self, checkable=True)
        self.act_top.toggled.connect(self._apply_always_on_top)
        # 与工具区复选框联动，保持显示一致
        self.act_top.toggled.connect(self.top_chk.setChecked)
        view_menu.addAction(self.act_top)
        # 初始化 OCR 自动计时模块（UI 已构建完成）
        try:
            self._init_ocr_agent()
        except Exception:
            pass

        QtCore.QTimer.singleShot(
            0, lambda: self.splitter.setSizes([320, max(360, self.width() - 320)])
        )

    # ---------- 打开/读取文件 ----------
    def open_file(self):
        """弹框选择 CSV/TXT/Excel 文件并加载。"""
        path_str, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "选择时间轴文件",
            filter="时间轴文件 (*.csv *.txt *.xlsx *.xls);;所有文件 (*.*)"
        )
        if not path_str:
            return
        self.load_timeline(Path(path_str))

    def load_timeline(self, path: Path):
        """加载指定文件，解析得到 flows（可能多流程）并填充左侧列表。"""
        try:
            flows = self._read_flows_from_file(path)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "读取失败", f"无法读取文件：\n{e}")
            return

        self.flows = flows
        self.flow_list.clear()
        for name in flows.keys():
            self.flow_list.addItem(name)

        if not flows:
            self.status_lbl.setText("未在文件中找到有效时间轴")
            return

        # 自动选择第一个流程
        first_item = self.flow_list.item(0)
        if first_item:
            self.flow_list.setCurrentItem(first_item)
            self._set_active_flow(first_item.text())

        self.status_lbl.setText(f"已加载：{path.name}（{len(flows)} 个流程）")

    def _read_flows_from_file(self, path: Path) -> Dict[str, List[TimelineEvent]]:
        """根据后缀选择解析器，返回 {流程名: 事件列表}。"""
        flows: Dict[str, List[TimelineEvent]] = {}
        suffix = path.suffix.lower()

        if suffix in (".csv", ".txt"):
            events = self._read_csv_like(path)
            flows[path.stem] = events
            return flows

        if suffix in (".xlsx", ".xls"):
            if not _HAS_PANDAS:
                raise RuntimeError("读取 Excel 需要安装 pandas 与 openpyxl：\n  pip install pandas openpyxl")
            # 读取所有 Sheet；每个 sheet 一个流程
            xls = pd.read_excel(path, sheet_name=None)
            for sheet, df in xls.items():
                events = self._events_from_dataframe(df)
                if events:
                    flows[f"{path.stem}/{sheet}"] = events
            return flows

        raise RuntimeError("仅支持 CSV/TXT/XLSX/XLS")

    def _read_csv_like(self, path: Path) -> List[TimelineEvent]:
        """按 CSV 读取（TXT 也按 CSV 读取）。

        - 自动识别编码（解决 'utf-8' codec can't decode byte 0x96 ...）
        - 自动嗅探分隔符（逗号/分号/制表符/竖线）
        - 需要表头至少包含：time, action
        """
        # 1) 自动识别编码
        text, encoding, warned = _read_text_autoenc(path)

        # 2) 用 StringIO + csv.Sniffer 解析
        sio = io.StringIO(text)
        _csv, dialect = _open_csv_stringio_guess(text)
        reader = _csv.DictReader(sio, dialect=dialect)
        headers = reader.fieldnames or []
        norm_map = {_normalize_header(h): h for h in headers}

        time_col = _resolve_header(norm_map, "time")
        action_col = _resolve_header(norm_map, "action")
        if not time_col or not action_col:
            raise RuntimeError("CSV/TXT 需包含表头：时间,动作（可选：人口/备注）")
        pop_col = _resolve_header(norm_map, "population")
        note_col = _resolve_header(norm_map, "note")

        events: List[TimelineEvent] = []
        for row in reader:
            try:
                t_ms = parse_time_to_ms(str(row.get(time_col, "")))
                action = str(row.get(action_col, "")).strip()
                if not action:
                    continue
                population = None
                if pop_col:
                    pop_raw = str(row.get(pop_col, "")).strip()
                    population = pop_raw or None
                note = None
                if note_col:
                    note_raw = str(row.get(note_col, "")).strip()
                    note = note_raw or None
                events.append(
                    TimelineEvent(
                        time_ms=t_ms,
                        action=action,
                        population=population,
                        note=note,
                    )
                )
            except Exception as e:
                print(f"[CSV] 跳过一行：{e}")

        # 4) 若非 UTF-8/被强制解码，给出一次友好提示（此处直接内联字符串，避免 msg 变量）
        if warned:
            QtWidgets.QMessageBox.warning(
                self,
                "编码提示",
                f"文件以 {encoding} 解码，部分字符可能显示异常。\n建议使用 UTF-8 保存以获得最佳兼容。",
            )

        events.sort(key=lambda e: e.time_ms)
        return events


    def _events_from_dataframe(self, df) -> List[TimelineEvent]:
        """从 pandas.DataFrame 中提取事件列表（Excel 使用）。"""
        norm_map = {_normalize_header(c): c for c in df.columns}
        time_col = _resolve_header(norm_map, "time")
        action_col = _resolve_header(norm_map, "action")
        if not time_col or not action_col:
            return []
        pop_col = _resolve_header(norm_map, "population")
        note_col = _resolve_header(norm_map, "note")

        events: List[TimelineEvent] = []
        for _, row in df.iterrows():
            t_val = row[time_col]
            a_val = row[action_col]
            if pd.isna(t_val) or pd.isna(a_val):
                continue
            try:
                t_ms = parse_time_to_ms(str(t_val))
                action = str(a_val).strip()
                if not action:
                    continue
                population = None
                if pop_col:
                    pv = row.get(pop_col)
                    if pv is not None and not pd.isna(pv):
                        pop_str = str(pv).strip()
                        population = pop_str or None
                note = None
                if note_col:
                    nv = row.get(note_col)
                    if nv is not None and not pd.isna(nv):
                        note_str = str(nv).strip()
                        note = note_str or None
                events.append(
                    TimelineEvent(
                        time_ms=t_ms,
                        action=action,
                        population=population,
                        note=note,
                    )
                )
            except Exception as e:
                print(f"[XLSX] 跳过一行：{e}")
        events.sort(key=lambda e: e.time_ms)
        return events

    # ---------- 切换流程/双击开始 ----------
    def _set_active_flow(self, name: str):
        """根据流程名切换当前事件表，并自动重置计时。"""
        evs = self.flows.get(name, [])
        self.model = TimelineModel(evs, parent=self)
        self.table.setModel(self.model)
        if "population" in self.model._columns:
            col_idx = self.model._columns.index("population")
            self.table.setColumnWidth(col_idx, 80)
        if "time" in self.model._columns:
            col_idx = self.model._columns.index("time")
            self.table.setColumnWidth(col_idx, 80)
        if "action" in self.model._columns:
            col_idx = self.model._columns.index("action")
            self.table.setColumnWidth(col_idx, 360)
        if "note" in self.model._columns:
            col_idx = self.model._columns.index("note")
            self.table.setColumnWidth(col_idx, 420)
        self.current_flow_name = name
        self.reset()  # 加载新流程后，自动重置为 0:00

    def on_flow_double_clicked(self, item: QtWidgets.QListWidgetItem):
        self._set_active_flow(item.text())
        self.start()  # 双击即开跑（符合“点流程立即开始”的习惯）

    # ---------- 控制区：开始/暂停/重置 ----------
    def _on_lead_changed(self, val: float):
        """全局提前播报秒数变化（单位：秒 → 保存为毫秒）。"""
        self.global_lead_ms = int(val * 1000)

    def _toggle_run(self):
        """空格：开始 ↔ 暂停。"""
        if self.running:
            self.pause()
        else:
            self.start()

    def start(self):
        """开始计时。若尚未加载流程，提示用户。"""
        if not self.model:
            QtWidgets.QMessageBox.information(self, "提示", "请先加载一个时间轴流程。")
            return
        self.running = True
        self.timer.start()
        self.status_lbl.setText(f"运行中：{self.current_flow_name}")
        # 对齐 prev_ms，避免瞬时跨界，并记录墙钟起点
        self.prev_ms = self.elapsed_ms
        self._last_tick = time.perf_counter()

        # OCR 自动计时：启动时视为未锁定，等待首次识别
        self.ocr_locked = False

    def pause(self):
        """暂停计时。"""
        self.running = False
        self.timer.stop()
        self.status_lbl.setText("已暂停")
        # 对齐 prev_ms，避免恢复时误触发，并清空墙钟起点
        self.prev_ms = self.elapsed_ms
        self._last_tick = 0.0

        # OCR 自动计时：暂停后清除锁定
        self.ocr_locked = False

    def reset(self):
        """重置计时并清空播报队列。"""
        self.running = False
        self.timer.stop()
        self.elapsed_ms = 0
        self.prev_ms = 0
        self._last_tick = 0.0
        # 清空 TTS 待播队列，避免上一轮残留
        try:
            if hasattr(self, 'tts') and self.tts:
                self.tts.clear_queue()
        except Exception:
            pass
        self._update_clock()
        self.status_lbl.setText("已重置")

    # ---------- 计时心跳 ----------
    def _on_tick(self):
        """每 100ms 调用：推进时间、更新显示、处理播报。"""
        if not self.running or not self.model:
            return
        # 自动计时优先：无识别→不计时；有识别→不自增，仅刷新/判定
        try:
            if hasattr(self, 'auto_chk') and self.auto_chk.isChecked():
                ocr_enabled = hasattr(self, 'ocr_agent') and self.ocr_agent.is_enabled()
                ocr_locked = bool(getattr(self, 'ocr_locked', False))
                if (not ocr_enabled) or (not ocr_locked):
                    try:
                        self.clock_lbl.setText("没检测到")
                    except Exception:
                        pass
                    return
                self._update_clock()
                self._check_announcements_simple()
                return
        except Exception:
            pass
        # 真实时间推进：使用单调时钟差值，避免 QTimer 抖动变慢
        now = time.perf_counter()
        if not hasattr(self, '_last_tick') or not self._last_tick:
            self._last_tick = now
        delta_ms = max(0, int((now - self._last_tick) * 1000))
        self._last_tick = now
        self.elapsed_ms += delta_ms
        self._update_clock()
        self._check_announcements_simple()
        # 更新 prev_ms（基于手动推进）
        self.prev_ms = self.elapsed_ms

    def _update_clock(self):
        """刷新大时钟，并滚动表格定位到“下一条未播事件”。"""
        clock_text = format_ms_to_clock(self.elapsed_ms)
        self.clock_lbl.setText(clock_text)

        # 高亮下一条（time_ms >= 当前时间）的事件
        if self.model:
            idx = self._next_event_row_simple()
            if idx is not None and idx >= 0:
                self.table.selectRow(idx)
                hint = (
                    QtWidgets.QAbstractItemView.ScrollHint.PositionAtTop
                    if self.act_mini.isChecked()
                    else QtWidgets.QAbstractItemView.ScrollHint.PositionAtCenter
                )
                self.table.scrollTo(self.model.index(idx, 0), hint)
                next_ev = self.model.events[idx]
                diff_ms = max(0, next_ev.time_ms - self.elapsed_ms)
                self.mini_countdown_lbl.setText(format_ms_to_clock(diff_ms))
            else:
                self.mini_countdown_lbl.setText("--")
        else:
            self.mini_countdown_lbl.setText("--")

    # ---------- 基于跨界的简化播报判定（不维护逐条状态） ----------
    def _next_event_row_simple(self) -> Optional[int]:
        """返回第一条 time_ms >= 当前 elapsed_ms 的行号（用于高亮）。"""
        if not self.model:
            return None
        for i, ev in enumerate(self.model.events):
            if ev.time_ms >= self.elapsed_ms:
                return i
        return len(self.model.events) - 1 if self.model.events else None

    def _check_announcements_simple(self):
        """只关注下一条事件，依据 prev_ms→elapsed_ms 的跨界判断是否播报一次。

        - 正点：prev_ms < time_ms <= elapsed_ms → 播一次 action
        - 提前：prev_ms < (time_ms - advance_ms) <= elapsed_ms 且 elapsed_ms < time_ms → 播一次 action（advance_ms 源于全局提前秒）
        - 每个 tick 最多播一条；不维护每条事件的“已播报/提前”状态
        """
        if not self.model or not self.model.events:
            return
        ps = getattr(self, 'prev_ms', 0)
        cs = self.elapsed_ms
        if cs <= ps:
            return
        for ev in self.model.events:
            # 选项：整点/提前
            try:
                on_time_enabled = self.on_time_chk.isChecked()
            except Exception:
                on_time_enabled = True
            try:
                early_enabled = self.early_chk.isChecked()
            except Exception:
                early_enabled = False
            # 提前毫秒：当“提前播报”开启时，统一使用全局提前秒
            advance_ms = self.global_lead_ms if early_enabled else 0
            early_start = max(0, ev.time_ms - advance_ms)
            # 正点跨界优先（需开启整点播报）
            if on_time_enabled and (ps < ev.time_ms <= cs):
                self._speak(ev.action)
                break
            # 提前跨界（需开启提前播报；不说“即将”）
            if (advance_ms > 0) and (ps < early_start <= cs) and (cs < ev.time_ms):
                self._speak(ev.action)
                break

    # ---------- 播报封装 ----------
    def _speak(self, text: str):
        """统一入口：将文本交给 TTS 线程；若失败则蜂鸣+打印。"""
        if not text.strip():
            return
        try:
            self.tts.speak(text)
        except Exception:
            print(f"[TTS 调用失败] {text}")
            QtWidgets.QApplication.beep()

    # ---------- 置顶窗口 ----------
    def _toggle_always_on_top(self):
        self.act_top.toggle()

    def _apply_always_on_top(self, enabled: bool):
        # 通过窗口标志位实现置顶/取消置顶
        flags = self.windowFlags()
        if enabled:
            self.setWindowFlag(QtCore.Qt.WindowType.WindowStaysOnTopHint, True)
        else:
            self.setWindowFlag(QtCore.Qt.WindowType.WindowStaysOnTopHint, False)
        self.setWindowFlags(self.windowFlags())
        self.show()

    # ---------- 导出示例 CSV ----------
    def _sync_on_top_from_checkbox(self, enabled: bool):
        """从工具区复选框切换置顶时，驱动菜单动作（从而统一应用效果）。"""
        try:
            # 将状态写回菜单动作；其toggled会调用_apply_always_on_top
            self.act_top.setChecked(enabled)
        except Exception:
            # 初始化阶段（菜单尚未创建）直接应用
            self._apply_always_on_top(enabled)

    def _set_left_panel_visible(self, visible: bool) -> None:
        if visible:
            self.left_panel.show()
            if self._last_splitter_sizes and sum(self._last_splitter_sizes) > 0:
                sizes = list(self._last_splitter_sizes)
            else:
                sizes = [320, max(360, self.width() - 320)]
            QtCore.QTimer.singleShot(0, lambda s=sizes: self.splitter.setSizes(s))
        else:
            self._last_splitter_sizes = self.splitter.sizes()
            self.left_panel.hide()
            QtCore.QTimer.singleShot(
                0, lambda: self.splitter.setSizes([0, max(200, self.width())])
            )
        if self.act_toggle_left.isChecked() != visible:
            self.act_toggle_left.blockSignals(True)
            self.act_toggle_left.setChecked(visible)
            self.act_toggle_left.blockSignals(False)

    def _set_mini_mode(self, enabled: bool) -> None:
        if enabled == self._mini_mode:
            return
        self._mini_mode = enabled
        self.act_toggle_left.setEnabled(not enabled)
        self.mini_toolbar.setVisible(enabled)
        try:
            self.table.horizontalHeader().setVisible(not enabled)
        except Exception:
            pass
        if enabled:
            self._before_mini_geometry = self.geometry()
            self._prev_window_flags = self.windowFlags()
            self._left_visible_before_mini = self.left_panel.isVisible()
            if self.act_toggle_left.isChecked():
                self.act_toggle_left.setChecked(False)
            mb = self.menuBar()
            if mb is not None:
                mb.setVisible(False)
            new_flags = (
                QtCore.Qt.WindowType.Window
                | QtCore.Qt.WindowType.FramelessWindowHint
                | QtCore.Qt.WindowType.WindowSystemMenuHint
            )
            self.setWindowFlags(new_flags)
            self._apply_always_on_top(self.act_top.isChecked())
            self.show()
        else:
            mb = self.menuBar()
            if mb is not None:
                mb.setVisible(True)
            restore_flags = self._prev_window_flags or QtCore.Qt.WindowType.Window
            self.setWindowFlags(restore_flags)
            self._apply_always_on_top(self.act_top.isChecked())
            self.show()
            if self._before_mini_geometry:
                self.setGeometry(self._before_mini_geometry)
            if self._left_visible_before_mini:
                self.act_toggle_left.setChecked(True)
            self.act_toggle_left.setEnabled(True)
            self._dragging = False

    def _leave_mini_if_needed(self) -> None:
        if self.act_mini.isChecked():
            self.act_mini.setChecked(False)

    def eventFilter(self, obj, event):
        if self._mini_mode:
            if event.type() == QtCore.QEvent.Type.MouseButtonPress:
                if getattr(event, "button", lambda: None)() == QtCore.Qt.MouseButton.LeftButton:
                    gp = getattr(event, "globalPosition", lambda: QtCore.QPointF())().toPoint()
                    self._dragging = True
                    self._drag_offset = gp - self.frameGeometry().topLeft()
            elif event.type() == QtCore.QEvent.Type.MouseMove and self._dragging:
                if getattr(event, "buttons", lambda: QtCore.Qt.MouseButton.NoButton)() & QtCore.Qt.MouseButton.LeftButton:
                    gp = getattr(event, "globalPosition", lambda: QtCore.QPointF())().toPoint()
                    self.move(gp - self._drag_offset)
            elif event.type() == QtCore.QEvent.Type.MouseButtonRelease:
                if getattr(event, "button", lambda: None)() == QtCore.Qt.MouseButton.LeftButton:
                    self._dragging = False
        return super().eventFilter(obj, event)

    # ---------- OCR 自动计时（初始化与桥接） ----------
    def _init_ocr_agent(self):
        # Settings: persist ROI and auto checkbox
        self.settings = QtCore.QSettings("sc_speaker", "pvz_timeline")
        self.ocr_agent = OcrTimerAgent(self, interval_ms=200, scale=3, score_thresh=0.55)
        # 初始未锁定识别
        self.ocr_locked = False

        # Restore settings
        try:
            roi_str = self.settings.value("ocr/roi", "", type=str)
        except Exception:
            roi_str = ""
        if roi_str:
            if self.ocr_agent.set_roi_from_string(roi_str):
                self.roi_edit.setText(roi_str)
        try:
            auto_on = bool(self.settings.value("ocr/auto", False, type=bool))
        except Exception:
            auto_on = False
        self.auto_chk.setChecked(auto_on)

        # Restore broadcast options
        try:
            on_time_on = bool(self.settings.value("opt/on_time", True, type=bool))
        except Exception:
            on_time_on = True
        try:
            early_on = bool(self.settings.value("opt/early", False, type=bool))
        except Exception:
            early_on = False
        try:
            self.on_time_chk.setChecked(on_time_on)
            self.early_chk.setChecked(early_on)
        except Exception:
            pass

        # Wire signals
        self.roi_btn.clicked.connect(lambda: self.ocr_agent.select_roi(self))
        self.roi_edit.editingFinished.connect(self._on_roi_edit_changed)
        self.auto_chk.toggled.connect(self._on_auto_chk_toggled)
        self.ocr_agent.roiSelected.connect(self._on_roi_selected)
        self.ocr_agent.timeDetected.connect(self._on_ocr_time_detected)
        # Save broadcast options
        try:
            self.on_time_chk.toggled.connect(lambda v: self.settings.setValue("opt/on_time", bool(v)))
            self.early_chk.toggled.connect(lambda v: self.settings.setValue("opt/early", bool(v)))
        except Exception:
            pass

        # Initial enable sync
        self._sync_ocr_agent_enabled()

    def _on_roi_edit_changed(self):
        text = self.roi_edit.text().strip()
        ok = self.ocr_agent.set_roi_from_string(text)
        if ok:
            self.settings.setValue("ocr/roi", text)
            # ROI 变化后需重新锁定
            self.ocr_locked = False
        self._sync_ocr_agent_enabled()

    def _on_roi_selected(self, x: int, y: int, w: int, h: int):
        s = f"{x},{y},{w},{h}"
        self.roi_edit.setText(s)
        self.settings.setValue("ocr/roi", s)
        # ROI 变化后需重新锁定
        self.ocr_locked = False
        self._sync_ocr_agent_enabled()

    def _on_auto_chk_toggled(self, enabled: bool):
        self.settings.setValue("ocr/auto", bool(enabled))
        # 切换自动计时后重新锁定
        self.ocr_locked = False
        self._sync_ocr_agent_enabled()

    def _sync_ocr_agent_enabled(self):
        # Enabled when: user checked + currently running + ROI valid
        want = False
        try:
            roi = self.ocr_agent.get_roi()
            want = bool(self.auto_chk.isChecked() and self.running and roi is not None and roi.is_valid())
        except Exception:
            want = False
        self.ocr_agent.set_enabled(want)

    def _on_ocr_time_detected(self, time_text: str, ms: int):
        # Update label always
        try:
            self.ocr_seen_lbl.setText(time_text)
        except Exception:
            pass
        # Only drive announcements when running
        if not self.running:
            return
        # 锁定：后续 tick 由 OCR 驱动
        # 首次锁定：对齐 prev_ms，避免锚定瞬间触发提前播报
        if not getattr(self, 'ocr_locked', False):
            self.ocr_locked = True
            self.elapsed_ms = ms
            self.prev_ms = ms
            self._update_clock()
            return
        self.ocr_locked = True
        self.elapsed_ms = ms
        self._update_clock()
        self._check_announcements_simple()
        # OCR 推进后对齐 prev_ms
        self.prev_ms = self.elapsed_ms

    def export_sample_csv(self):
        """导出一份示例时间轴 CSV（含 PvZ 方案B 的节点）。"""
        sample = (
            "人口,时间,动作,备注\n"
            "14/15,0:17,一水晶,\n"
            "16/19,0:38,网关,\n"
            "18/23,0:44,一气,\n"
            "26/31,1:38,二基地（自然口）,补探机\n"
            "28/31,1:50,核心,\n"
            "30/34,2:05,二水晶,\n"
            "34/42,2:40,折跃门研究,\n"
            "36/44,3:10,暮光议会,\n"
            "40/52,3:25,熔炉（+1攻）,排队升级\n"
            "46/60,4:00,机械台,\n"
            "48/64,4:10,研究冲锋,\n"
            "50/66,4:15,研究+1攻,\n"
            "54/72,5:00,圣堂武士档案馆,\n"
            "56/74,5:05,棱镜,\n"
            "60/80,5:20,补门到7门,\n"
            "66/90,5:50,补门到10门,\n"
            "68/92,6:05,停探机至66–68,\n"
            "70/100,6:10,全门刷狂热者,\n"
            "74/106,6:50,插前哨水晶,\n"
            "82/114,7:20,撞三矿开团,\n"
        )

        path_str, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "导出示例 CSV", filter="CSV 文件 (*.csv)"
        )
        if not path_str:
            return
        path = Path(path_str)
        try:
            path.write_text(sample, encoding="utf-8")
            QtWidgets.QMessageBox.information(self, "已导出", f"示例 CSV 已保存至：\n{path}")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "保存失败", f"无法保存：\n{e}")


# ===========================================================
# 入口函数
# ===========================================================

def main():
    app = QtWidgets.QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

