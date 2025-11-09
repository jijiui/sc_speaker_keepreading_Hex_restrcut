# 重构计划

> 依据《六边形重构前导说明》与最新代码状态（commit `c290155431168fc54b160b38641fa0a30b783db4`），制定从现有 PyQt6 单体应用演进到 Hexagonal Architecture 的详细步骤。计划分阶段推进，每阶段包含准备、实施与验证动作。

---

## 阶段 0：准备与基线
1. **建立基线分支**  
   - 从当前 `option/opencv` 分支切出 `feature/hex-prep`，锁定 commit `c2901554…`。  
   - 将《六边形重构前导说明.md》和本计划置于 `docs/` 并提交，确保信息可追溯。
2. **收集依赖信息**  
   - `pip freeze > requirements.txt`（若已有文件则更新），特别注明可选依赖（pyttsx3、pandas、openpyxl、win32com、OpenCV 等）。  
   - 记录运行环境（Python 版本、OS、Qt 版本）。
3. **快速回归用例**  
   - 手动走查前导说明列出的 7 个用例，记录结果与潜在缺陷，作为后续 refactor 的回归脚本依据。
4. **新增最小测试脚本**（可选）  
   - 若时间允许，编写 CLI 脚本加载样例 CSV 并模拟 `_check_announcements_simple`，用于后续验证域逻辑。

## 阶段 1：抽取领域与应用服务
目标：将核心逻辑从 UI 中抽离，形成可测试的领域层。

1. **定义领域模型模块**  
   - 新建 `core/domain.py`（或类似路径），迁移 `TimelineEvent`、时间格式化函数、`parse_time_to_ms` 等纯函数。  
   - 保持 API 与现有调用兼容（UI 导入域模块）。
2. **设计应用服务接口**  
   - 创建 `core/services/timeline_service.py`，定义类 `TimelineService`，负责：  
     - 管理 `flows` 数据  
     - 当前流程选择  
     - 计时推进（传入 delta_ms 或 OCR ms）  
     - 播报触发决策（返回应播报的动作列表）  
   - 将 `_check_announcements_simple` 逻辑迁移至服务层，确保依赖注入 `global_lead_ms`、开关状态。
3. **补充单元测试**  
   - 引入 `pytest` 或标准库 `unittest`，针对 `TimelineService` 编写测试：  
     - 纯正点触发  
     - 提前触发  
     - OCR 对齐  
     - “一次 tick 仅一条”约束  
   - 使用样例数据，确保逻辑与旧行为一致。
4. **UI 接入服务**  
   - `MainWindow` 不再维护 `flows`、`elapsed_ms` 等原始数据，而是持有 `TimelineService` 实例，所有状态访问都通过服务接口完成。  
   - `_on_tick`、`_on_ocr_time_detected` 调整为向服务发送事件（delta_ms / absolute_ms），再依据返回值更新 UI。

## 阶段 2：抽象端口与适配器
目标：为外部依赖（文件 IO、OCR、TTS、设置存储）定义端口接口，实现松耦合。

1. **文件仓储接口**  
   - 定义 `TimelineRepository`（例如 `core/ports/timeline_repository.py`），提供 `load(path) -> Dict[str, List[TimelineEvent]]`。  
   - 现有 `_read_csv_like` / `_events_from_dataframe` 移动到 `infra/file_repository.py` 作为具体适配器。
2. **偏好存储接口**  
   - 定义 `PreferenceStore`，封装读取/写入 `opt/on_time` 等；默认实现使用 `QSettings`，未来可替换为 JSON/DB。  
   - UI 通过服务层访问偏好，而不直接操作 `QSettings`。
3. **语音端口**  
   - 定义 `SpeechPort`，暴露 `speak(text)`、`clear_queue()`、`stop()`。  
   - `TTSWorker` 实现该接口，未来可再添加 CLI 版（如日志记录）。
4. **OCR 端口**  
   - 定义 `TimeSourcePort`，提供 `start()`, `stop()`, `select_roi()`, `set_roi()` 及 `time_detected` 事件回调。  
   - 现有 `OcrTimerAgent` 实现该端口，UI 仅通过接口与之交互。
5. **适配器注册**  
   - 建立简单的依赖注入（DI）容器或工厂（可先手写），`MainWindow` 在初始化时注入服务和端口实例。  
   - 确保没有模块再直接 import 具体实现。

## 阶段 3：UI 精简与组件划分
目标：让 PyQt UI 成为纯粹的输入/输出适配器，逻辑留给服务层。

1. **拆分 UI 组件**  
   - 将左侧控制区、右侧表格封装成独立 QWidget/Presenter，`MainWindow` 负责组装。  
   - 将迷你模式逻辑封装到 `MiniWindowController`，减少主类复杂度。
2. **事件绑定重写**  
   - 所有按钮/复选框直接调用服务接口或触发命令对象，而非操作内部状态。  
   - 对 OCR/TTS 状态变更使用观察者/信号，确保 UI 更新与业务解耦。
3. **错误与状态处理**  
   - 统一使用一个状态管理器，将“运行中/暂停/未加载”等状态暴露给 UI；UI 通过绑定或信号更新标签。

## 阶段 4：测试与工具链
目标：确保重构后系统可验证、可持续集成。

1. **自动化测试覆盖**  
   - 在 `tests/` 目录添加：  
     - 域服务测试（UC 场景）  
     - 仓储解析测试（基于样例文件）  
     - 偏好存储 mock 测试  
   - 如可能，添加一个 Qt-less 的 Presenter 测试，验证 UI 与服务交互。
2. **CI 配置**  
   - 配置 GitHub Actions 或其他 CI 工具，执行 `pytest`/`flake8`（或 `ruff`）、`mypy`（若启用）。  
   - 在 CI 中缓存依赖，提高速度。
3. **打包/运行脚本**  
   - 提供 `make run` / `python -m app` 等命令，将 DI 初始化与 Qt 启动封装，便于未来替换 UI。

## 阶段 5：功能验证与回归
1. **回归用例**  
   - 重跑阶段 0 的 7 个用例，确保行为一致（尤其是提前/正点播报、OCR 对齐、迷你模式）。  
   - 记录测试结果，附在 PR 或 release note。
2. **性能与稳定性**  
   - 检查 TTS 队列、OCR 信号在新架构下是否存在延迟或阻塞；根据结果调整线程/事件处理。
3. **清理遗留**  
   - 删除不再使用的模块（例如旧的 `_check_announcements_simple` 实现），确保仓库整洁。

## 阶段 6：后续迭代（可选）
- **CLI / 服务端适配器**：基于 Hex 核心添加 CLI 或 Web 服务，用于自动播报或录制。  
- **per-event 提前量**：若重新启用 `lead` 列，可在领域层扩展 `TimelineEvent` 并调整服务逻辑，不影响 UI。  
- **替换 OCR/TTS 实现**：利用端口机制，探索新的 OCR 模型或云端 TTS。

---

## 里程碑与交付
| 里程碑 | 目标 | 交付物 |
| --- | --- | --- |
| M0 | 基线与回归脚本 | `docs/指南 + 计划`、requirements、手动回归记录 |
| M1 | 领域服务抽离 | `core/domain.py`、`timeline_service`、单元测试 |
| M2 | 端口/适配器重构 | 仓储/偏好/语音/OCR 接口与实现、DI 初始化 |
| M3 | UI 精简 | 重构后的 `MainWindow`、组件划分文档 |
| M4 | 测试/CI | `tests/`、CI pipeline、运行脚本 |
| M5 | 完整回归 | 测试报告、发布说明 |

完成以上步骤后，项目将具备清晰的领域层、独立的端口/适配器、可复用的服务与测试体系，满足 Hexagonal Architecture 的核心要求。随后可在不影响核心的情况下拓展新的 UI 或外部集成。
