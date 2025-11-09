# MainWindow 重构计划

## 计划摘要
- 按“控件 → 控制器 → 入口”三层推进，先剥离 UI 构建，再抽象控制逻辑，最后整理启动流程。

## 阶段划分
1. **UI 组件拆分**
   - 新增 `ui/bindings.py` 负责快捷键/菜单/控件信号。
   - `main.py` 仅调用 `build_left_panel/build_right_panel/build_mini_toolbar` + `bind_shortcuts`。
2. **控制器层**
   - 创建 `controllers/timeline_controller.py`、`controllers/ocr_controller.py`，迁移 `_on_tick`、`_handle_auto_mode`、`_on_ocr_time_detected`、文件导入/导出等。
   - 引入 `actions.py`（open/export/reset 等命令）。
3. **入口/Bootstrap**
   - 新增 `app/bootstrap.py` 封装依赖注入，`main.py` 仅保留类定义；`python -m app.bootstrap` 为默认入口。

## 依赖与前置
- 依赖 Stage 4 的 CI/test/脚本已就绪。
- `TimelineService`/ports 不需修改。

## 风险控制
- 每阶段完成后运行 `python -m unittest tests.test_timeline_service tests.test_file_repository` 与 `scripts/manual_regression_stage0.py`。
- 文档 (`docs/重构任务日志.md`) 记录每个阶段时间戳。
