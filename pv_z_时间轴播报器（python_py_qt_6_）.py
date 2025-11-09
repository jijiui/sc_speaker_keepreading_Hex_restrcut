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

import sys
import threading
import queue
from pathlib import Path
from typing import List, Optional

# -------------------------------
# 可选依赖的“安全导入”（失败不报错，后面做功能降级）
# -------------------------------
try:
    import pyttsx3  # 离线 TTS 引擎
    _HAS_TTS = True
except Exception:  # 未安装或初始化失败
    pyttsx3 = None
    _HAS_TTS = False

# PyQt6 为必需依赖，如缺失应直接报错提示安装
from PyQt6 import QtCore, QtGui, QtWidgets
import time
from opencv_timer_agent import OcrTimerAgent, Roi, parse_roi_string
from core.domain import TimelineEvent, parse_time_to_ms, format_ms_to_clock
from core.ports import PreferenceStore, TimelineRepository, SpeechPort, TimeSourcePort
from core.services import TimelineService
from infra.file_repository import FileTimelineRepository
from infra.qsettings_store import QtPreferenceStore
from ui.components import build_left_panel, build_mini_toolbar, build_right_panel
from ui.state import UiStateController

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

    def __init__(
        self,
        timeline: Optional[TimelineService] = None,
        repository: Optional[TimelineRepository] = None,
        preference_store: Optional[PreferenceStore] = None,
        speech_port: Optional[SpeechPort] = None,
        time_source: Optional[TimeSourcePort] = None,
    ):
        super().__init__()
        self.setWindowTitle("时间轴播报器（PvZ 战术计时）")
        self.resize(1000, 620)

        # ---- 运行时状态 ----
        self.timeline = timeline or TimelineService(global_lead_ms=2000)
        self.repository: TimelineRepository = repository or FileTimelineRepository()
        self.prefs: PreferenceStore = preference_store or QtPreferenceStore()
        self.model: Optional[TimelineModel] = None
        self._last_tick: float = 0.0

        # 100ms 刷新时钟与播报判定
        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self._on_tick)

        # 语音线程/端口
        self._owns_speech = speech_port is None
        self.tts: SpeechPort = speech_port or TTSWorker(self)
        if self._owns_speech and isinstance(self.tts, TTSWorker):
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

        left_widgets = build_left_panel(self)
        self.left_panel = left_widgets.widget
        self.clock_lbl = left_widgets.clock_label
        self.flow_list = left_widgets.flow_list
        self.start_btn = left_widgets.start_btn
        self.pause_btn = left_widgets.pause_btn
        self.reset_btn = left_widgets.reset_btn
        self.top_chk = left_widgets.top_checkbox
        self.auto_chk = left_widgets.auto_checkbox
        self.roi_edit = left_widgets.roi_edit
        self.roi_btn = left_widgets.roi_button
        self.ocr_seen_lbl = left_widgets.ocr_label
        self.lead_spin = left_widgets.lead_spin
        self.on_time_chk = left_widgets.on_time_checkbox
        self.early_chk = left_widgets.early_checkbox
        self.status_lbl = left_widgets.status_label
        self.splitter.addWidget(self.left_panel)

        self.lead_spin.setValue(self.timeline.global_lead_ms / 1000.0)
        self.lead_spin.valueChanged.connect(self._on_lead_changed)

        try:
            self.start_btn.clicked.connect(lambda: QtCore.QTimer.singleShot(0, self._sync_ocr_agent_enabled))
            self.pause_btn.clicked.connect(lambda: QtCore.QTimer.singleShot(0, self._sync_ocr_agent_enabled))
            self.reset_btn.clicked.connect(lambda: QtCore.QTimer.singleShot(0, self._sync_ocr_agent_enabled))
            self.reset_btn.clicked.connect(lambda: self.ocr_seen_lbl.setText("-"))
        except Exception:
            pass

        mini_widgets = build_mini_toolbar(self)
        self.mini_toolbar = mini_widgets.widget
        self.mini_countdown_lbl = mini_widgets.countdown_label
        self.mini_restore_btn = mini_widgets.restore_button
        self.mini_close_btn = mini_widgets.close_button
        self.mini_size_grip = mini_widgets.size_grip
        self.mini_restore_btn.clicked.connect(lambda: self.act_mini.setChecked(False))
        self.mini_close_btn.clicked.connect(self.close)

        right_widgets = build_right_panel(self, self.mini_toolbar)
        self.right_panel = right_widgets.widget
        self.table = right_widgets.table
        self.splitter.addWidget(self.right_panel)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self._last_splitter_sizes: Optional[List[int]] = None

        self.ui_state = UiStateController(
            timeline=self.timeline,
            status_label=self.status_lbl,
            clock_label=self.clock_lbl,
            countdown_label=self.mini_countdown_lbl,
        )

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
        self.ocr_agent: Optional[TimeSourcePort] = None
        try:
            self._init_ocr_agent(time_source)
        except Exception:
            self.ocr_agent = None

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

        self.timeline.set_flows(flows)
        self.flow_list.clear()
        for name in flows.keys():
            self.flow_list.addItem(name)

        if not flows:
            self.ui_state.set_status("未在文件中找到有效时间轴")
            return

        # 自动选择第一个流程
        first_item = self.flow_list.item(0)
        if first_item:
            self.flow_list.setCurrentItem(first_item)
            self._set_active_flow(first_item.text())

        self.ui_state.set_status(f"已加载：{path.name}（{len(flows)} 个流程）")

    # ---------- 切换流程/双击开始 ----------
    def _set_active_flow(self, name: str):
        """根据流程名切换当前事件表，并自动重置计时。"""
        events = self.timeline.set_current_flow(name)
        self.model = TimelineModel(events, parent=self)
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
        self.reset()  # 加载新流程后，自动重置为 0:00

    def on_flow_double_clicked(self, item: QtWidgets.QListWidgetItem):
        self._set_active_flow(item.text())
        self.start()  # 双击即开跑（符合“点流程立即开始”的习惯）

    # ---------- 控制区：开始/暂停/重置 ----------
    def _on_lead_changed(self, val: float):
        """全局提前播报秒数变化（单位：秒 → 保存为毫秒）。"""
        self.timeline.set_global_lead(int(val * 1000))

    def _toggle_run(self):
        """空格：开始 ↔ 暂停。"""
        if self.timeline.running:
            self.pause()
        else:
            self.start()

    def start(self):
        """开始计时。若尚未加载流程，提示用户。"""
        if not self.model:
            QtWidgets.QMessageBox.information(self, "提示", "请先加载一个时间轴流程。")
            return
        try:
            self.timeline.start()
        except RuntimeError as exc:
            QtWidgets.QMessageBox.information(self, "提示", str(exc))
            return
        self.timer.start()
        self.ui_state.set_status(f"运行中：{self.timeline.current_flow_name or '--'}")
        self._last_tick = time.perf_counter()
        self.ocr_locked = False
        self._sync_ocr_agent_enabled()

    def pause(self):
        """暂停计时。"""
        if not self.timeline.running:
            return
        self.timeline.pause()
        self.timer.stop()
        self.ui_state.set_status("已暂停")
        self._last_tick = 0.0
        self.ocr_locked = False
        self._sync_ocr_agent_enabled()

    def reset(self):
        """重置计时并清空播报队列。"""
        self.timeline.reset()
        self.timer.stop()
        self._last_tick = 0.0
        self.ocr_locked = False
        try:
            if hasattr(self, 'tts') and self.tts:
                self.tts.clear_queue()
        except Exception:
            pass
        self._update_clock()
        self.ui_state.set_status("已重置")
        self._sync_ocr_agent_enabled()

    # ---------- 计时心跳 ----------
    def _on_tick(self):
        """每 100ms 调用：推进时间、更新显示、处理播报。"""
        if not self.timeline.running or not self.model:
            return
        if self._handle_auto_mode():
            return
        now = time.perf_counter()
        if not hasattr(self, '_last_tick') or not self._last_tick:
            self._last_tick = now
            return
        delta_ms = max(0, int((now - self._last_tick) * 1000))
        self._last_tick = now
        decision = self.timeline.advance(delta_ms)
        self._update_clock()
        self._handle_decision(decision)

    def _handle_auto_mode(self) -> bool:
        """Auto OCR mode hijacks ticks; return True when manual advance should skip."""
        try:
            auto_enabled = hasattr(self, 'auto_chk') and self.auto_chk.isChecked()
        except Exception:
            auto_enabled = False
        if not auto_enabled:
            return False
        ocr_agent = getattr(self, 'ocr_agent', None)
        ocr_enabled = bool(ocr_agent and ocr_agent.is_enabled())
        ocr_locked = bool(getattr(self, 'ocr_locked', False))
        if (not ocr_enabled) or (not ocr_locked):
            try:
                self.clock_lbl.setText("没检测到")
            except Exception:
                pass
            self._last_tick = time.perf_counter()
            return True
        self._update_clock()
        self._last_tick = time.perf_counter()
        return True

    def _handle_decision(self, decision):
        if not decision:
            return
        self._speak(decision.event.action)

    def _update_clock(self):
        """刷新大时钟，并滚动表格定位到“下一条未播事件”。"""
        self.ui_state.update_clock(self.model, self.table, self.act_mini.isChecked())

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
    def _init_ocr_agent(self, time_source: Optional[TimeSourcePort]):
        self.ocr_agent: TimeSourcePort = time_source or OcrTimerAgent(
            self,
            interval_ms=200,
            scale=3,
            score_thresh=0.55,
        )
        # 初始未锁定识别
        self.ocr_locked = False

        # Restore settings
        try:
            roi_str = self.prefs.get_str("ocr/roi", "")
        except Exception:
            roi_str = ""
        if roi_str:
            if self.ocr_agent.set_roi_from_string(roi_str):
                self.roi_edit.setText(roi_str)
        try:
            auto_on = self.prefs.get_bool("ocr/auto", False)
        except Exception:
            auto_on = False
        self.auto_chk.setChecked(auto_on)

        # Restore broadcast options
        try:
            on_time_on = self.prefs.get_bool("opt/on_time", True)
        except Exception:
            on_time_on = True
        try:
            early_on = self.prefs.get_bool("opt/early", False)
        except Exception:
            early_on = False
        try:
            self.on_time_chk.setChecked(on_time_on)
            self.early_chk.setChecked(early_on)
        except Exception:
            pass
        self.timeline.on_time_enabled = bool(on_time_on)
        self.timeline.early_enabled = bool(early_on)

        # Wire signals
        self.roi_btn.clicked.connect(lambda: self.ocr_agent.select_roi(self))
        self.roi_edit.editingFinished.connect(self._on_roi_edit_changed)
        self.auto_chk.toggled.connect(self._on_auto_chk_toggled)
        self.ocr_agent.roiSelected.connect(self._on_roi_selected)
        self.ocr_agent.timeDetected.connect(self._on_ocr_time_detected)
        # Save broadcast options
        try:
            self.on_time_chk.toggled.connect(lambda v: self._on_broadcast_option_toggled("on_time", v))
            self.early_chk.toggled.connect(lambda v: self._on_broadcast_option_toggled("early", v))
        except Exception:
            pass

        # Initial enable sync
        self._sync_ocr_agent_enabled()

    def _on_roi_edit_changed(self):
        if not getattr(self, 'ocr_agent', None):
            return
        text = self.roi_edit.text().strip()
        ok = self.ocr_agent.set_roi_from_string(text)
        if ok:
            self.prefs.set_str("ocr/roi", text)
            # ROI 变化后需重新锁定
            self.ocr_locked = False
        self._sync_ocr_agent_enabled()

    def _on_roi_selected(self, x: int, y: int, w: int, h: int):
        if not getattr(self, 'ocr_agent', None):
            return
        s = f"{x},{y},{w},{h}"
        self.roi_edit.setText(s)
        self.prefs.set_str("ocr/roi", s)
        # ROI 变化后需重新锁定
        self.ocr_locked = False
        self._sync_ocr_agent_enabled()

    def _on_auto_chk_toggled(self, enabled: bool):
        self.prefs.set_bool("ocr/auto", bool(enabled))
        # 切换自动计时后重新锁定
        self.ocr_locked = False
        self._sync_ocr_agent_enabled()

    def _on_broadcast_option_toggled(self, option: str, value: bool):
        enabled = bool(value)
        if option == "on_time":
            self.timeline.on_time_enabled = enabled
            self.prefs.set_bool("opt/on_time", enabled)
        else:
            self.timeline.early_enabled = enabled
            self.prefs.set_bool("opt/early", enabled)

    def _sync_ocr_agent_enabled(self):
        # Enabled when: user checked + currently running + ROI valid
        if not getattr(self, 'ocr_agent', None):
            return
        want = False
        try:
            roi = self.ocr_agent.get_roi()  # type: ignore[union-attr]
            want = bool(
                self.auto_chk.isChecked()
                and self.timeline.running
                and roi is not None
                and roi.is_valid()
            )
        except Exception:
            want = False
        try:
            self.ocr_agent.set_enabled(want)  # type: ignore[union-attr]
        except Exception:
            pass

    def _on_ocr_time_detected(self, time_text: str, ms: int):
        if not getattr(self, 'ocr_agent', None):
            return
        # Update label always
        try:
            self.ocr_seen_lbl.setText(time_text)
        except Exception:
            pass
        # Only drive announcements when running
        if not self.timeline.running:
            return
        # 锁定：后续 tick 由 OCR 驱动
        # 首次锁定：对齐 prev_ms，避免锚定瞬间触发提前播报
        if not getattr(self, 'ocr_locked', False):
            self.ocr_locked = True
            self.timeline.prime_elapsed(ms)
            self._update_clock()
            self._last_tick = time.perf_counter()
            return
        self.ocr_locked = True
        decision = self.timeline.sync_elapsed(ms)
        self._update_clock()
        self._handle_decision(decision)
        self._last_tick = time.perf_counter()

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
    timeline = TimelineService(global_lead_ms=2000)
    repository = FileTimelineRepository()
    prefs = QtPreferenceStore()
    win = MainWindow(
        timeline=timeline,
        repository=repository,
        preference_store=prefs,
    )
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

