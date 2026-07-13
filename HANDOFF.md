# 招聘Agent 2.0 阶段性总结与交接文档

> 生成时间：2026-07-10 17:45
> 当前阶段：Stage 2（简历解析模块）收尾阶段

---

## 一、项目概览

**项目名称**：recruitment-agent-2.0（智能招聘助手）
**技术栈**：
- 后端：Python 3.10+ / FastAPI / SQLAlchemy (async) / Alembic / PostgreSQL / MinIO
- 前端：React 18 + TypeScript + Vite + Ant Design 5 + React Router
- AI：火山引擎 Ark API（DeepSeek-V4-flash 模型）+ LangChain
**项目根目录**：`e:\AI-WORK\Project-Work\recruitment-agent-2.0`

---

## 二、服务运行状态（截至本次会话结束）

| 服务 | 地址 | 状态 |
|------|------|------|
| 后端 API | http://localhost:8000 | ✅ 运行中（uvicorn --reload） |
| 前端 Dev | http://localhost:5173 | ✅ 运行中（npm run dev, Vite HMR） |
| PostgreSQL | （本地/Docker） | ✅ 正常 |
| MinIO | （本地/Docker） | ✅ 正常，bucket: `resumes` |

**启动命令**：
```powershell
# 后端
cd e:\AI-WORK\Project-Work\recruitment-agent-2.0\backend
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 前端
cd e:\AI-WORK\Project-Work\recruitment-agent-2.0\frontend
npm run dev
```

---

## 三、已完成功能（Stage 2 简历解析模块）

### 3.1 后端完成情况

| 功能 | 接口 | 状态 | 关键文件 |
|------|------|------|----------|
| 简历上传 | `POST /api/v1/resumes/upload` | ✅ | [resume.py (endpoint)](file:///e:/AI-WORK/Project-Work/recruitment-agent-2.0/backend/app/api/v1/endpoints/resume.py) |
| 触发解析 | `POST /api/v1/resumes/{id}/parse` | ✅ | BackgroundTasks 异步执行 |
| 简历列表 | `GET /api/v1/resumes`（分页、状态筛选、关键词） | ✅ | 支持 page/page_size/parse_status/keyword |
| 简历详情 | `GET /api/v1/resumes/{id}` | ✅ | 返回完整 parsed_content |
| 删除简历 | `DELETE /api/v1/resumes/{id}` | ✅ | 同时删除MinIO文件 |
| **原始文件预览** | `GET /api/v1/resumes/{id}/preview` | ✅ | StreamingResponse 代理 MinIO 文件流 |
| **解析结果编辑** | `PUT /api/v1/resumes/{id}` | ✅ | 支持更新 name/phone/email/parsed_content |
| JD模块基础 | JD CRUD | ✅ | Stage 1 已完成 |

**关键配置（backend/.env）**：
```
LLM_MODEL=deepseek-v4-flash-260425       # ⚠️ 必须用DeepSeek-V4-flash，不能用doubao-seed
LLM_MAX_TOKENS=4096                       # ⚠️ 4096是当前验证可用的值
LLM_TIMEOUT=180
MINIO_RESUME_BUCKET=resumes
DATABASE_URL=postgresql+asyncpg://...
```

**关键后端文件说明**：
- [llm_adapter.py](file:///e:/AI-WORK/Project-Work/recruitment-agent-2.0/backend/app/agent/llm_adapter.py)：LLM调用适配器，**ChatOpenAI max_retries=0**（避免重试叠加超时），**不包含 reasoning_effort 参数**（DeepSeek不兼容）
- [resume.py (service)](file:///e:/AI-WORK/Project-Work/recruitment-agent-2.0/backend/app/services/resume.py)：简历服务层，包含 `parse_resume_background()` 后台任务、`get_file_stream()` 预览流、`update_resume()` 更新方法
- [resume.py (endpoint)](file:///e:/AI-WORK/Project-Work/recruitment-agent-2.0/backend/app/api/v1/endpoints/resume.py)：API路由，**注意路由顺序**：`/preview` 必须定义在 `/{resume_id}` 之前，否则会被路径参数匹配覆盖

### 3.2 前端完成情况

| 页面/组件 | 路由 | 状态 | 关键文件 |
|-----------|------|------|----------|
| 简历工作台 | `/resumes` | ✅ | [Resumes.tsx](file:///e:/AI-WORK/Project-Work/recruitment-agent-2.0/frontend/src/pages/Resumes.tsx) |
| 简历详情预览 | `/resumes/:id` | ✅ | [ResumeDetail.tsx](file:///e:/AI-WORK/Project-Work/recruitment-agent-2.0/frontend/src/pages/ResumeDetail.tsx) |
| 简历编辑Modal | 共享组件 | ✅ | [ResumeEditModal.tsx](file:///e:/AI-WORK/Project-Work/recruitment-agent-2.0/frontend/src/components/ResumeEditModal.tsx) |
| JD列表/生成 | `/jds`, `/jds/generate` | ✅ | Stage 1 已完成 |

**前端关键功能**：
1. **拖拽上传简历**：支持PDF/DOCX，上传后自动进入解析流程
2. **智能轮询**：2秒间隔轮询解析状态，解析完成/失败自动停止并通知
3. **列表功能**：分页、状态筛选（待解析/解析中/已解析/失败）、关键词搜索、批量统计卡片
4. **展开行详情**：点击行展开显示结构化解析内容
5. **右侧面板**：选中候选人后右侧展示详细信息+匹配入口
6. **预览流程**：列表"预览"按钮 → 跳转到 `/resumes/:id` 详情页 → 详情页"查看原始简历"按钮 → 新标签页打开PDF/DOCX
7. **编辑功能**：列表和详情页均可打开编辑Modal，支持修改基础信息+教育/工作/项目经历+技能标签
8. **重新解析**：失败/已解析状态均可触发重新解析

**前端服务层**：[resume.ts](file:///e:/AI-WORK/Project-Work/recruitment-agent-2.0/frontend/src/services/resume.ts)
```typescript
resumeApi.list(params)        // GET /api/v1/resumes
resumeApi.getById(id)         // GET /api/v1/resumes/{id}
resumeApi.upload(file)        // POST /api/v1/resumes/upload
resumeApi.parse(id)           // POST /api/v1/resumes/{id}/parse
resumeApi.delete(id)          // DELETE /api/v1/resumes/{id}
resumeApi.update(id, data)    // PUT /api/v1/resumes/{id}
resumeApi.getPreviewUrl(id)   // 返回 /api/v1/resumes/{id}/preview 字符串
```

**Vite代理配置**：[vite.config.ts](file:///e:/AI-WORK/Project-Work/recruitment-agent-2.0/frontend/vite.config.ts) 中 `/api` 代理到 `http://localhost:8000`

---

## 四、已知问题与待验证项

### ⚠️ 需要下一位Agent验证的问题

1. **新上传简历解析成功率**：本次会话将模型切换为 DeepSeek-V4-flash + max_tokens=4096，但在会话结束前**未来得及验证新上传简历是否能100%解析成功**。请刷新前端页面，上传一份新简历进行测试，重点观察：
   - 后端日志中 LLM 响应是否完整（无 length limit 错误）
   - 解析完成后 `candidate_name`、`parsed_content` 是否正常填充
   - 如果仍然出现截断错误，将 `LLM_MAX_TOKENS` 提高到 `8192` 再试

2. **DOCX文件解析**：当前DOCX解析使用 `python-docx` 库，请验证DOCX文件上传、解析、预览全链路是否正常

3. **长简历文本截断**：当前 [resume.py (service)](file:///e:/AI-WORK/Project-Work/recruitment-agent-2.0/backend/app/services/resume.py) 中传给LLM的 `raw_text` 截断长度需要确认（此前记忆中记录为8000字符，请确认实际代码中的值）

### 已知的小问题（不影响核心功能）

1. 列表中"置信度"列目前使用随机数展示（ScoreRing组件），后续需要接入真实的AI匹配评分
2. "候选人→JD匹配"面板显示"匹配功能将在Stage 4评分模块完成后开放"
3. 批量解析、批量导出按钮显示"功能开发中"

---

## 五、踩坑记录（重要！）

### 5.1 LLM相关
- **❌ 不要使用 doubao-seed-2-1-turbo（推理模型）做简历解析**：其内部推理链会消耗大量completion tokens，即使设置max_tokens=4096也可能全部被reasoning_tokens占满导致JSON输出被截断
- **❌ 不要设置 reasoning_effort 参数**：DeepSeek模型不兼容此参数，会导致API报错
- **❌ 不要多层重试**：Skill层和LangChain ChatOpenAI层都设置max_retries会导致超时叠加（2次×120秒=240秒 > 前端180秒超时）。必须两处都设为 max_retries=0
- **✅ 使用 DeepSeek-V4-flash**：结构化提取效果好，无推理token开销，max_tokens=4096足够

### 5.2 前端相关
- **❌ 不要用动态创建 `<a>` 元素的方式打开新窗口**：`document.createElement('a').click()` 可能被浏览器安全策略拦截
- **✅ 使用 `window.open(url, '_blank', 'noopener,noreferrer')`**：在onClick同步事件上下文中直接调用，不会被拦截
- **❌ 不要在Modal关闭/未挂载时调用 Form.useForm() 对应的 form.setFieldsValue**：会导致 "useForm is not connected to any Form element" 警告
- **✅ 正确做法**：将Modal+Form抽成独立子组件，父组件使用条件渲染 `{visible && <EditModal />}` 确保只在打开时挂载
- **Ant Design v5**：`destroyOnClose` 已废弃，使用 `destroyOnHidden` 代替
- **FastAPI路由顺序**：`GET /{resume_id}/preview` 必须定义在 `GET /{resume_id}` 之前

---

## 六、下一步计划

### 近期（Stage 2 收尾）
1. **验证简历解析稳定性**：上传多份不同长度/格式的简历，确认解析成功率100%
2. **简历解析字段完善**：确认parsed_content的Schema是否完整覆盖需求（当前包含 summary/education/work_experience/project_experience/skills）
3. **错误处理优化**：解析失败时展示更友好的错误信息

### Stage 3 - 候选人管理模块
- 候选人标签/分类
- 候选人状态流转（新简历→初筛通过→面试中→录用/淘汰）
- 候选人搜索与筛选增强
- 候选人备注与评价

### Stage 4 - 人岗匹配评分模块
- JD与简历的AI匹配评分
- 多维度匹配度展示
- 匹配报告生成
- 候选人排序推荐

### Stage 5 - 面试安排与反馈
- 面试日程管理
- 面试评价表
- 面试反馈记录

---

## 七、关键文件速查表

### 后端文件
| 文件 | 用途 |
|------|------|
| [backend/.env](file:///e:/AI-WORK/Project-Work/recruitment-agent-2.0/backend/.env) | 环境变量（LLM配置、数据库、MinIO） |
| [backend/app/main.py](file:///e:/AI-WORK/Project-Work/recruitment-agent-2.0/backend/app/main.py) | FastAPI应用入口 |
| [backend/app/agent/llm_adapter.py](file:///e:/AI-WORK/Project-Work/recruitment-agent-2.0/backend/app/agent/llm_adapter.py) | LLM适配器（max_retries=0, 无reasoning_effort） |
| [backend/app/services/resume.py](file:///e:/AI-WORK/Project-Work/recruitment-agent-2.0/backend/app/services/resume.py) | 简历服务（上传/解析/预览/更新/删除） |
| [backend/app/api/v1/endpoints/resume.py](file:///e:/AI-WORK/Project-Work/recruitment-agent-2.0/backend/app/api/v1/endpoints/resume.py) | 简历API路由 |
| [backend/app/models/resume.py](file:///e:/AI-WORK/Project-Work/recruitment-agent-2.0/backend/app/models/) | 简历数据模型（Resume） |
| [backend/app/schemas/resume.py](file:///e:/AI-WORK/Project-Work/recruitment-agent-2.0/backend/app/schemas/) | Pydantic Schema（ResumeCreate/ResumeResponse/ResumeUpdateRequest） |

### 前端文件
| 文件 | 用途 |
|------|------|
| [frontend/src/App.tsx](file:///e:/AI-WORK/Project-Work/recruitment-agent-2.0/frontend/src/App.tsx) | 路由配置 |
| [frontend/src/pages/Resumes.tsx](file:///e:/AI-WORK/Project-Work/recruitment-agent-2.0/frontend/src/pages/Resumes.tsx) | 简历工作台（列表/上传/筛选/展开/右侧面板） |
| [frontend/src/pages/ResumeDetail.tsx](file:///e:/AI-WORK/Project-Work/recruitment-agent-2.0/frontend/src/pages/ResumeDetail.tsx) | 简历详情预览页 |
| [frontend/src/components/ResumeEditModal.tsx](file:///e:/AI-WORK/Project-Work/recruitment-agent-2.0/frontend/src/components/ResumeEditModal.tsx) | 共享编辑弹窗组件 |
| [frontend/src/services/resume.ts](file:///e:/AI-WORK/Project-Work/recruitment-agent-2.0/frontend/src/services/resume.ts) | 简历API服务层 |
| [frontend/src/types/index.ts](file:///e:/AI-WORK/Project-Work/recruitment-agent-2.0/frontend/src/types/index.ts) | TypeScript类型定义 |
| [frontend/vite.config.ts](file:///e:/AI-WORK/Project-Work/recruitment-agent-2.0/frontend/vite.config.ts) | Vite配置（API代理） |
| [frontend/src/utils/request.ts](file:///e:/AI-WORK/Project-Work/recruitment-agent-2.0/frontend/src/utils/request.ts) | Axios封装（timeout=180s） |

---

## 八、快速验证清单（下次启动后）

```
1. 打开浏览器访问 http://localhost:5173/resumes
2. 确认后端已启动 http://localhost:8000/docs 可访问
3. 上传一份PDF简历 → 应在1秒内返回，状态显示"解析中"
4. 等待10-30秒 → 应自动变为"已解析"，姓名/技能等字段正确填充
5. 点击"预览"按钮 → 应跳转到详情页 /resumes/{id}
6. 在详情页点击"查看原始简历" → 应在新标签页打开PDF
7. 点击"编辑修正" → 弹出编辑Modal，修改后保存应成功
8. 点击"重新解析" → 应重新触发解析流程
9. 对已失败的简历点击"重新解析" → 应在新配置下成功解析
```
