# 2025-11-09 Main UI Refactor Instruction

## 1. Document Info
| Item | Value |
| --- | --- |
| Scope | MainWindow / GUI shell refactor |
| Author | Project team (jijiui) |
| Date | 2025-11-09 |
| Related docs | `2025-11-09-main-ui-plan.md`, `2025-11-09-main-ui-tasks.md` |

## 2. Background
- `src/app/main.py` 仍承担 **控件构造 + 信号绑定 + 控制逻辑 + 依赖注入** 等全部职责，文件 >1000 行。
- Stage 1–4 已实现领域/端口分层、CI 流程和 src 布局，但 GUI 层尚未模块化，不利于扩展其它 UI 或自动化。
- 未来需要可复用的 GUI 适配器和清晰入口，以支撑可执行发行版。

## 3. Goals
1. MainWindow 仅负责 wiring（Qt 容器 + 控制器注入，≈<400 行）。
2. UI 构造、快捷键/菜单绑定、业务动作分别位于专用模块（components、bindings、actions）。
3. 计时/OCR/文件命令由控制器层（TimelineController、OcrController）封装，可单元测试。
4. 入口 `app/bootstrap.py` 负责依赖注入，`python -m app.bootstrap` 成为统一运行方式。
5. Stage 0 冒烟脚本与 CI 工作流继续通过。

## 4. Non-goals
- 不改动 `TimelineService` 或领域层 API。
- 不调整 UI 文案/布局（除必要的拆分）。
- 不引入新的 UI 框架（仍为 PyQt6）。

## 5. Scope & Components
| Layer | 当前 | 拟引入 |
| --- | --- | --- |
| UI Builder | `build_left_panel` 等函数散落在 `main.py` | `ui/components.py`、`ui/bindings.py` 模块 |
| 控制器 | 内联 `_on_tick`、`_on_ocr_time_detected` 等方法 | `controllers/timeline_controller.py`、`controllers/ocr_controller.py` |
| 命令 | `open_file/export_sample` 直接写在 MainWindow | `actions.py` 封装命令，供菜单与快捷键调用 |
| 入口 | `main.py` 同时负责类定义 + DI + `app.exec()` | `bootstrap.py` 负责 DI/启动；`main.py` 仅暴露类 |

## 6. Use Cases Impacted
- UC-01/02（文件加载）：改由 `TimelineController` + `FileRepository` 命令执行。
- UC-03（计时控制）：tick 逻辑转交控制器。
- UC-04（OCR 自动计时）：`OcrController` 管理锁定/ROI。
- UC-05/06/07：通过 actions/bindings 触发，行为保持不变。

## 7. Constraints & Dependencies
- 继续在 `.venv` + `PYTHONPATH=src` 环境下开发。
- 新模块需遵循英文注释规则（见 `agent.md`）。
- 现有单测（Timeline + Repository）必须保持通过。

## 8. Risks & Mitigation
| Risk | Impact | Mitigation |
| --- | --- | --- |
| 控制逻辑拆分引入回归 | 计时/OCR 失效 | 每阶段运行单测 + `scripts/manual_regression_stage0.py` |
| 信号绑定遗漏 | 快捷键失效 | `ui/bindings.py` 统一管理，编写检查清单 |
| 入口切换导致脚本失效 | 无法启动 | `scripts/run_app.ps1`、README 同步更新 |

## 9. Deliverables & Definition of Done
- `ui/bindings.py`、`controllers/*.py`、`actions.py`、`bootstrap.py` 新模块完成，头部注释齐全。
- `src/app/main.py` 主要包含类定义 + wiring（LOC 显著降低）。
- `scripts/run_app.ps1` / README 指向 `python -m app.bootstrap`。
- `docs/重构任务日志.md` 记录各阶段时间戳；Stage 0 冒烟 + CI 通过。

## 10. Milestones (aligned with plan)
| Stage | Description | Exit Criteria |
| --- | --- | --- |
| A | UI components & bindings 拆分 | MainWindow 使用新 builder/bindings；UC-01/06 冒烟通过 |
| B | 控制器 + actions | `_on_tick` 等迁入控制器，命令模块可测试；单测 + UC-01~07 通过 |
| C | Bootstrap/入口治理 +文档 | `app/bootstrap.py` 生效、脚本更新、CI/README 同步；Stage 0 冒烟 + CI 绿 |
