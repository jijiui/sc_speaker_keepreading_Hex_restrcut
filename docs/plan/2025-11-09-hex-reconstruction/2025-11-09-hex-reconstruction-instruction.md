# 六边形重构前导说明

## 1. 文档说明
- **目的**：记录 PvZ 时间轴播报器桌面客户端（`pv_z_时间轴播报器（python_py_qt_6_）.py`）在 commit `c290155431168fc54b160b38641fa0a30b783db4` 时的实现现状，为后续 Hexagonal Architecture 重构提供基线。
- **适用范围**：PyQt6 桌面端代码及直接依赖（`opencv_timer_agent.py` 等）。
- **读者对象**：重构参与的开发、架构、领域专家。
- **基线日期**：2025-11-09。
- **变更记录**
  | 版本 | 日期 | 作者 | 摘要 |
  | --- | --- | --- | --- |
  | v1.0 | 2025-11-09 | （当前） | 首次创建，基于 commit `c2901554…`. |

## 2. 系统现状概览
### 2.1 系统上下文
- **用户**：在桌面端通过 GUI 操作导入流程、控制计时、收听播报、切换迷你模式。
- **PyQt UI**：`MainWindow` 负责所有控制与呈现（`pv_z_时间轴播报器（python_py_qt_6_）.py:487-1448`）。
- **文件系统**：读取 CSV/TXT/Excel（`open_file` → `_read_csv_like` / `_events_from_dataframe`，`pv_z_时间轴播报器（python_py_qt_6_）.py:783-907`），并可导出示例 CSV（`pv_z_时间轴播报器（python_py_qt_6_）.py:1401-1422`）。
- **OCR Agent**：`OcrTimerAgent`（`opencv_timer_agent.py`）负责 ROI 选择与时间识别，通过信号与 UI 同步（`pv_z_时间轴播报器（python_py_qt_6_）.py:1313-1400`）。
- **TTS 子系统**：`TTSWorker` 线程借助 pyttsx3 或 Windows SAPI 播报文本，失败时降级为蜂鸣（`pv_z_时间轴播报器（python_py_qt_6_）.py:327-505`）。
- **设置存储**：`QSettings("sc_speaker", "pvz_timeline")` 保存 ROI、自动 OCR、播报勾选状态等用户偏好。

### 2.2 模块职责
| 模块 | 职责 | 输入 | 输出 | 依赖 |
| --- | --- | --- | --- | --- |
| `MainWindow` | 构建 UI、管理状态、调度文件加载/计时/OCR/TTS、更新界面 | 用户交互、OCR 信号、文件内容 | GUI 更新、TTS 指令、状态标签 | PyQt6、TTSWorker、OcrTimerAgent |
| `TimelineModel` | 将 `TimelineEvent` 列表绑定到 `QTableView`，控制列显示 | `List[TimelineEvent]` | Qt 模型数据 | PyQt6 |
| `TimelineEvent` | 表示单条事件（时间、动作、人口、备注） | 文件解析结果 | 供 UI/TTS 使用 | dataclasses |
| `_read_csv_like` / `_events_from_dataframe` | 解析 CSV/TXT、Excel Sheet | 文件内容 | 排序后的 `TimelineEvent` 列表 | csv、pandas/openpyxl |
| `TTSWorker` | 异步播报队列 | `_speak` 调用 | 音频输出、蜂鸣 | pyttsx3、win32com |
| `OcrTimerAgent` | 选择 ROI、周期识别游戏计时 | ROI 设置、interval | `timeDetected` 信号 | OpenCV/PyAutoGUI（推测） |

### 2.3 关键依赖
- Python 3.9+, PyQt6。
- pyttsx3（可选；缺失时回退至控制台输出 + `QApplication.beep()`），win32com（Windows SAPI）。
- pandas + openpyxl（解析 Excel），缺失时仅支持 CSV/TXT。
- OCR 端依赖 OpenCV、图像采样等（详见 `opencv_timer_agent.py`）。

## 3. 运行场景与用例流程
### UC-01：加载 CSV/TXT
- **触发**：用户点击“打开时间轴文件”，选择 CSV/TXT（`pv_z_时间轴播报器（python_py_qt_6_）.py:783-807`）。
- **流程**：检测编码 → `csv.DictReader` → 解析 `time/action/population/note` → 生成 `TimelineEvent` → 更新 `flows` 与 `flow_list`。
- **异常**：缺少必需列时弹窗报错；无法识别编码时警告（`pv_z_时间轴播报器（python_py_qt_6_）.py:844-850`）。

### UC-02：加载 Excel 多流程
- **触发**：同上，但选择 .xlsx/.xls。
- **流程**：用 pandas 读取所有 Sheet，逐个转换为事件列表，流程名按 `文件名/Sheet` 命名（`pv_z_时间轴播报器（python_py_qt_6_）.py:819-907`）。
- **异常**：缺少 pandas/openpyxl 时提示安装；Sheet 缺列直接跳过。

### UC-03：开始 / 暂停 / 重置
- **流程**：按钮或快捷键触发 `start/pause/reset`（`pv_z_时间轴播报器（python_py_qt_6_）.py:952-1000`）。`start` 启动 QTimer、设置状态；`pause` 停止计时并保持 `elapsed_ms`；`reset` 清零时间并清空 TTS 队列。

### UC-04：OCR 自动对时
- **触发**：勾选“自动 OCR”并选择 ROI（`pv_z_时间轴播报器（python_py_qt_6_）.py:1313-1394`）。
- **流程**：`timeDetected` 信号带回文本和毫秒 → `_on_ocr_time_detected` 更新 `elapsed_ms`，触发 `_check_announcements_simple`。
- **异常**：OCR 未锁定则显示“没检测到”并暂停手动计时（`pv_z_时间轴播报器（python_py_qt_6_）.py:1052-1068`）。

### UC-05：语音播报
- **触发**：`_check_announcements_simple` 监控 `prev_ms → elapsed_ms` 跨界（`pv_z_时间轴播报器（python_py_qt_6_）.py:1049-1083`）。
- **流程**：满足提前或正点条件时调用 `_speak` → `TTSWorker` 队列 → pyttsx3/SAPI/蜂鸣。
- **注意**：每个 tick 仅播一条，提前与正点文本相同。

### UC-06：导出示例 CSV
- **触发**：菜单“导出示例 CSV”（`pv_z_时间轴播报器（python_py_qt_6_）.py:1401-1422`）。
- **流程**：写入内置示例内容到用户选择的路径。

### UC-07：迷你模式 / 置顶
- **触发**：菜单或快捷键（`pv_z_时间轴播报器（python_py_qt_6_）.py:1219-1295`）。
- **流程**：切换帧窗口、隐藏菜单/左面板、显示迷你工具条，保持倒计时。支持拖拽和置顶同步。

## 4. 领域模型与数据结构
### 4.1 词汇表
| 术语 | 定义 | 代码引用 |
| --- | --- | --- |
| Flow | 单个 CSV/TXT 或 Excel Sheet 对应的一组事件 | `MainWindow.flows` (`pv_z_时间轴播报器（python_py_qt_6_）.py:492-545`) |
| TimelineEvent | 事件实体，包含时间、动作、人口、备注 | `pv_z_时间轴播报器（python_py_qt_6_）.py:212-231` |
| Global Lead | 全局提前播报毫秒值（唯一提前设置） | `pv_z_时间轴播报器（python_py_qt_6_）.py:505-507` |
| OCR ROI | 游戏计时区域的屏幕坐标，供自动对时使用 | `pv_z_时间轴播报器（python_py_qt_6_）.py:1313-1383` |
| 迷你模式 | 仅显示倒计时与控制按钮的无框窗口 | `pv_z_时间轴播报器（python_py_qt_6_）.py:1219-1295` |

### 4.2 数据结构
| 名称 | 字段 | 来源 / 用途 |
| --- | --- | --- |
| `TimelineEvent` | `time_ms`, `action`, `population`, `note` | CSV/TXT/Excel 解析；供 UI、播报使用 |
| `flows: Dict[str, List[TimelineEvent]]` | key=流程名 | 文件加载后生成，驱动 `flow_list` 与 `TimelineModel` |
| `settings (QSettings)` | `ocr/roi`, `ocr/auto`, `opt/on_time`, `opt/early` | OCR 与播报偏好持久化 |
| `TTSWorker` 队列 | `queue.Queue[str]` | `_speak` 提交的文本，线程串行播报 |
| `global_lead_ms` | int（默认 2000 ms） | 全局提前量 UI 控件与播报逻辑共享 |

### 4.3 业务规则
- QTimer 以 100 ms tick 推进 `elapsed_ms`；若启用 OCR 且未锁定，则不自增并在 UI 显示“没检测到”（`pv_z_时间轴播报器（python_py_qt_6_）.py:500-1082`）。
- 提前播报仅使用 `global_lead_ms`，CSV/Excel 中的 `lead` 列即使存在也被忽略（`pv_z_时间轴播报器（python_py_qt_6_）.py:505-507` + `pv_z_时间轴播报器（python_py_qt_6_）.py:801-907`）。
- `_check_announcements_simple` 在一个 tick 内最多播一条，先检查正点，再检查提前（`pv_z_时间轴播报器（python_py_qt_6_）.py:1049-1083`）。
- TTSWorker 若 pyttsx3/SAPI 均不可用，则打印并蜂鸣，避免阻塞 UI（`pv_z_时间轴播报器（python_py_qt_6_）.py:327-505`）。

## 5. 技术现状：端口 / 适配器
- **UI 适配器**：`MainWindow` 直接处理所有业务逻辑（文件 IO、计时策略、状态切换），尚未与领域服务解耦。
- **输入端口**：文件解析、OCR 信号都以具体实现存在，没有抽象接口；UI 亲自管理 `OcrTimerAgent` 生命周期与设置。
- **输出端口**：TTS 与设置持久化也在 UI 层直接调度；`TTSWorker` 作为具体适配器缺乏抽象 `SpeechPort`。
- **线程/同步**：`TTSWorker` 作为 `QThread`，仅通过队列与 UI 交互；OCR 信号在 Qt 事件循环内处理。

## 6. 重构展望与 Gap 分析
### 6.1 目标 Hex 结构（设想）
- **领域核心**：事件时间轴、计时推进、播报策略。
- **应用服务**：加载流程、管理计时状态、处理 OCR 输入、推送播报。
- **端口**：
  - 输入端：UI 控制、OCR 时间源、文件仓储。
  - 输出端：语音播报、偏好存储、文件导出。

### 6.2 差距
| 问题 | 现状 | 影响 |
| --- | --- | --- |
| 领域逻辑集中在 UI | `_on_tick`、`_check_announcements_simple` 等全部在 `MainWindow` | 难以测试/替换 |
| IO 与展示耦合 | 文件解析、CSV 导出、QSettings 都在 UI | 不利于 CLI/服务化 |
| 外部依赖难替换 | UI 直接依赖 `OcrTimerAgent`、`TTSWorker` 实现细节 | 无法 mock 或多实现 |
| 状态杂糅 | `MainWindow` 同时承担控制与数据存储 | 可维护性差 |

### 6.3 建议路线
1. 抽象应用服务层（如 `TimelineService`）封装计时推进、播报逻辑。
2. 定义仓储接口，将 CSV/TXT/Excel 解析、设置持久化移出 UI。
3. 拆出 `SpeechPort`、`OcrPort`，以依赖注入方式实现 TTS/OCR。
4. 之后再重构 UI，使其仅处理输入与呈现。
5. 为新层提供单元测试，尤其是提前/正点播报规则。

## 7. 附录
- **参考文件**：`pv_z_时间轴播报器（python_py_qt_6_）.py`、`opencv_timer_agent.py`、`六边形重构前导说明文档生成指南.md`。
- **术语表**：TTS=Text-To-Speech；OCR=Optical Character Recognition；ROI=Region of Interest。
- **开放问题**：
  - OCR 实现依赖的外部库能否在 Hex 架构中模块化？
  - 迷你模式是否需要独立适配器或可选功能？
  - 将来是否会重新启用 per-event 提前量？若是，需要怎样的数据结构与端口支持？
