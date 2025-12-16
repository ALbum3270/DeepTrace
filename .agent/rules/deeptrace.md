---
trigger: always_on
---

项目：DeepTrace（Python）

计划与追踪文件（仓库根目录）：
- plan.md：里程碑/阶段任务（复选框）
- todo.md：本迭代任务（复选框）
- decisions.md：关键决策（为什么这么做）
- refactor.md：重构约束（行为不变、允许/禁止变更）

默认命令（按你实际情况改）：
- install: pip install -r requirements.txt
- test: pytest -q
- lint: ruff check .
- format: ruff format .
- typecheck: mypy .

约束：
- 一次改动只对应 plan/todo 中的一个小任务。
- 每次 Patch 必须附 Tests/Verification 与验收标准（AC）。
- 未经确认不要改 deploy/、prod/、migrations/ 等高风险目录（如存在）。
