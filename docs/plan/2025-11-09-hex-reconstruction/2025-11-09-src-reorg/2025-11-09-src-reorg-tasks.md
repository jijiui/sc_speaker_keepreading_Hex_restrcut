# src/重构执行指南

## 背景
- 仓库根目录混杂主程序、领域层、适配层与工具脚本，难以在后续打包/发布时直接引用。
- Stage 1–3 已经将领域与适配器拆分清晰，但缺少标准 `src/` 目录结构。
- 未来需要打包成软件（例如 `python -m app.bootstrap` 或生成可执行文件），因此必须统一入口与导入路径。

## 目标
1. 所有可执行/可导入代码都集中到 `src/`，形成可复用的包结构：`src/app`、`src/core`、`src/infra`、`src/ui`、`src/infra/ocr` 等。
2. 根目录仅保留文档、脚本、依赖说明，便于打包配置。
3. 确保迁移后所有脚本、测试、GUI 入口都能无缝运行。

## 详细步骤
1. **创建目录与移动文件**
   - 新建 `src/`。
   - 将 `core/` → `src/core/`，`infra/` → `src/infra/`，`ui/` → `src/ui/`。
   - 将 `pv_z_时间轴播报器（python_py_qt_6_）.py` 重命名并移动到 `src/app/main.py`（保持中文 UI 文本，代码注释用英文）。
   - 将 `opencv_timer_agent.py` → `src/infra/ocr/qt_ocr_agent.py`，`opencv_timer_core.py` → `src/infra/ocr/opencv_core.py`。
   - 每个移动后的文件在头部补充/更新英文注释，若原有注释失效则修正；清理过时代码。

2. **更新导入路径**
   - 在新 `src/` 包中使用绝对导入：例如 `from core.services import TimelineService` 改为 `from app.core.services import TimelineService`（依据最终包名），或配置 `sys.path`/`PYTHONPATH` 指向 `src`。
   - 主程序 (`src/app/main.py`) 负责构建 TimelineService、Repository、PreferenceStore、TTS、OCR 端口等。
   - `scripts/manual_regression_stage0.py`、`scripts/smoke_timeline.py` 等入口脚本引用新的模块路径。

3. **同步测试与脚本**
   - 重新运行：
     - `python -m unittest tests.test_timeline_service`
     - `python scripts/manual_regression_stage0.py`
     - `python scripts/smoke_timeline.py --tick 2000 --lead 3000 --early`
   - 所有命令需在 `.venv` 中执行并记录通过情况。

4. **文档与日志**
   - 在 `docs/重构任务日志.md` 中追加 `src/` 重构时间戳（精确到秒，使用 `UTC±HH:MM`）。
   - 若迁移过程中有新的 rationale 或依赖调整，更新 `docs/plan/2025-11-09-src-reorg.md` 或追加补充文档。

## 任务单
| 序号 | 任务 | 负责人 | 状态 |
| --- | --- | --- | --- |
| 1 | 建立 `src/` 并迁移 `core/`、`infra/`、`ui/`、主程序、OCR 相关文件 | _TODO_ | ☐ |
| 2 | 更新所有导入路径，统一用 `app.<module>` 形式（通过 `PYTHONPATH=src` 或等价配置暴露包根） | _TODO_ | ☐ |
| 3 | 调整 `scripts/manual_regression_stage0.py`、`scripts/smoke_timeline.py`、测试文件的导入 | _TODO_ | ☐ |
| 4 | `.venv` 中重跑单元测试与冒烟脚本，记录结果 | _TODO_ | ☐ |
| 5 | 更新 `docs/重构任务日志.md`，记录 `src/` 迁移完成的 UTC 时间戳 | _TODO_ | ☐ |
