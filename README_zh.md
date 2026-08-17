# UniDeer - 2.0

[English](./README.md) | 中文 | [日本語](./README_ja.md) | [Français](./README_fr.md) | [Русский](./README_ru.md)

[![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)](./backend/pyproject.toml)
[![Node.js](https://img.shields.io/badge/Node.js-22%2B-339933?logo=node.js&logoColor=white)](./Makefile)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

UniDeer（**D**eep **E**xploration and **E**fficient **R**esearch **Flow**）是一个开源的 **super agent harness**，构建在 **LangGraph** 之上。它通过 **sub-agents**（子代理）、**长期记忆**和**沙箱执行**来编排复杂的多步骤任务——并由**可扩展的 skills**（技能）驱动。

UniDeer 是 **[DeerFlow](https://github.com/bytedance/deer-flow)（由 [ByteDance](https://www.bytedance.com/) 创建）** 的**社区 fork**（基于 v2.0+），并已发展为一个具有自身工程方向的项目。它继承了 deep-research 的血统和大部分原始架构；代码库、中间件流水线和运行时行为都已重新改造。参见[UniDeer 与 DeerFlow 的区别](#unideer-与-deerflow-的区别)和[致谢](#致谢)。

> **关于血统的说明：** DeerFlow 2.0 是一次彻底的从头重写，与 v1 没有任何共享代码。UniDeer 建立在这一 2.0 基础之上并继续演进。最初的 v1 deep-research 框架仍在上游的 [1.x 分支](https://github.com/bytedance/deer-flow/tree/main-1.x) 维护。

---

## 目录

- [为什么选择 UniDeer](#为什么选择-unideer)
  - [“聊天机器人加工具”的问题](#聊天机器人加工具的问题)
  - [设计原则](#设计原则)
- [致谢](#致谢)
- [UniDeer 与 DeerFlow 的区别](#unideer-与-deerflow-的区别)
- [架构概览](#架构概览)
  - [服务拓扑](#服务拓扑)
  - [harness 与 app 的依赖防火墙](#harness-与-app-的依赖防火墙)
  - [一次典型的请求，端到端](#一次典型的请求端到端)
- [核心特性](#核心特性)
  - [Skills 与工具](#skills-与工具)
  - [中间件流水线](#中间件流水线)
  - [子代理](#子代理)
  - [沙箱与文件系统](#沙箱与文件系统)
  - [上下文工程](#上下文工程)
  - [长期记忆](#长期记忆)
  - [MCP 与模型工厂](#mcp-与模型工厂)
  - [工具目录](#工具目录)
- [运行时与可靠性](#运行时与可靠性)
  - [运行所有权、租约与恢复](#运行所有权租约与恢复)
  - [检查点](#检查点)
  - [数据库级并发不变量](#数据库级并发不变量)
- [快速开始](#快速开始)
  - [前置要求](#前置要求)
  - [配置](#配置)
  - [运行应用](#运行应用)
  - [启动模式](#启动模式)
- [进阶](#进阶)
  - [沙箱提供方](#沙箱提供方)
  - [IM 渠道](#im-渠道)
  - [授权与 RBAC](#授权与-rbac)
  - [追踪与可观测性](#追踪与可观测性)
  - [定时任务](#定时任务)
  - [Provisioner（Kubernetes）](#provisionerkubernetes)
- [嵌入式 Python 客户端](#嵌入式-python-客户端)
- [终端工作台（TUI）](#终端工作台tui)
- [部署](#部署)
  - [本地开发](#本地开发)
  - [Docker](#docker)
  - [Kubernetes](#kubernetes)
- [安全](#安全)
- [文档](#文档)
- [贡献](#贡献)
- [许可证](#许可证)

---

## 为什么选择 UniDeer

大多数“AI 代理”工具只是接了一个搜索工具的聊天界面。UniDeer 是一个 **harness**：一个结构化的运行时，把随机的 LLM 生成转变为确定性的、由状态机管理的执行流水线。

一次请求会流经：

1. **主导代理（lead agent）** — 规划本轮，决定是否委派，并综合最终答案
2. **中间件链** — 由 35 个以上可组合的拦截器组成的流水线，在每次模型调用和工具执行前后强制执行技能、预算、安全和工具策略
3. **子代理** — 并行、隔离的工作单元，用于那些能从真实并行延迟、专业能力或上下文隔离中受益的任务
4. **沙箱** — 每个线程独立的文件系统（skills、workspace、uploads、outputs），并带有可插拔的执行隔离
5. **记忆** — 跨会话持久化的用户画像和事实，在相关时注入提示词
6. **流式输出** — SSE 事件，实时渲染到 Web UI、TUI 或 IM 渠道

核心理念只有一句话：**skills 负责教学，middlewares 负责执行。** 能力在 `SKILL.md` 文件中声明；不变量——写前先读、token 预算、工具策略、循环检测、安全终止——在代码中确定性地执行，无论模型决定做什么。

### “聊天机器人加工具”的问题

单纯的 LLM 加工具的聊天封装有三个结构性弱点，UniDeer 正是为此而设计：

- **没有强制力。** 模型可以无视指令。“先搜索再回答”的提示只是一个建议；而统计搜索次数并注入纠正的中间件则是一种保证。
- **没有隔离。** 每次工具调用都运行在与聊天相同的上下文中，因此冗长的研究任务会污染对话，子任务也无法安全地并行运行。
- **没有状态纪律。** 没有检查点、压缩和跨会话记忆，多轮任务会失去连贯性，多小时的任任务则会撑爆上下文窗口。

UniDeer 用状态机运行时、强制流水线和沙箱文件系统解决了这三个问题。

### 设计原则

- **确定性优于随机性。** 提示词负责引导；中间件负责执行。门控、计数和策略都从消息历史和线程状态推导，不依赖模型的临时决定。
- **渐进加载。** 技能只在需要时加载，保持上下文窗口精简。工具通过 `tool_search` 发现，仅在相关时提升。
- **默认隔离。** 子代理无法看到父代理的历史；沙箱路径按线程隔离；记忆按用户和代理隔离；运行有所有权和租约。
- **失败关闭。** 冲突的状态更新会抛错，工具授权在执行前过滤，检查点不变量在数据库层用部分唯一索引强制执行。
- **可运维。** 运行租约、孤儿恢复、请求追踪关联，以及可插拔的追踪（Langfuse、LangSmith、Monocle）都是一等公民，而不是事后补充。

## 致谢

UniDeer 的存在离不开前人的工作。

- **[ByteDance](https://www.bytedance.com/)** — 原始 DeerFlow 项目和 deep-research 框架的创造者，UniDeer 正是从其 fork 而来。本项目建立在他们开源的基础之上。
- **[DeerFlow](https://github.com/bytedance/deer-flow)** — 上游开源项目（MIT 许可），UniDeer 是其社区 fork。我们感谢其架构、skills 生态和工程成果。
- **DeerFlow v1 维护者与贡献者** — 最初的 Deep Research 框架（在 [1.x 分支](https://github.com/bytedance/deer-flow/tree/main-1.x) 维护）为 UniDeer 所基于的 2.0 重写奠定了基础。
- **DeerFlow 社区** — 塑造了上游项目的贡献者、测试者和用户。

UniDeer 自身的差异、优化和新增内容见[UniDeer 与 DeerFlow 的区别](#unideer-与-deerflow-的区别)。

## UniDeer 与 DeerFlow 的区别

UniDeer 保留了 super agent harness 的愿景，但在工程和产品方向上有所分歧。今天重要的区别：

| 领域 | DeerFlow（上游） | UniDeer（本项目） |
| --- | --- | --- |
| **仓库** | `bytedance/deer-flow` | 独立 fork，拥有自己的路线图和发布节奏 |
| **中间件流水线** | 基于宽泛关键词触发的技能门控，会在“形似但未激活”的对话中注入激活提示 | **未激活技能的快速退出**：技能门控（deep-research、system-design、startup-sketch 等）只在技能被显式斜杠激活或已载入 `skill_context` 时触发。闲聊查询直接通过——不污染提示词，降低首 token 延迟 |
| **回答后纠正** | Metacognition 等门控可能触发第二次完整 LLM 生成来“修正”回答 | **建议式纠正**：回答后的提示在下一个自然轮次生效，而不是强制立即重新生成，消除第二次 LLM 往返的延迟尖峰 |
| **子代理可观测性** | 折叠的子代理卡片只显示状态 | **实时运行时元数据**：折叠卡片显示生效的模型名和累计 token 用量，每次子代理 LLM 调用后更新，并在重载后保持 |
| **会话持久化** | 仅会话 cookie | **“保持登录”** 策略：统一的会话 cookie 生命周期、`remember_me` 处理，以及按部署形态（HTTPS、回环、公网 HTTP）的 Secure/Max-Age 策略 |
| **记忆后端** | 默认 DeerMem | 默认 DeerMem，**另加 OpenViking HTTP 后端**，支持远程、跨实例的记忆召回 |
| **授权** | 默认关闭 | **可插拔授权 + 内置 RBAC** 提供方，支持按角色的工具/路由允许-拒绝策略 |
| **追踪关联** | 基础 | X-Trace-ID 传播，外加 Langfuse/LangSmith/Monocle 追踪，带 `metadata.deerflow_trace_id` 关联 |
| **代码库** | — | harness 包（`backend/packages/harness/deerflow/`）在此维护，带有自己的测试、不变量（harness/app 导入防火墙）和文档 |

共享的 DNA 仍然存在：skills、子代理、沙箱、记忆、MCP 和 IM 渠道桥接。UniDeer 的关注点是**可预测的延迟**（不浪费 token、不意外重新生成）和**运维深度**（所有权、租约、数据库级并发、可观测性）。

## 架构概览

### 服务拓扑

一个标准部署运行四个协作服务，由一条命令或一个 Docker Compose 栈编排：

| 服务 | 端口 | 角色 |
| --- | --- | --- |
| **Nginx** | `2026` | 统一反向代理入口。将 `/api/langgraph/*` 路由到 Gateway 的内嵌 LangGraph 运行时，其余代理到 Frontend。 |
| **Gateway API** | `8001` | FastAPI REST API，外加内嵌的 LangGraph 运行时（`RunManager`、`run_agent()`、`StreamBridge`）。没有独立的 LangGraph 服务——运行时就在 Gateway 进程内部。 |
| **Frontend** | `3000` | Next.js 16 Web 界面（React 19、TypeScript、Tailwind CSS 4、pnpm）。 |
| **Provisioner** | `8002` | 可选——仅在沙箱配置为 provisioner/Kubernetes 模式时启动。负责沙箱 pod/VM 的生命周期管理。 |

```
                    Browser / IM Client (Feishu, Slack, Telegram, WeChat, WeCom, DingTalk, GitHub, Discord)
                                       |
                                       v
                            Nginx (port 2026)
                     /api/langgraph/*          /, /workspace/*, /blog/*
                     |                        |
                     v                        v
            Gateway API (FastAPI :8001)   Frontend (Next.js :3000)
            + embedded LangGraph runtime
                     |
        +------------+------------+-----------+
        |            |            |           |
        v            v            v           v
   Sandbox      IM Channels  Provisioner   Persistence
   (E2B/Aio/    (8 bridges)   (:8002, K8s)  (SQLAlchemy +
    Local)                                  Alembic)
```

### harness 与 app 的依赖防火墙

后端分为两层，并有一条由 CI 强制执行的硬性依赖规则：

- `app.*`（FastAPI 宿主：gateway 路由、渠道桥接、调度器）**可以**导入 `deerflow.*`
- `packages/harness/deerflow/`（harness 包，以 `deerflow.*` 导入）**绝不能**导入 `app.*`

这由 `backend/tests/test_harness_boundary.py` 强制执行，并在 CI 中运行。harness 保持可发布、与 app 无关、可独立测试。第二个不变量由 `make test-blocking-io` 强制：异步事件循环上零同步文件/数据库/网络 I/O——阻塞工作必须通过 `asyncio.to_thread` 卸载。

### 一次典型的请求，端到端

1. 用户在 Frontend 输入框中输入消息（可选语音转录或 AI 润色）。
2. `POST /api/threads/{id}/runs/stream` 开启一个 SSE 流式请求。
3. Gateway 验证认证（Better Auth cookie 会话、CSRF、RBAC），解析代理配置，创建 LangGraph 运行。
4. `RunManager.run_agent()` 从检查点加载 `ThreadState`，解析模型，构建中间件链。
5. 主导代理节点执行：记忆中间件注入用户上下文，技能激活在斜杠激活时加载 `SKILL.md`，组装系统提示词（目标、技能、工具、记忆），并以工具定义调用模型。
6. 如果模型调用工具，则路由到内置 / 沙箱 / 社区 / MCP 处理器，结果被净化，并运行循环检测。
7. 如果调用 `task` 工具，子代理执行器会以隔离上下文和受限工具集生成并行子代理；每个返回结构化的 `TaskResult`；主导代理综合结果。
8. 运行结束后：记忆提取保存新事实，生成标题（首轮），计算 workspace 变更，评估目标，生成建议。
9. `StreamBridge` 将内部事件转换为 SSE 事件（`values`、`messages-tuple`、`custom`、`tasks`），Frontend 实时渲染：动画 Markdown、带步骤时间线和 token 用量的子代理卡片、workspace 变更 diff、待办、目标状态和后续建议。

## 核心特性

### Skills 与工具

Skills 是结构化的能力模块——一个定义工作流、最佳实践和参考资源的 `SKILL.md` 文件。UniDeer 内置 30+ 技能，并允许你添加自己的技能、替换内置技能，或组合成复合工作流。

**技能如何工作：**

1. 每个技能位于 `skills/public/`（已提交）或 `skills/custom/`（gitignore）下的独立目录。
2. `SKILL.md` 文件是入口——技能激活时代理遵循的指令。
3. 技能**渐进加载**——只在任务需要时加载，保持上下文窗口精简。
4. 技能可以声明 `allowed-tools`，在激活时限制代理可用的工具（尽力而为的行为范围）。
5. **斜杠激活**：请求开头使用 `/skill-name` 可在本轮激活技能。
6. **SkillScan**：对已安装技能运行确定性安全检查器，标记高置信度问题（私钥、shell 执行模式）。

**激活门控。** 领域特定技能门控（deep-research、system-design、startup-sketch 等）只在技能于线程中显式激活时触发——通过 `/skill-name` 斜杠激活，或通过 `read_file` 加载捕获到 `skill_context`。仅包含技能相关词汇的闲聊查询（例如“为什么……”、“解释……”或“设计……”）直接通过：不注入隐藏的激活提示，因此闲聊轮次不会污染提示词或拖慢首 token 延迟。

**内置技能包括：**

- 研究与分析：`deep-research`、`github-deep-research`、`data-analysis`、`academic-paper-review`、`systematic-literature-review`、`consulting-analysis`
- 内容生成：`report-generation`、`ppt-generation`、`image-generation`、`video-generation`、`music-generation`、`podcast-generation`、`newsletter-generation`
- 工程：`frontend-design`、`web-design-guidelines`、`chart-visualization`、`code-documentation`、`system-design`、`bootstrap`
- 产品与需求：`business-requirement`、`product-requirements`、`software-requirements`、`startup-sketch`
- 元技能：`skill-creator`、`skill-reviewer`、`find-skills`、`surprise-me`、`vercel-deploy-claimable`、`claude-to-deerflow`

技能的 `allowed-tools` 策略只在技能被显式激活后生效。仅仅启用、宣传或在自定义代理或子代理 `skills` 允许列表中列出技能，并不会缩减代理的正常工具集。一旦激活，策略会同时过滤模型可见的工具 schema 和工具执行。这是尽力而为的行为范围，不是硬性安全边界。

### 中间件流水线

主导代理图（`make_lead_agent`）组装了一条由 35 个以上中间件阶段（源码树中 60+ 模块）组成的流水线，包裹每一次模型调用和工具执行。这是 harness 的主要扩展点。

按大致顺序选择的部分阶段：

| 中间件 | 用途 |
| --- | --- |
| `InputSanitization` | 中和原始输入中的恶意系统标签 |
| `ToolOutputBudget` | 限制过大的工具输出，防止上下文溢出 |
| `ToolResultSanitization` | 净化远程抓取的 HTML/网页结果 |
| `ThreadData` / `Uploads` | 挂载线程隔离范围并注入上传文件元数据 |
| `Sandbox` | 获取沙箱容器或本地上下文 |
| `DanglingToolCall` | 中断恢复后修补未完成的工具调用 |
| `LLMErrorHandling` | 将提供方错误规范化为可恢复的轮次 |
| `SandboxAudit` | AST 检查 bash 命令中的不安全模式 |
| `ReadBeforeWrite` | 文件写入前强制执行加密 SHA 哈希戳门控 |
| `ToolProgress` | 检测工具停滞的状态机（ACTIVE 到 WARNED 到 BLOCKED） |
| `SkillActivation` / `SkillToolPolicy` | 绑定 `SKILL.md` 上下文并执行 `allowed-tools` |
| `Metacognition` | 复杂提示词的先思考执行（回答前；回答后为建议式） |
| `Planner` | 多步骤变更的“没有计划，不做修改”规则 |
| `EmojiGate` | Unicode 扫描器，保证生成的代码/配置无 emoji |
| `Summarization` / `TokenBudget` | 高 token 水位时压缩上下文 |
| `TodoList` / `Title` | 计划模式的任务跟踪和首轮后自动标题 |
| `Memory` | 运行前注入长期记忆，运行后提取新事实 |
| `LoopDetection` | 硬性停止重复的相同工具调用循环 |
| `TerminalResponse` | 重试空白的助手响应；防止静默失败 |
| `Safety / ModelLengthFinishReason` | 处理提供方内容过滤器和最大 token 限制 |
| `Clarification`（最后） | 拦截 `ask_clarification` 并发出 `Command(goto=END)` |

同一链条（减去主导代理特有的阶段）也应用于子代理，因此委派任务受与父任务相同的不变量约束。

### 子代理

子代理是一种优化，而不是复杂请求的默认响应。

主导代理会即时生成子代理——每个都有自己的作用域上下文、工具和终止条件——当委派能带来真实的并行延迟、专业能力或上下文隔离的净收益时。它会让相互依赖的作用域和重叠副作用远离并行调度。子代理返回结构化结果；主导代理验证并综合。

**执行模型。** 子代理执行器是线程池 + asyncio 的混合体：上下文变量从父代理正确传播，每个子代理运行自己的隔离事件循环，生命周期状态遵循严格状态机：`PENDING` 到 `RUNNING` 到 `COMPLETED` / `FAILED` / `CANCELLED` / `TIMED_OUT`。护栏上限（`token_capped`、`turn_capped`、`loop_capped`）提前结束运行，同时保留部分输出，主导代理可以区分“完成”和“被封顶”。

**并发限制。** `SubagentLimitMiddleware` 限制并发委派（默认 3，可配置 1-4）和每次运行的委派总数（默认 6，最大 50）。

**结构化契约。** 子代理结果以固定契约承载在 `ToolMessage.additional_kwargs` 中：状态、停止原因、错误、完整结果的 SHA-256 摘要、生效模型名和累计 token 用量。枚举值通过 `contracts/subagent_status_contract.json` 在 Python 和 TypeScript 之间共享，契约测试将两者钉在一起，确保前后端永不漂移。

**实时运行时元数据。** 折叠的子代理卡片显示生效模型，并在提供方返回用量元数据时显示累计 token 总数，每次子代理 LLM 调用完成后更新，重载后保持。并发子代理以 `task_id` 为键保持独立总数。不提供用量的提供方显示明确的不可用状态，绝不显示伪造的零。

独立的只读研究可以在墙钟节省超过重复发现与综合成本时并发运行。共享文件且有顺序测试反馈的仓库重构则留在主导代理。当 `max_concurrent_subagents` 为 1 时，并行和多批路由指导被禁用；委派仅保留给有实质专业或上下文隔离收益的场景。

### 沙箱与文件系统

每个任务都有自己的执行环境，拥有完整的文件系统视图——skills、workspace、uploads、outputs。

```
/mnt/user-data/
├── uploads/          # your files
├── workspace/        # agents' working directory
└── outputs/          # final deliverables
```

**提供方：**

| 提供方 | 描述 |
| --- | --- |
| `E2BSandboxProvider` | 远程 E2B 沙箱，带 VM 隔离、预热池、突发，以及多 worker 部署的 Redis 所有权 |
| `AioSandboxProvider` | 基于容器的隔离（Docker） |
| `LocalSandboxProvider` | 宿主机文件系统，带每线程目录；默认禁用宿主机 bash |

**关键特性：**

- 每线程目录隔离，带路径安全策略和环境变量策略
- 文件操作锁，序列化同一路径上的并发读写
- **写前先读强制**：`read_file` 将文件当前内容的 SHA-256 哈希戳到消息上；对已存在文件的 `write_file` / `str_replace` 在磁盘哈希与戳不匹配时被确定性地阻止。任何写入都会使先前的读取失效，强制连续修改之间重新读取。
- **Workspace 变更跟踪**：每次运行后，记录 `workspace` 和 `outputs` 中变更文件的 diff 摘要，并在 UI 中以“files changed”徽章和文本 diff 显示。上传被排除（它们是用户输入）。
- 图像处理：base64 图像在视觉模型消费后从检查点移除，避免负载重复。
- 用内置 `grep` 工具搜索沙箱文件。

### 上下文工程

- **隔离的子代理上下文** — 子代理无法看到父代理或兄弟的历史
- **摘要** — 完成的子任务被压缩，中间结果卸载到文件系统，上下文被压缩以保持在 token 限制内
- **严格的工具调用恢复** — 悬空的工具调用在下次模型调用前用占位结果修补，防止严格的推理模型因畸形历史而失败
- **可见的工具运行完成** — 空的后工具最终响应重试一次，然后以可见错误呈现，而不是静默成功
- **手动压缩** — 编辑器中的 `/compact` 在保持完整聊天可见的同时总结旧上下文
- **会话目标** — `/goal <条件>` 附加线程作用域的完成条件；运行时在每次运行后对照目标评估对话，并注入隐藏的继续（安全上限 8 次），直到满足或清除

### 长期记忆

用户画像、偏好和积累知识的跨会话持久记忆。

**存储架构：**

```
{deerflow_home}/memory/
├── users/{user_id}/
│   ├── memory.json              # user profile + history summaries (JSON)
│   └── agents/{agent_name}/
│       └── facts/
│           ├── ab/cdef123...md  # individual fact (Markdown, sharded by SHA-256)
│           └── ...
```

- 事实是规范的 Markdown 文件，按 `SHA-256(fact_id)` 的前两个十六进制字符分片
- 日志式写入防止静默丢失更新；共享用户锁和乐观修订保护并发访问
- 检索默认使用作用域 SQLite FTS5/BM25 适配器，带本地子串回退；派生索引可重建，损坏索引自动重建
- 旧版 `memory.json` 事实在首次读取时自动迁移

**后端：**

- **DeerMem**（默认）— 文件后端、作用域感知，带提取写入门控，在存储前按作用域、持久性和权威性对每条候选事实分类。只存储持久的、描述性的用户级事实；当前线程约束和一次性权限留在对话状态中。
- **OpenViking**（可选）— 通过 HTTP 连接独立 OpenViking 服务器，支持远程、跨实例召回。有界提交水位和抖动重试防止重试时重复提交。

记忆注入按操作模式配置（`middleware` 与 `tool`），`memory.injection_enabled: false` 完全禁用该块。

### MCP 与模型工厂

UniDeer 支持 **Model Context Protocol**，通过 stdio 或 HTTP 连接外部工具服务器，带工具 schema 缓存、MCP 路由中间件和 MCP 来源工具的工具注解。

模型工厂与提供方无关：

- OpenAI 和 OpenAI 兼容 API（`langchain_openai:ChatOpenAI`）
- vLLM（自托管，支持思考/推理，通过 `chat_template_kwargs.enable_thinking`）
- OpenAI Codex CLI（`gpt-5.4` 类）和 Anthropic Claude（OAuth 或 API 密钥）
- 华为 MindIE，外加打补丁的提供方（DeepSeek、MiniMax、StepFun、MiMo）以支持推理

思考/推理支持（`supports_thinking`、`supports_reasoning_effort`）、视觉模型和 Responses API（`output_version: responses/v1`）都是一等公民。凭据通过凭据加载器从环境变量加载。

### 工具目录

**内置工具** — `task`（生成子代理）、`tool_search`（按描述发现工具）、`ask_clarification`（暂停等待用户输入）、`view_image`、`present_file`、`list_uploaded_files`、`review_skill_package`、`setup_agent` / `update_agent`、`invoke_acp_agent`。

**社区工具** — `web_search`、`web_fetch`、`web_capture`、`image_search`（提供方可配置）。

**沙箱工具** — `bash`、`ls`、`read_file`（支持行范围）、`write_file`、`str_replace`。

**浏览器工具**（可选附加）— `browser_navigate`、`browser_snapshot`、`browser_click`、`browser_type`、`browser_get_text`、`browser_back`、`browser_screenshot`、`browser_close`。由 Playwright 驱动，带 SSRF 筛查；默认禁用。

**授权。** 启用 `authorization.enabled` 后，可插拔的 `AuthorizationProvider` 在工具到达模型或延迟工具目录之前过滤被拒绝的工具，并在每次业务工具执行前再次检查。内置 RBAC 提供方支持按角色的 `tools` 和 `routes` 允许/拒绝策略。

## 运行时与可靠性

### 运行所有权、租约与恢复

每次运行都有所有权。运行管理器分配唯一 worker id（`hostname:hex_uuid`），为每次运行打上租约，并将所有权持久化到 runs 表。如果 Gateway 重启或 worker 在运行达到持久最终状态前变得不可达，该运行会以清晰的停止原因作为孤儿恢复：

- `"Gateway restarted before this run reached a durable final state."`
- `"Run lease expired - owning worker is unreachable."`

租约过期检测、启动孤儿恢复和多 worker 运行所有权在 SQLite（本地）和 Postgres（部署）上都受支持。状态最终化时的瞬态 SQLite 锁竞争以有界退避重试，驱动原生唯一约束信号（Postgres `23505`、SQLite 约束码）被检测，而不依赖随语言变化的错误文本。

### 检查点

线程状态在每一步后检查点化，因此运行可以恢复或分支。运行时为上游 LangGraph 检查点机制附带兼容性补丁（例如，修复 `InMemorySaver` 在 full-to-delta 迁移线程上丢失写入），钉在已验证的 LangGraph 版本上，如果上游修复则自动退出。检查点通道模式和快照频率可按部署配置。

### 数据库级并发不变量

并发由数据库管理，而不是内存标志。部分唯一索引强制关键不变量：

| 索引 | 不变量 |
| --- | --- |
| `uq_runs_thread_active` | 每线程最多一个 pending/running 运行（`WHERE status IN ('pending','running')`） |
| `uq_scheduled_task_run_active` | 每个定时任务最多一个活动运行（`WHERE status IN ('queued','running')`） |
| `uq_channel_connection_active_identity` | 外部 IM 身份的单活动所有者转移（`WHERE status != 'revoked'`） |

迁移包含去重预步骤，因此即使在已经违反不变量的数据库上（现场数据库、修复前的多 worker 部署）也能构建索引。竞争中的失败写入方以类型化冲突呈现（例如 `ActiveScheduledRunConflict`），与活动运行重叠的定时调度会记录终态 `skipped` 墓碑，永远不会占用活动槽位。

## 快速开始

### 前置要求

- Python 3.12+ 和 `uv`
- Node.js 22+ 和 pnpm 10
- `nginx`（`make dev` 统一本地端点所需）
- Docker（可选，用于容器化部署）

运行 `make check` 验证工具链。

### 配置

```bash
git clone https://github.com/bytedance/deer-flow.git
cd deer-flow
```

> 上面的克隆 URL 指向上游仓库。对于 UniDeer，请改为克隆你收到的 fork URL。

1. 安装依赖：`make install`（先后端后前端，按 target 实现）
2. 运行设置向导：

```bash
make setup
```

向导引导你选择 LLM 提供方、可选网页搜索，以及执行/安全偏好，如沙箱模式、bash 访问和文件写入工具。它生成一个最小化的 `config.yaml` 并将你的密钥写入 `.env`。大约需要 2 分钟。

随时运行 `make doctor` 验证设置并获得可操作的修复提示。如果你要针对本地设置或运行时问题提交 GitHub issue，运行 `make support-bundle`——它会写出脱敏的 issue 摘要、AI 辅助的 issue 草稿，以及 `.deer-flow/support-bundles/` 下的可选证据压缩包。

**配置文件：**

- `config.yaml`（gitignore）— 主应用配置：模型、沙箱、工具、渠道、调度器、日志、追踪
- `extensions_config.json`（gitignore）— MCP 服务器和技能定义
- `config.example.yaml` / `extensions_config.example.json` — 复制用模板

使用 `make config-upgrade` 将 `config.example.yaml` 中的新字段合并到现有 `config.yaml`，不丢失本地设置。

**模型**在 `config.yaml` 的 `models:` 下配置。每个条目指定提供方类、模型 id 和通过环境变量的凭据：

```yaml
models:
  - name: gpt-4o
    display_name: GPT-4o
    use: langchain_openai:ChatOpenAI
    model: gpt-4o
    api_key: $OPENAI_API_KEY
  - name: qwen3-32b-vllm
    display_name: Qwen3 32B (vLLM)
    use: deerflow.models.vllm_provider:VllmChatModel
    model: Qwen/Qwen3-32B
    api_key: $VLLM_API_KEY
    base_url: http://localhost:8000/v1
    supports_thinking: true
```

**环境变量**（路径和运行时状态）：

- `UNI_DEER_PROJECT_ROOT` — 显式项目根
- `UNI_DEER_CONFIG_PATH` — 指向特定配置文件
- `UNI_DEER_HOME` — 运行时状态位置（默认项目根下的 `.deer-flow`）
- `UNI_DEER_SKILLS_PATH` — 技能目录（默认项目根下的 `skills/`）

### 运行应用

**方案 1：Docker（推荐）**

```bash
make docker-start
```

从 `config.yaml` 进行模式感知启动，统一端点为 `http://localhost:2026`。其他 target：`make docker-stop`、`make docker-logs`、`make docker-logs-gateway`、`make docker-logs-frontend`、`make docker-logs-redis`。

**方案 2：本地开发**

```bash
make dev
```

启动三个带热重载的服务：

- Gateway API（FastAPI，端口 8001，带内嵌 LangGraph 运行时）
- Frontend（Next.js，端口 3000）
- Nginx（端口 2026 — 统一入口）

用 `make stop` 停止一切。日志位于 `logs/gateway.log`、`logs/frontend.log` 和 `logs/nginx.log`。在 Windows 上，请从 Git Bash 运行本地流程（原生 `cmd.exe`/PowerShell 不支持基于 bash 的服务脚本）。

**后端开发命令**（在 `backend/` 下）：

```bash
make dev                # FastAPI Gateway with reload (port 8001)
make test               # offline unit tests
make test-blocking-io   # strict blocking-IO runtime gate
make lint               # ruff check
make format             # ruff format
make migrate-rev MSG="" # autogenerate an Alembic migration
```

**前端开发命令**（在 `frontend/` 下）：

```bash
pnpm dev                # Next.js Turbopack dev server (port 3000)
pnpm lint               # ESLint
pnpm typecheck          # TypeScript check
pnpm test               # unit tests
pnpm test:e2e           # Playwright E2E tests
```

### 启动模式

`config.yaml` 支持模式感知启动：

| 模式 | 描述 |
| --- | --- |
| `flash` | 快速响应，最少推理 |
| `standard` | 速度与深度均衡 |
| `pro` | 带显式推理的计划模式 |
| `ultra` | 完整子代理编排 |

## 进阶

### 沙箱提供方

**E2B** 默认使用 `wait` 溢出策略：等待 `acquire_timeout`，然后使代理轮次失败（UniDeer 不自动重试；客户端可用结构化错误安排重试）。`burst` 加 `burst_limit` 允许有限额外 VM；`reject` 可在返回错误前移除一个预热 VM。使用 Redis 所有权时，`replicas` 是通过一个容量哈希在 worker 间共享的部署级硬限制；不匹配的 worker 失败关闭。

**Aio** 在隔离的 Docker 容器中运行 shell 执行，线程数据挂载从其后端检测（本地容器使用挂载的 gateway 目录；远程/provisioner 沙箱通过显式同步接收上传）。

**Local** 将文件工具映射到宿主机上的每线程目录，但默认禁用宿主机 `bash`，因为它不是安全隔离边界。只对完全可信的本地工作流重新启用。宿主机 bash 命令有墙钟超时。

### IM 渠道

UniDeer 桥接外部消息平台：**Feishu、Slack、Telegram、Discord、DingTalk、WeChat、WeCom 和 GitHub**。所有渠道共享同一条通过 Gateway 运行生命周期的执行路径：

- 每个渠道接收用户消息，转换为线程运行，并流式返回响应
- 会话管理（assistant id、递归限制、思考模式）按渠道可配置
- 消息总线、每渠道运行策略和连接身份关联统一了 8 个桥接
- **单活动所有者转移**：外部身份以 `(provider, external_account_id, workspace_id)` 为键；最新成功的绑定胜出，由 `uq_channel_connection_active_identity` 部分唯一索引无竞争地强制
- 入站重投递去重、文件附件暂存到沙箱，以及工件投递（仅 outputs——其他路径被拒绝以防止外泄）

### 授权与 RBAC

高级部署可以在 `config.yaml` 中启用 `authorization.enabled` 的可插拔授权。配置的 `AuthorizationProvider` 在工具到达模型或延迟工具目录之前过滤被拒绝的工具，然后在每次业务工具执行前再次检查同一提供方。Gateway `threads:*` 和 `runs:*` 路由权限来自同一提供方，而现有的所有者检查和仅管理员管理门控仍然有效。内置 RBAC 提供方支持按角色的 `tools` 和 `routes` 允许/拒绝策略，并验证 `default_role` 命名了已配置角色。默认关闭。

### 追踪与可观测性

- **请求追踪关联**：每个 Gateway HTTP 响应都包含 `X-Trace-Id`；日志包含 `trace_id`
- **Langfuse**：追踪包含匹配 `X-Trace-Id` 的 `metadata.deerflow_trace_id`；设置 `UNI_DEER_ENV`（或 `ENVIRONMENT`）按部署环境标记追踪
- **LangSmith 和 Monocle**：可插拔追踪提供方
- 追踪回调在图的调用根附加，因此 span 不会重复；代码库明确记录了这一不变量

### 定时任务

从 Web UI 或 Gateway API 配置循环代理运行。后台调度器按 cron 调度分发每个任务，并带：

- 数据库强制“每个任务最多一个活动运行”语义（`uq_scheduled_task_run_active`）
- 调度与活动运行重叠时的 `skipped` 墓碑（绝不占用活动槽位）
- 手动触发与轮询器竞争时收敛到与快速路径相同的结果（手动：409 冲突；调度：`skipped`）

### Provisioner（Kubernetes）

可选的 Provisioner 服务（端口 8002）管理 Kubernetes 部署的沙箱基础设施：按需分配沙箱 pod/VM，维护快速获取的预热池，并处理完整生命周期（创建、健康检查、销毁）。仅在沙箱配置为 provisioner/K8s 模式时启动；使用 E2B/Aio 提供方的本地和 Docker Compose 部署不需要它。

## 嵌入式 Python 客户端

以编程方式与 UniDeer 实例交互——无需 Web UI：

```python
from deerflow.client import DeerFlowClient

client = DeerFlowClient(base_url="http://localhost:8001")

# Stream a turn
for event in client.stream("thread-id", "your prompt"):
    print(event)

# Create a thread
thread = client.create_thread(agent="lead_agent")
```

客户端支持线程创建、消息流式（与 UI 相同的 SSE 模式）、记忆管理、文件上传和代理配置。在 `backend/` 中运行 `make test-live` 进行实时 API 测试。

## 终端工作台（TUI）

一个无需 Web UI 即可与 UniDeer 交互的终端界面——从 CLI 新建线程、流式响应、目标和技能命令。用 `deerflow` CLI 命令启动；在非 TTY 上退化为无头 `--print` / `--json` 输出以便脚本化。

## 部署

### 本地开发

```bash
make dev       # Gateway (8001) + Frontend (3000) + Nginx (2026)
make stop      # stop everything
```

### Docker

```bash
make docker-start   # mode-aware development stack from config.yaml (localhost:2026)
make up             # production compose (localhost:2026)
make down           # stop and remove production containers
```

### Kubernetes

Helm chart 位于 `deploy/helm/deer-flow/`，用于 Kubernetes 部署，由 Provisioner 管理沙箱基础设施。

## 安全

UniDeer 在设计上赋予代理真实的文件系统和执行能力。部署必须被视为特权基础设施：

- **不当部署可能引入安全风险。** Gateway 管理员实际上等同于宿主机上的代码执行。
- 本地沙箱默认禁用宿主机 bash；只对完全可信的本地工作流重新启用。
- 浏览器控制在可信调试之外保持 `headless: true` 和 `allow_private_addresses: false`。用 `cdp_url` 附加现有 Chrome 无法强制 SSRF 防护，除非 `allow_unguarded_cdp: true` 明确承认风险，否则失败关闭。
- 将 `config.yaml` 和 `extensions_config.json` 视为可信的操作者控制文件：中间件、工具、模型、沙箱、护栏和 MCP 声明都是代码执行。
- 认证使用 HttpOnly cookie、CSRF 保护和可插拔 RBAC；“保持登录”策略在公网 HTTP 上降级为会话 cookie，仅在 HTTPS 或回环上使用 Secure + Max-Age。

## 文档

- [架构](docs/ARCHITECTURE.md) — 服务拓扑、全部 8 层、数据流、仓库地图、术语表
- [上下文指南](context.md) — 面向编码代理的系统架构与代理上下文
- [计划与 RFC](docs/plans/) — 授权、追踪、记忆等
- [贡献](CONTRIBUTING.md) — 开发环境与工作流
- [安装](Install.md) — 一键代理设置说明

## 贡献

参见 [CONTRIBUTING.md](CONTRIBUTING.md) 了解开发环境设置、必需的命令顺序和验证预期。提交变更前：

- 后端：`cd backend && make lint && make test`（CI 对齐：`uv sync --group dev`，然后 lint，然后 test）
- 前端（如涉及）：`cd frontend && pnpm lint && pnpm typecheck`；生产构建设置 `BETTER_AUTH_SECRET`
- 绝不破坏 harness/app 导入防火墙（`tests/test_harness_boundary.py`）
- 保持异步事件循环无阻塞 I/O（`make test-blocking-io`）
- 修改功能时更新文档（`README.md`）或修改架构/中间件时更新（`AGENTS.md`）

## 许可证

UniDeer 以 **MIT 许可证** 分发——参见 [LICENSE](LICENSE)。作为 DeerFlow（同样是 MIT）的 fork，源自上游项目的部分的原始版权和署名归 ByteDance 和 DeerFlow 贡献者所有。
