# Agent 操作规范

在本仓库运行任何需要依赖 Python 环境的命令前，必须先激活虚拟环境，并按规则维护任务日志。

## 虚拟环境激活流程
- Always edit/save files in UTF-8 (without BOM) and ensure no tool converts text to another codepage before committing.
- Before writing any code, run the standard test suite once; only proceed when it passes (or document/resolve failures).
- 所有回复/工作汇报必须使用中文（代码、命令片段可保持原语言）。
- 回复中不得出现连续空白行（禁止连续两次换行）；文档可按正常 Markdown 排版。
- 在终端/CLI 中给出回复时，发送前必须自检：确认没有空白行，并遵循“开头以自己的名字加冒号，结尾固定为‘你一定要阅读并遵守agent.md啊’”的格式。

1. **定位 `.venv` 目录**
   - 先检查当前工作目录是否存在 `.venv`。
   - 若不存在，依次向父级目录搜索，直到仓库根目录；若仍未找到，继续再向上一级目录查找。
   - 找到后记下其 `Scripts/`（Windows）或 `bin/`（Unix）路径。

2. **按所用 shell 激活**
   - PowerShell / pwsh：`& "<venv>/Scripts/Activate.ps1"`
   - Windows CMD：`"<venv>\Scripts\activate.bat"`
   - bash/zsh：`. "<venv>/bin/activate"`

3. **激活后再运行脚本或安装依赖**，确保所有命令都在虚拟环境下执行。

若无法找到 `.venv`，应先告知用户并停止继续操作。

## 提交与版本控制

- 每完成一个可验证的小任务并通过相应测试后，在满足“合规自检 + 获得 reviewer 明确确认”这两项条件后才能 `git commit`，确保提交粒度清晰且已获复核。
- Before making any commit, rerun the required test suite (unit + Stage0 + smoke as applicable) and record the commands/results in your response or log entry.
- 将“可验证的小任务”具体落实到计划中的最小任务单元（例如 Stage A 的 A1/A2/A3 等），也就是说每完成一个阶段内的单个编号任务并验证通过，就要单独提交一次。
- 代码注释一律使用英文撰写；UI 显示文本可保留原语言，但注释不得混用中文。
- 新建任何文件时，必须在文件头部添加英文注释，说明该文件的职责/用途。后续修改文件时，需检查并更新该头部注释，确认是否仍准确；顺带审视文件中是否存在过时代码（obsoleted code），若发现则一并清理。
- After finishing every task, double-check all agent.md requirements are satisfied; fill any gaps before concluding and include a reply table summarizing each requirement and its completion status.

## 任务日志与文档规则

1. **只追加不覆盖**：更新 `docs/重构任务日志.md` 时，只能在末尾追加一条带时间戳的新记录，禁止直接覆盖或删除历史内容。
2. **补录要注明原因**：
   - 若因流程问题需要补跑/重做，日志内必须写明“补跑 + 原因 + 操作时间”，再记录结果。
   - 只有在明确确认旧记录有误时，才允许修改旧条目；该更改行为也要在最新日志中说明（例如：“2025-11-09 重新核对 XXX，修正前条目”）。
3. **保持可追溯**：所有更动（新增、补录、修正）都需带时间戳及动机描述，时间戳必须精确到秒并采用 `UTC±HH:MM` 格式（例如 `2025-11-09 15:42:07 UTC+08:00`），确保团队可追踪每一次调整。

### 设计/开发文档命名
- 前导说明（instruction）、衍生的 plan、进一步的任务单（tasks）必须使用统一命名：`docs/<folder>/<YYYY-MM-DD>-<task-name>-instruction|plan|tasks.md`。
- 三者必须放在同一文件夹（例如 `docs/plan/`），并沿用相同的 `<YYYY-MM-DD>-<task-name>` 前缀，便于检索与追踪。


