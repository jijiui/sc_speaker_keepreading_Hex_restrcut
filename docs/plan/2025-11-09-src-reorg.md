# src/ 重构计划

## 背景
- 当前所有 Python 文件散落在仓库根目录，`pv_z_时间轴播报器（python_py_qt_6_）.py`、`core/`、`infra/`、`ui/`、`scripts/manual_regression_stage0.py` 等混杂，层次混乱。
- Stage 1–3 重构后已经有清晰的核心/适配器，但缺少标准的 `src/` 结构，导致运行入口和 import 都不直观。

## 目标
- 建立 `src/` 作为唯一代码根目录。
- 将主程序和适配器拆分到 `src/app/`、`src/infra/`、`src/ui/` 等标准包中。
- 根目录只保留 `docs/`、`scripts/`、`requirements.txt`、`agent.md` 等元信息。

## 目录映射与 rationale
| 现有路径 | 目标路径 | Rationale |
| --- | --- | --- |
| `pv_z_时间轴播报器（python_py_qt_6_）.py` | `src/app/main.py` | 主程序和入口脚本应放在 `src/app/`，统一命名后便于 `python -m app.main` 启动。
| `opencv_timer_agent.py` | `src/infra/ocr/qt_ocr_agent.py` | OCR 适配器属于基础设施层，放到 infra/ocr 子包，命名更语义化。
| `opencv_timer_core.py` | `src/infra/ocr/opencv_core.py` | OCR 内部工具与 `opencv_timer_agent` 同属 infra 层，保持同级。
| `core/` | `src/core/` | 领域模型/服务包移入 `src/`，与其他代码并列。
| `infra/` | `src/infra/` | 仓储/偏好/端口实现应放在 `src/infra`。
| `ui/` | `src/ui/` | 组件与状态控制属于 UI 适配层，放在新的 `src/ui`。
| `scripts/manual_regression_stage0.py` | 保持在 `scripts/` | 作为运行脚本，继续留在顶层；文档记录其使用方式即可。
| `scripts/smoke_timeline.py` | 保持在 `scripts/` | 烟雾测试脚本同上。
| `docs/` | 不动 | 文档本就应在根目录。

## 后续步骤
1. 创建 `src/` 并迁移 core/infra/ui/main 相关文件，更新 `__init__.py` 注释。
2. 调整 import 路径（例如 `from core...` → `from app.core...` 或配置 `PYTHONPATH=src`）。
3. 更新 `manual_regression_stage0.py`、`scripts/smoke_timeline.py` 等脚本的导入。
4. 重新运行 `python scripts/manual_regression_stage0.py` 和 `python -m unittest tests.test_timeline_service`。
5. 更新 `docs/重构任务日志.md`，记录迁移时间戳。
