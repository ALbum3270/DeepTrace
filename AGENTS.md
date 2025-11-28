# AGENTS.md

## 项目简介
DeepTrace 是一个基于 LangGraph 的事件链侦探系统，旨在通过按需检索和多轮推理，还原事件的起因、经过和结果。

## 环境设置

**重要**: 本项目使用 `Album` conda 环境。

1.  **激活环境**:
    ```bash
    conda activate Album
    ```

2.  **安装依赖** (如果尚未安装):
    ```bash
    pip install -r requirements.txt
    ```

## 运行项目

本项目目前提供命令行接口 (CLI)。

**运行示例**:
```bash
python -m src.interface.cli --query "请梳理最近一个月小红书上关于 XXX 的翻车事件"
```

## 代码结构

*   `src/core`: 核心数据模型 (Evidence, EventNode) 和业务逻辑。
*   `src/fetchers`: 数据获取适配器 (Mock, News, XHS)。
*   `src/agents`: LangGraph 节点逻辑 (EventExtractor, CommentTriage 等)。
*   `src/graph`: StateGraph 定义和编排。
*   `src/interface`: CLI 入口。

## 开发规范

*   使用 `pytest` 运行测试。
*   遵循 Python 3.11+ 类型提示。
