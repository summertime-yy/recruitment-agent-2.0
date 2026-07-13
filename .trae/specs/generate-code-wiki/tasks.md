# Tasks: 生成智能招聘 Agent Code Wiki 文档

## Task 1: 创建项目整体架构文档 (code-wiki.md)

- [ ] SubTask 1.1: 编写项目概述部分,包括产品定位、核心目标、MVP范围
- [ ] SubTask 1.2: 绘制系统总体架构图(使用Mermaid),包含前端、后端、Agent核心、工具层、数据层
- [ ] SubTask 1.3: 详细说明Agent推理框架(R-P-R-A-R)的六阶段流程和核心创新点
- [ ] SubTask 1.4: 说明四层记忆架构(L1-L4)的设计原理和实现方式
- [ ] SubTask 1.5: 整理技术栈总览,包括前端(React+Ant Design)、后端(FastAPI+LangGraph)、数据库(PostgreSQL+Redis)
- [ ] SubTask 1.6: 列出MVP的8个核心功能模块及其职责
- [ ] SubTask 1.7: 绘制项目目录结构建议
- [ ] SubTask 1.8: 编写快速开始指南,包括环境准备和启动步骤

## Task 2: 创建模块职责与依赖关系文档 (architecture-modules.md)

- [x] SubTask 2.1: 编写前端模块架构说明
  - 说明12项导航结构(核心流程6项+分析设置2项+Phase 2占位4项)
  - 详细说明8个核心页面(page-1至page-8)的职责和交互逻辑
  - 说明R-P-R-A-R消息流组件的实现要点
  - 列出共享组件库建议(Sidebar、Toast、Modal、PlanCard等)
- [x] SubTask 2.2: 编写Agent核心架构说明
  - 任务编排器(Task Orchestrator)的状态机设计
  - 上下文管理器(Context Manager)的三层信息分离策略
  - 工具路由器(Tool Router)的四层决策模型
  - 结果校验器(Result Validator)的三层校验机制
  - 异常处理器(Exception Handler)的五类异常场景处理
- [x] SubTask 2.3: 编写工具层架构说明
  - 简历解析引擎的实现方案和失败处理策略
  - 智能评分引擎的多维度评分逻辑
  - JD生成器的结构化字段和合规校验
  - 日历集成服务的对接方案(Google Calendar/Outlook)
  - 推送通知服务的渠道对接(邮件/企业IM)
  - 反馈收集系统的三态反馈机制
- [x] SubTask 2.4: 编写数据层架构说明
  - PostgreSQL核心表结构设计(Task、JD、Resume、Candidate、Score、Push、Feedback)
  - Redis缓存策略(工作记忆、日历可用性缓存)
  - 绘制数据流向图,说明从用户输入到最终输出的完整数据流
- [x] SubTask 2.5: 绘制模块依赖关系图(使用Mermaid)
  - 展示前端模块与Agent API的调用关系
  - 展示Agent核心与工具层的调用关系
  - 展示工具层与数据层的读写关系

## Task 3: 创建项目运行与部署指南文档 (deployment-guide.md)

- [ ] SubTask 3.1: 编写开发环境搭建指南
  - 前端开发环境配置(Node.js、React、TypeScript、Ant Design)
  - 后端开发环境配置(Python、FastAPI、LangGraph、虚拟环境)
  - 数据库配置(PostgreSQL 15、Redis 7的安装与初始化)
  - Agent服务配置(LLM API配置、MinIO文件存储配置)
- [ ] SubTask 3.2: 编写生产环境部署指南
  - Docker Compose配置文件示例(前端、后端、数据库、MinIO)
  - 环境变量配置清单(数据库连接、API密钥、文件存储等)
  - 数据库初始化脚本(SQL migration文件)
  - 服务启动流程说明(启动顺序、健康检查)
- [ ] SubTask 3.3: 编写监控与运维指南
  - Prometheus配置方案(采集Agent指标、系统指标)
  - Grafana看板配置(功能健康度、用户接受度)
  - 日志收集方案(结构化日志、日志级别、日志聚合)
  - 告警规则配置(错误率、响应延迟、任务失败率)
- [ ] SubTask 3.4: 编写数据备份与恢复方案
  - PostgreSQL备份策略(每日全量备份、增量备份)
  - Redis持久化配置(RDB+AOF)
  - MinIO数据备份方案
  - 灾难恢复流程

## Task 4: 创建渐进式开发实施路线文档 (development-roadmap.md)

### 核心开发策略:模块优先、逐步验证

采用"从JD管理模块开始,验证闭环后再扩展到其他模块"的渐进式开发策略。每个模块都遵循"数据库表设计→后端API实现→前端页面开发→集成测试验收"的完整闭环,确保每个环节独立可用后再继续扩展。

- [ ] SubTask 4.1: Stage 1 - JD管理模块完整闭环(Week 1-2)
  - **数据库层:** 设计JD表结构(jd_id、title、department、level、skills、requirements等字段),编写migration脚本并验证
  - **后端层:** 实现JD CRUD API(创建、查询、更新、删除),编写JD模板匹配算法(从模板库识别相关JD)
  - **Agent层:** 实现JD生成Agent(基于LLM生成结构化JD),集成合规校验(歧视性词汇检测)
  - **前端层:** 开发page-3 JD管理页面(JD模板库+JD编辑器+关联候选人视图)
  - **验收标准:**
    - JD表成功创建并可通过API进行CRUD操作
    - JD模板匹配算法能从模板库识别3个以上相关JD
    - JD生成Agent能基于用户输入生成完整JD(必填字段完整度>90%)
    - page-3页面可正常渲染并完成JD创建/编辑/保存流程
    - 单元测试覆盖率>70%,集成测试通过率>95%

- [ ] SubTask 4.2: Stage 2 - 任务管理模块(Week 3-4)
  - **数据库层:** 设计Task表结构(task_id、jd_id关联、status、stage、created_at等),与JD表建立关联关系
  - **后端层:** 实现任务管理API(创建任务、更新状态、查询任务列表),实现任务状态机(6状态转换逻辑)
  - **前端层:** 开发page-2任务看板页面(看板视图+列表视图+任务卡片),开发page-1b任务详情页
  - **验收标准:**
    - Task表与JD表正确关联,支持双向查询
    - 任务状态机能正确处理6状态转换(需求解析→JD编写→简历筛选→评分推送→已归档)
    - 任务看板可展示所有任务并支持状态筛选和排序
    - 从任务卡片点击可进入任务详情页并查看关联JD信息

- [ ] SubTask 4.3: Stage 3 - 简历解析模块(Week 5-6)
  - **数据库层:** 设计Resume表结构(resume_id、candidate_id、file_path、parse_status、parsed_data JSONB),设计Candidate表结构(candidate_id、name、contact、education、experience等)
  - **后端层:** 实现简历解析引擎(PDF/DOCX解析、结构化提取),实现候选人管理API
  - **前端层:** 开发page-4简历工作台(上传区+解析结果列表+展开详情+补录弹窗)
  - **验收标准:**
    - Resume和Candidate表成功创建,支持简历文件存储和结构化数据存储
    - 简历解析引擎能解析PDF/DOCX格式,解析成功率>95%
    - 简历工作台可批量上传简历,实时显示解析进度和结果
    - 解析失败简历有明确错误提示和人工补录入口

- [ ] SubTask 4.4: Stage 4 - 评分引擎模块(Week 7-8)
  - **数据库层:** 设计Score表结构(score_id、candidate_id、jd_id双向关联、各维度得分、总分、evidence JSONB),建立Candidate-JD双向关联关系
  - **后端层:** 实现评分引擎(5维度权重计算、总分计算、evidence生成),实现评分API
  - **前端层:** 开发page-5评分报告页面(评分维度配置+候选人排序列表+候选人详情面板)
  - **验收标准:**
    - Score表正确建立Candidate-JD双向关联,支持双向查询(候选人→JD、JD→候选人)
    - 评分引擎能按5维度权重计算总分,evidence包含得分依据文本
    - 评分报告页面可调整权重并实时重新计算,Top20%候选人与人工重合率>70%
    - 支持按JD查看其历史筛选的所有候选人及状态

- [ ] SubTask 4.5: Stage 5 - Agent对话核心(Week 9-10)
  - **Agent层:** 实现R-P-R-A-R推理框架(状态机定义、六阶段流程编排),实现流式消息推送(SSE)
  - **工具层:** 集成已有工具(JD生成器、简历解析器、评分引擎),实现工具调用决策逻辑(四层决策模型)
  - **前端层:** 开发page-1对话任务中心(R-P-R-A-R消息流组件、岗位选择器、底部输入区)
  - **验收标准:**
    - Agent能通过对话完成JD生成任务,展示完整R-P-R-A-R推理过程
    - Plan阶段可展示执行步骤清单,用户可确认/调整/跳过
    - 流式消息能实时渲染(thinking/plan/tool_call/progress/result等7种消息类型)
    - 对话中可调用JD生成器、简历解析器、评分引擎并展示执行过程

- [ ] SubTask 4.6: Stage 6 - 推送与反馈模块(Week 11-12)
  - **数据库层:** 设计Push表结构(push_id、candidate_ids、target_user、status、sent_at),设计Feedback表结构(feedback_id、candidate_id、push_id、feedback_type、reasons)
  - **后端层:** 实现推送服务(邮件/企业IM渠道对接),实现反馈收集API(三态反馈、原因标签)
  - **前端层:** 开发page-6推送反馈页面(推送管理+反馈收集+统计分析)
  - **验收标准:**
    - Push和Feedback表成功创建,推送记录可追溯候选人列表和反馈结果
    - 推送服务能成功发送邮件或企业IM消息,推送成功率>95%
    - 反馈收集支持三态反馈(符合/部分符合/不符合)和原因标签多选
    - 推送反馈页面可展示推送历史和反馈统计(符合率、拒绝原因排行)

- [ ] SubTask 4.7: Stage 7 - 数据看板与系统设置(Week 13-14)
  - **数据库层:** 设计系统配置表(config_id、config_key、config_value JSONB),设计指标采集表(metric_id、metric_type、metric_value、timestamp)
  - **后端层:** 实现指标采集服务(功能健康度指标、用户接受度指标),实现LLM配置API(多模型配置、API密钥管理)
  - **前端层:** 开发page-7数据看板(KPI卡片+SVG图表),开发page-8系统设置(LLM配置+评分引擎参数+系统参数)
  - **验收标准:**
    - 系统配置表支持存储LLM配置、评分引擎参数、系统参数三类配置
    - 指标采集服务能实时采集10+类指标(意图识别准确率、简历解析成功率、任务完成率等)
    - 数据看板能展示实时指标和历史趋势图表
    - 系统设置页面可配置多个LLM模型,支持测试连通性
- [ ] SubTask 4.8: 编写模块优先开发策略总结
  - 总结渐进式开发的核心原则(模块闭环、独立验证、逐步扩展)
  - 说明每个Stage的依赖关系(JD管理→任务管理→简历解析→评分→Agent→推送→看板)
  - 强调数据层优先的设计理念(先建表→验证数据流→再实现业务逻辑)
  - 提供模块组合建议(哪些模块可以并行开发、哪些必须串行)
- [ ] SubTask 4.9: 编写团队分工建议
  - Agent工程师职责(核心推理、工具编排、prompt工程) - 适合负责Stage 5和Agent层实现
  - 后端工程师职责(工具层实现、数据库设计、API开发) - 适合负责Stage 1-4和Stage 6-7的后端部分
  - 前端工程师职责(UI组件开发、状态管理、API对接) - 适合负责所有Stage的前端页面开发
  - 测试工程师职责(测试用例设计、自动化测试、验收测试) - 适合在每个Stage完成后进行验收测试
- [ ] SubTask 4.10: 编写技术风险预案
  - 大模型输出不稳定的应对策略(规则兜底、人工确认、prompt版本管理)
  - 简历解析准确率不足的优化路径(多引擎投票、人工补录、bad-case分析)
  - 数据库设计缺陷的风险(在Stage 1充分验证JD表设计后再扩展其他表)
  - 模块集成失败的预防(每个Stage独立验收后再进行模块间集成)
- [ ] SubTask 4.11: 编写迭代优化机制
  - 每周Stage验收机制(每个Stage完成后进行完整的验收测试)
  - 每2周指标看板review机制(展示已完成模块的核心指标)
  - 每月bad-case分析和优化流程(针对已上线模块的问题进行定向优化)
  - 每季度架构调整评估流程(评估是否需要调整数据库表结构或API设计)

## Task Dependencies

- Task 2 depends on Task 1 (模块详解需要先建立整体架构框架)
- Task 3 depends on Task 2 (部署指南需要明确模块架构才能配置环境)
- Task 4 depends on Task 1, Task 2, Task 3 (开发路线需要基于完整的架构理解)

## 渐进式开发策略的执行顺序

**核心原则:** 数据层优先、模块闭环验证、逐步扩展

**推荐执行顺序:**
1. **Stage 1 (JD管理) 必须最先完成** - 它是所有后续模块的基础,JD表的设计直接影响Task、Score等关联表
2. **Stage 2-4 可以并行推进** - Task管理、简历解析、评分引擎在数据层相对独立,可以并行开发
3. **Stage 5 (Agent核心) 必须等Stage 1-4完成** - Agent需要调用JD生成器、简历解析器、评分引擎,这些工具必须先验证可用
4. **Stage 6-7 可以并行推进** - 推送反馈和数据看板相对独立,可以在Agent核心开发的同时进行前端开发

**数据层优先的具体体现:**
- 每个Stage先设计数据库表,编写migration脚本
- 在数据层验证通过(表结构正确、索引有效、关联关系清晰)后再实现后端API
- 后端API验证通过(单元测试覆盖率>70%)后再开发前端页面
- 前端页面验证通过(交互完整、无明显bug)后再进入下一个Stage

**模块闭环验证的具体体现:**
- 每个Stage都包含完整的验收标准(至少5条量化指标)
- 每个Stage完成后必须进行集成测试,验证模块间数据流是否正确
- 验收不通过的Stage不能进入下一个Stage,必须修复问题后再继续

## Parallel Execution Opportunities

- Task 1和Task 4.8-4.11可以并行编写(策略总结、团队分工、风险预案、迭代机制不依赖具体架构)
- Task 3.3-3.4可以与Task 2并行编写(监控运维方案相对独立)
- 在实际开发中,Stage 2-4可以并行开发(前端工程师可以同时开发page-2、page-4、page-5)
- Stage 6-7可以并行开发(推送反馈和数据看板的前端开发可以同时进行)