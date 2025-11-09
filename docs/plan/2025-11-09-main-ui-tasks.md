# MainWindow 重构任务单（2025-11-09）

## UI 组件拆分
1. [ ] 新建 `src/app/ui/bindings.py`，集中快捷键、菜单、信号连接；`main.py` 仅调用绑定函数。
2. [ ] 将 `_build_ui` 中控件创建和信号注册迁移到 `ui/components.py`/`ui/bindings.py`，确保英文化注释。

## 控制器层
3. [ ] 新建 `src/app/controllers/timeline_controller.py`，承载 `_on_tick`、`_handle_auto_mode` 等逻辑；MainWindow 内改为委托。
4. [ ] 新建 `src/app/controllers/ocr_controller.py`，负责 OCR agent 初始化、ROI 处理、时间推送。
5. [ ] 新建 `src/app/actions.py`（或等价模块），封装“打开文件”“导出示例”“置顶切换”等命令，供菜单/快捷键调用。

## 入口/Bootstrap
6. [ ] 创建 `src/app/bootstrap.py`（或 `__main__.py`），从此处构建 TimelineService/Repository/PreferenceStore/SpeechPort/OCR，`python -m app.bootstrap` 为默认入口。
7. [ ] `scripts/run_app.ps1` & README 更新为 `python -m app.bootstrap`。

## 验证
8. [ ] 运行 `python -m unittest tests.test_timeline_service tests.test_file_repository`。
9. [ ] 运行 `python scripts/manual_regression_stage0.py` 与 `python scripts/smoke_timeline.py --tick 2000 --lead 3000 --early`。
10. [ ] 更新 `docs/重构任务日志.md`，记录每阶段完成的 UTC 时间戳。
