# 重构任务单

> 基于《重构计划.md》，将六边形重构拆解为可执行任务。各任务默认指向 `feature/hex-prep` 分支，并按阶段排序。可在 issue/项目管理工具中逐项跟踪。

---

## 阶段 0：准备与基线
| # | 任务 | 关键输出 |
| --- | --- | --- |
| 0.1 | 创建 `feature/hex-prep` 分支，提交《前导说明》《重构计划》到 `docs/` | 新分支、提交记录 |
| 0.2 | 生成/更新 `requirements.txt`，记录依赖版本（注明可选项） | `requirements.txt` |
| 0.3 | 手动回归 7 个关键用例并记录结果 | 回归笔记/截图 |
| 0.4 | （可选）编写 CLI 脚本模拟 `_check_announcements_simple` 以便后续测试 | `scripts/smoke_timeline.py` |

## 阶段 1：领域与应用服务
| # | 任务 | 关键输出 |
| --- | --- | --- |
| 1.1 | 新建 `core/domain.py`，迁移 `TimelineEvent`、时间解析/格式化函数 | 域模块 |
| 1.2 | 设计 `TimelineService`（管理 flows、计时推进、播报判定） | `core/services/timeline_service.py` |
| 1.3 | 引入测试框架（pytest/unittest），为 `TimelineService` 编写 UC 测试 | `tests/test_timeline_service.py` |
| 1.4 | 重构 `MainWindow`，将 flows/elapsed 等状态替换为服务调用 | 更新 UI 逻辑 |

## 阶段 2：端口与适配器
| # | 任务 | 关键输出 |
| --- | --- | --- |
| 2.1 | 定义 `TimelineRepository` 接口；将 CSV/Excel 解析迁移到 `infra/file_repository.py` | 仓储接口+实现 |
| 2.2 | 封装 `PreferenceStore` 接口，抽离 `QSettings` 读写 | 偏好存储接口 |
| 2.3 | 定义 `SpeechPort`，让 `TTSWorker` 实现该接口 | 语音端口 |
| 2.4 | 定义 `TimeSourcePort`（OCR），封装 `OcrTimerAgent` | OCR 端口 |
| 2.5 | 实现简单 DI/工厂，在 `main` 中注入各端口 | 初始化逻辑 |

## 阶段 3：UI 精简
| # | 任务 | 关键输出 |
| --- | --- | --- |
| 3.1 | 拆分左侧控制区、右侧表格、迷你工具条为独立组件/控制器 | 子组件类 |
| 3.2 | 重写事件绑定：UI 仅调用服务/端口，不直接操作内部状态 | 精简信号槽 |
| 3.3 | 构建统一状态管理器（运行状态、倒计时、错误提示）供 UI 订阅 | 状态模型 |

## 阶段 4：测试与工具链
| # | 任务 | 关键输出 |
| --- | --- | --- |
| 4.1 | 为仓储、偏好、端口适配器编写单元测试（含样例文件） | `tests/test_infra_*` |
| 4.2 | 配置 CI（GitHub Actions 或等价）运行 lint + tests | `.github/workflows/ci.yml` |
| 4.3 | 提供统一入口脚本（如 `python -m app` 或 `make run`） | 运行脚本/README 更新 |

## 阶段 5：功能验证
| # | 任务 | 关键输出 |
| --- | --- | --- |
| 5.1 | 重跑 7 个用例，记录结果，与阶段 0 对比 | 回归报告 |
| 5.2 | 监测 TTS/OCR 性能与稳定性，必要时调整线程/事件处理 | 性能记录 |
| 5.3 | 清理废弃代码与文档（旧逻辑、未用模块） | 最终提交 |

## 阶段 6：后续迭代（可选）
| # | 任务 | 关键输出 |
| --- | --- | --- |
| 6.1 | 实现 CLI 或 Web 入口，复用 Hex 核心服务 | 新适配器 |
| 6.2 | 评估重新启用 per-event 提前量的需求，扩展领域模型 | 需求方案 |
| 6.3 | 探索替换 OCR/TTS 实现（云服务、其他模型），通过端口接入 | 新实现 PoC |

---

> 建议将每项任务关联 issue，明确负责人与预期完成时间。在阶段交付前进行代码评审与测试验证，确保逐步达成 Hexagonal 架构的目标。
