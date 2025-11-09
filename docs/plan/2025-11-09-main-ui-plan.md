# 2025-11-09 Main UI Refactor Plan

## Overview
Guided by `2025-11-09-main-ui-instruction.md`,本计划分三阶段推进：UI 组件拆分 → 控制器 & 命令 → 入口治理。每个阶段列出 rationale、核心活动、预期结果与验证方式。

## Stage A – UI Components & Bindings
- **Rationale**：MainWindow 目前同时负责控件创建与信号绑定，难以复用。先将这些职责迁至 `ui/components.py`、`ui/bindings.py`，为后续控制器化打基础。
- **Activities**：
  1. 提炼左/右/迷你面板 builder，返回结构体（参考 Stage 3 的 `LeftPanelWidgets` 等）。
  2. 新建 `ui/bindings.py`，封装快捷键、菜单、按钮事件与 QoL 同步（置顶/自动 OCR 等）。
  3. MainWindow 仅调用 builder + bindings，并通过 `UiStateController` 更新状态。
- **Expected Outcome**：`src/app/main.py` 控件相关代码减少 >50%，所有控件与快捷键集中在 `ui/*` 模块。UC-01/UC-06（文件加载/导出）通过冒烟验证。
- **Testing**：运行 `python -m unittest tests.test_timeline_service tests.test_file_repository`，`python scripts/manual_regression_stage0.py`（至少关注 UC-01/06）以及 `python scripts/smoke_timeline.py --tick 2000 --lead 3000 --early`。

## Stage B – Controllers & Actions
- **Rationale**：计时/OCR/命令逻辑依旧耦合在 MainWindow，需要抽象成可测试控制器和命令层，便于复用与维护。
- **Activities**：
  1. 新建 `controllers/timeline_controller.py`，迁移 `_on_tick`、`_handle_auto_mode`、队列播报触发等逻辑。
  2. 新建 `controllers/ocr_controller.py`，负责 agent 初始化、ROI/自动模式锁定、触发 timeline sync。
  3. 新建 `actions.py`（或命令模块），封装 open/export/mini 模式等行为，供 bindings 调用。
  4. 为控制器添加针对性单测（例如模拟 timeline service、repository）。
- **Expected Outcome**：MainWindow 只注入控制器与 actions，不直接存储业务状态；`tests/test_file_repository.py` 之外再新增控制器层测试。UC-01~UC-07 全量冒烟通过。
- **Testing**：`python -m unittest tests.test_timeline_service tests.test_file_repository` + 新控制器测试模块；`python scripts/manual_regression_stage0.py`（完整 UC）+ `python scripts/smoke_timeline.py --tick ...`。

## Stage C – Bootstrap & Documentation
- **Rationale**：目前 `main.py` 仍承担 DI 和 `app.exec()`，需要一个专门入口便于打包和脚本调用，同时同步 README/脚本/CI。
- **Activities**：
  1. 新建 `app/bootstrap.py`（或 `app/__main__.py`），构建 service/ports/controller/bindings，再启动 MainWindow。
  2. 更新 `scripts/run_app.ps1`、README 以及 CI（如需）改用 `python -m app.bootstrap`。
  3. 清理旧入口/多余代码，更新 `docs/重构任务日志.md`。
- **Expected Outcome**：`python -m app.bootstrap` 成为唯一入口，README/脚本/CI 使用该命令；Stage 0 冒烟 + CI workflow 全绿；文档记录完成时间戳。
- **Testing**：终态执行 `python -m unittest ...`、`python scripts/manual_regression_stage0.py`、`python scripts/smoke_timeline.py --tick ...` 以及 `python -m app.bootstrap` 手动验证。
