# 2025-11-09 Main UI Refactor Tasks

本任务单对应 `2025-11-09-main-ui-instruction.md` 与 `2025-11-09-main-ui-plan.md`，分阶段列出具体任务、动机与测试计划。

## Stage A – UI Components & Bindings
| # | Task | Rationale | Test Plan |
| --- | --- | --- | --- |
| A1 | 在 `src/app/ui/components.py` 中补充/重构 builder，确保左/右/迷你面板返回结构体，移除 `main.py` 中的控件创建代码 | 统一控件构造，降低 MainWindow 体积 | 运行 `python -m unittest tests.test_timeline_service tests.test_file_repository`；执行 UC-01/UC-06 冒烟（`python scripts/manual_regression_stage0.py`，至少到 UC-06） |
| A2 | 新建 `src/app/ui/bindings.py`，集中快捷键、菜单、按钮与 OCR enable 等信号绑定；MainWindow 通过函数注入 | 避免信号分散，方便审计 | 同 A1；额外手动验证快捷键（Space/R/O/T）在现行入口 `python -m app.bootstrap` 下仍生效 |
| A3 | 复用 `UiStateController` 更新状态文本/倒计时，删除 `main.py` 中重复逻辑 | 防止状态更新散落 | `python scripts/manual_regression_stage0.py` 至少覆盖 UC-03/UC-07 |

**Stage A 验证**：  
- `python -m unittest tests.test_timeline_service tests.test_file_repository`  
- `python scripts/manual_regression_stage0.py`（允许跳过 UC-04 之前的提示但需确认 UC-01/06/07）  
- `python scripts/smoke_timeline.py --tick 2000 --lead 3000 --early`

## Stage B – Controllers & Actions
| # | Task | Rationale | Test Plan |
| --- | --- | --- | --- |
| B1 | 新建 `src/app/controllers/timeline_controller.py`（含 tick/auto-mode/TTS 调用），`main.py` 仅保留引用 | 将计时逻辑与 UI 解耦，可单独测试 | 新增 `tests/test_timeline_controller.py`（模拟 TimelineService/TTS）；运行 `python -m unittest`（含新测试） |
| B2 | 新建 `src/app/controllers/ocr_controller.py`，封装 OCR agent 初始化、ROI 输入、时间同步 | OCR 行为集中，便于未来替换实现 | 添加针对 OCR controller 的轻量单测（可使用 fake agent）；运行 `python scripts/manual_regression_stage0.py` 全量 UC |
| B3 | 新建 `src/app/actions.py`，封装文件打开/导出/置顶/迷你等命令；绑定函数调用 actions 而非 MainWindow 方法 | 菜单/快捷键可复用同一命令，实现更清晰的审计点 | `python scripts/manual_regression_stage0.py`（全量 UC）+ 手动验证 `scripts/run_app.ps1` 中 open/export |

**Stage B 验证**：  
- `python -m unittest tests.test_timeline_service tests.test_file_repository tests.test_timeline_controller tests.test_ocr_controller`  
- `python scripts/manual_regression_stage0.py`（全量 UC）  
- `python scripts/smoke_timeline.py --tick 2000 --lead 3000 --early`  
- 记录任何 TTS/OCR 性能变化

## Stage C – Bootstrap & Documentation
| # | Task | Rationale | Test Plan |
| --- | --- | --- | --- |
| C1 | 新建 `src/app/bootstrap.py`（或 `app/__main__.py`），在此创建 TimelineService/Repository/PreferenceStore/Controllers，再启动 MainWindow | 将 DI 与类定义分离，便于打包/脚本 | 在 `.venv` 中运行 `python -m app.bootstrap` 验证 |
| C2 | 更新 `scripts/run_app.ps1`、README、CI workflow 使用 `python -m app.bootstrap`；清理旧入口说明 | 防止误用旧命令 | 执行脚本 + CI workflow（手动 `Invoke-WebRequest` 非必要，确保 `scripts/run_app.ps1` 正常启动） |
| C3 | 更新 `docs/重构任务日志.md`，记录 Stage A/B/C 的 UTC 时间戳与测试结论 | 保持可追溯性 | 手动检查 markdown 是否合规，确保日志只追加 |

**Stage C 验证**：  
- `python -m unittest ...`（含新测试）  
- `python scripts/manual_regression_stage0.py`（全量）  
- `python scripts/smoke_timeline.py --tick 2000 --lead 3000 --early`  
- `python -m app.bootstrap` 手动运行 GUI  
- 确认 CI workflow 在下一次 push 中通过
