# MainWindow 重构先导说明

## 背景
- `src/app/main.py` 仍承担 UI 构建、信号绑定、控制逻辑、OCR/TTS 协调等多重职责，文件超过 1k 行，维护成本高。
- Stage 1–4 已完成领域/端口拆分与 src 布局，但 GUI 壳层尚未模块化，不利于后续扩展（例如添加 CLI 或新的 UI 框架）。

## 问题痛点
1. **UI 组件与控制逻辑耦合**：`_build_ui` 同时负责控件创建与业务信号，难以复用或测试。
2. **控制流程分散**：计时、OCR、菜单、快捷键等逻辑散落在 MainWindow 方法中，难以定位。
3. **状态同步重复**：除了 `UiStateController`，仍有零散的 status/倒计时更新代码。
4. **启动/依赖组装混在主模块**：`main()` 既构造依赖又启动窗口，缺少可复用的 bootstrap 层。

## 目标
- 将“控件构建”“信号绑定”“业务动作”拆分成独立模块，使 MainWindow 只负责调度。
- 构建可测试的控制器（TimelineController、OcrController 等），支撑未来 CLI/自动化。
- 规范入口：将 DI/启动逻辑移到 `app/bootstrap.py` 或同级模块，以便封装发布。

## 范围
1. UI 层：MainWindow、组件 builder、快捷键/菜单绑定。
2. 控制器层：计时 tick、OCR 回调、命令执行、文件对话框动作。
3. 入口层：`main()`、脚本/PowerShell 启动器。

## 风险与缓解
- **风险**：大规模移动代码易引入回归。缓解：保持 `TimelineService`/ports API 不变，编写/扩充单测、继续依赖 Stage0 冒烟。
- **风险**：Qt 信号连接散落。缓解：集中在 `ui/bindings.py`，统一引用。

## 成功标准
- `src/app/main.py` 主要负责 wiring（<400 行）；控件建造、动作、控制逻辑分别在独立模块。
- 新增控制器/动作模块具备英文模块注释，可单独测试。
- `python -m app.main`、`scripts/manual_regression_stage0.py`、CI workflow 全部通过。

## 时间线（预估）
1. Day 1：拆分 UI builder / bindings。
2. Day 2：实现 TimelineController + OcrController，迁移 `_on_tick` 等逻辑。
3. Day 3：编写/更新单测与文档，切换入口至 bootstrap。
