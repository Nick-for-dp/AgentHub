## Context

AgentHub 当前以 `DEPLOYMENT_PROFILE=external|internal` 区分两套交付：通用认证、管理和聊天路由始终存在，`/api/v1/internal/*` 只在 internal 后端注册；前端通过 `VITE_DEPLOYMENT_PROFILE` 在构建期移除或加入 internal 路由。该边界适合分机部署，但仓库中的 `deploy/nginx/agenthub.conf`、`deploy/systemd/agenthub-backend.service`、单一 `frontend/dist` 和通用 `seed.py` 仍按“一个主机只有一个实例”假设编写。

试用阶段没有域名，external 营销入口和 internal 合同审查/风控入口需要共用同一应用服务器，通过同一 IP 的不同端口访问；MySQL 位于另一台服务器。HTTP Cookie 不区分端口，现有两实例都会写入 `agenthub_session; Path=/`，因此仅复制进程配置会造成会话覆盖。当前 seed 还会在一次运行中同时创建外部演示用户、营销 Agent、内部管理员、合同审查 Agent 和风控 Agent，无法作为两个独立数据库的安全初始化入口。

本 change 是 ADR-015 正式分机方案之前的试用期过渡能力。应用进程允许同机，但数据库 schema/账号、Dify App/API Key、MinIO service account/bucket、Cookie 命名空间和入口访问面继续隔离；达到退出条件后应能把 internal 运行目录和配置整体迁移到独立主机，而无需修改业务代码或数据模型。

模块边界如下：

- backend config/security：只负责解析 profile 级配置和写入/清理对应 Cookie，不新增业务 endpoint。
- backend seed script：负责 profile-aware bootstrap；继续通过现有 service/repository 创建数据，不绕过密码、权限或 Agent 服务边界。
- frontend config/page：只根据构建 profile 展示入口名称并选择现有默认路由；不直接调用 Dify、MinIO SDK 或文件解析库。
- deploy：负责两套进程、静态产物、端口、环境文件、依赖、日志和预检；不把部署差异写入业务 service/repository/integration client。
- database：沿用同一 Alembic migration 链，在两个独立数据库分别执行；本 change 不增加表或字段，不需要新 migration。

## Goals / Non-Goals

**Goals:**

- 在一台 Ubuntu 试用服务器上从同一代码版本稳定运行 external/internal 两个独立 AgentHub 实例。
- 通过同一 IP 的不同前端端口提供清晰分割的营销登录入口和内部智能体登录入口。
- 消除 Cookie、前端产物、Python 依赖、seed 数据、端口、日志和凭证的跨 profile 冲突。
- 提供可重复执行、可预检、可分别迁移/回滚的运维脚手架。
- 保持 external 不注册 internal API、不打包 internal 页面、不安装 PyMuPDF 的既有边界。
- 记录无域名 HTTP 试用的风险、内网限制和转 HTTPS/分机的退出条件。

**Non-Goals:**

- 不把两个 profile 合并为一个运行时实例、一个数据库或一个统一登录后端。
- 不新增用户类型选择型登录 API、跨 profile SSO 或共享 Session。
- 不改变营销问答、合同审查、风控助手的 API、任务、规则、Dify workflow 或对象存储业务流程。
- 不引入 Docker/Kubernetes、服务发现、负载均衡、多副本或自动证书签发。
- 不把同机模式作为真实公网营销流量和高敏合同生产处理的最终安全架构。

## Decisions

### 1. 同机运行两个完整实例，而不是让一个 internal 实例兼任 external

Nginx 提供两个独立 origin，例如 `http://<ip>:8080` 和 `http://<ip>:8081`；external backend 监听 `127.0.0.1:8240`，internal backend 监听 `127.0.0.1:8241`。每个前端 origin 的 `/api/` 只代理到对应 backend，健康检查、静态目录和日志也分别配置。

虽然 internal backend 仍包含通用 `/chat`，但用一个 internal 实例同时服务营销用户会合并数据库、会话、依赖和内部 API 攻击面，违背 ADR-015 的数据/凭证边界，因此不采用。两个 profile 使用同一 Git commit，减少试用期版本漂移；服务可单独重启，任一实例故障不要求停止另一实例。

备选的同一端口路径前缀方案（如 `/marketing`、`/internal-app`）需要修改 Vite base、Vue Router history base、绝对 `/api` 路径和 Cookie path，并使后续迁移到域名更复杂，因此不采用。

### 2. 共享只读源码版本，分离运行环境和前端产物

部署目录使用一份 release/source tree，systemd unit 通过独立 `EnvironmentFile` 注入配置，并使用显式虚拟环境解释器：

```text
/opt/agenthub/releases/<revision>/
/opt/agenthub/venvs/external/
/opt/agenthub/venvs/internal/
/opt/agenthub/frontend-dist/external/
/opt/agenthub/frontend-dist/internal/
/etc/agenthub/external.env
/etc/agenthub/internal.env
```

external venv 只安装基础依赖；internal venv 使用 `uv sync --extra internal` 的等价隔离安装，确保 external 运行环境不包含 `pymupdf`。systemd 不依赖仓库内共享 `.env` 或共享 `.venv`，避免 profile 之间读取错误配置。

Vite 新增可选构建输出配置或等价脚本，使 external/internal 构建分别写入独立目录。现有 `npm run build` 的单实例开发行为保持兼容；双 profile 发布命令连续构建两次并检查 external 产物不含 internal 路由、页面 chunk 和文案。

备选的两份 Git checkout 更容易理解，但升级时可能指向不同 commit，并重复占用源码/Node 安装空间；保留为手工兜底，不作为模板默认方案。

### 3. 使用 profile-aware Cookie 默认值，并由预检阻止冲突

浏览器 Cookie 以 host/path 命中，不以端口隔离。backend `Settings` 提供 profile-aware 的有效 Cookie 名称：external 保持现有 `agenthub_session` 兼容，internal 在未显式配置时使用 `agenthub_internal_session`。若显式设置 `AUTH_COOKIE_NAME`，写入和删除必须使用同一解析结果；空名称必须启动失败。

embed 默认只在 external 启用。若 internal 被显式允许启用 embed，其 `EMBED_SESSION_COOKIE_NAME` 必须与 external 不同；双实例部署预检会比较两个环境文件中的有效 auth/embed Cookie 名称，只报告字段名和冲突结果，不输出 Cookie 值、密钥或连接串。

IP 访问使用 host-only Cookie：`AUTH_COOKIE_DOMAIN` 和 `EMBED_COOKIE_DOMAIN` 留空，`Path=/` 保持现状。HTTP 试用使用 `Secure=false`，但 runbook 必须声明仅允许受控内网/VPN；切换 IP SAN 证书或域名 HTTPS 后改为 `Secure=true`。

仅依赖运维人员手填两个不同名称容易遗漏，因此不采用“只改文档、不改默认解析”的方案。

### 4. 登录页按构建 profile 展示身份，认证仍由两个数据库自然隔离

前端 deployment profile 配置增加稳定的产品展示元数据。external 登录页显示“AgentHub 营销智能体”和产品咨询/营销问答说明；internal 登录页显示“AgentHub 内部智能体”和合同审查/风控工作台说明。登录表单、认证 API 和错误处理继续复用现有实现。

登录成功后沿用现有跳转：external 普通用户进入 `/chat`，internal 普通用户进入 `/internal/contract-review`，管理员进入 `/admin/agents`。internal 顶部导航已经提供合同审查/风控助手切换，本 change 不新增智能体选择首页。

不在单个登录页增加“外部/内部用户”单选项。入口端口已经确定目标 backend，且两个数据库的用户集合不同；让用户在表单中选择 profile 会重新引入跨实例路由和错误目标认证问题。

### 5. seed 按 profile 拆分，同时保留共享 bootstrap helper

`backend/scripts/seed.py` 增加明确的 profile 参数，默认取 `Settings.deployment_profile`。显式参数若与运行时 profile 不一致则 fail closed，不连接另一个数据库尝试初始化。内部实现拆为共享平台管理员/bootstrap helper、external seed 和 internal seed：

- external：创建外部客户组织/演示用户、营销 `qa` Agent、知识库、外部调用权限及 external 管理所需管理员；不创建合同审查、风控 Agent 和内部业务部门数据。
- internal：创建内部公司、部门、管理员、合同审查 Agent、风控 Agent及其权限；不创建外部客户演示账号、营销 Agent 或外部 API Key。

两条路径都必须幂等。production 模式不打印默认密码、原始 API Key、Dify Key 或连接串；需要一次性凭证时通过显式安全 bootstrap 流程返回，不能依赖可重复 seed 的标准输出。

备选方案是复制成两个脚本，但会使用户、Agent、权限创建规则快速漂移，因此采用一个入口加 profile-specific helper。

### 6. 通过 profile 部署模板与无秘密预检保护逻辑隔离

新增 `deploy/profiles/external/`、`deploy/profiles/internal/` 和 single-host runbook。模板分别声明前端端口、backend loopback 端口、环境文件、静态目录、日志、数据库、Dify 和对象存储命名空间。internal Nginx server 默认 `deny all`，只有明确填写的公司内网/VPN CIDR 才 `allow`；external 入口按试用范围开放。

预检至少验证：

- profile 值和端口不重复；
- auth/embed Cookie 名称不重复；
- database URL/schema/账号不相同；
- API Key 签名密钥、Auth 密钥、Dify Key、MinIO access key 不复用；
- raw/parsed bucket 不相同且使用 `ext-*` / `int-*` 命名空间；
- internal embed 默认关闭，internal CORS/MinIO CORS 精确包含带端口 origin；
- external venv 不含 `fitz`，internal venv具备 DOCX/PDF 解析依赖；
- 两套前端产物存在且 external 产物不包含 internal 页面资源。

预检对敏感值只做缺失、相等性和占位符检查，输出脱敏字段名与结论，不回显值。无法静态验证的数据库授权、MinIO policy 和防火墙规则进入人工验收清单。

### 7. 同一 migration 链分别执行，发布和回滚按 profile 独立

部署顺序为：记录 ADR-015 试用例外 → 准备两个数据库/账号与外部依赖凭证 → 创建两套 venv和前端产物 → 对 external/internal 环境分别执行 `alembic upgrade head` → 分别运行 profile-aware seed → 启动两个 backend → 安装/验证 Nginx → 执行 smoke tests。

发布使用版本化 release 目录和 profile 独立的静态目录/服务重启。若 internal 发布失败，可只恢复 internal 静态目录与 systemd release 指针；external 保持运行。数据库 migration 仍遵循现有向前兼容约束，本 change 本身没有 schema 变更。

smoke tests 包括：两个 `/health` 成功、两个登录页品牌正确、external internal API 返回 404、internal internal API 未登录返回 401、两个登录响应的 `Set-Cookie` 名称不同、external 登录进入 `/chat`、internal 登录进入 internal 工作台、合同文件预签名 URL 可从 internal origin 上传。

### 8. 同机模式有明确退出条件，不替代 ADR-015 正式拓扑

出现任一条件时必须安排 internal 迁移到独立主机/网络：开始接入真实公网营销用户、开始处理未经脱敏的高敏合同/单据、合规要求主机级隔离、任一 profile 资源争抢影响另一 profile、需要独立发布节奏或需要高可用。迁移只复制 internal venv/静态产物/环境文件/systemd/Nginx 配置并切换入口 IP，数据库、Dify 和 MinIO 命名空间保持不变。

## Risks / Trade-offs

- [同一主机被攻破后两个 profile 都可能受影响] → 明确仅限试用；backend 只绑定 loopback，internal 端口默认拒绝非内网来源，凭证/账号/目录权限分离，并设置退出条件。
- [HTTP 传输暴露手机号、密码和合同正文] → 仅在可信内网/VPN使用，文档醒目标注风险；优先准备带 IP SAN 的内部 CA/自签证书，真实外部用户或真实高敏数据前必须启用 HTTPS。
- [Cookie 仍因错误显式配置而冲突] → profile-aware 默认值、双环境预检和端到端 `Set-Cookie` smoke test 三层防护。
- [共享主机 CPU/内存/磁盘争抢] → 两个 systemd unit 使用独立日志和可选资源限制；监控长请求、磁盘和内存，达到阈值即触发分机。
- [共享代码升级同时影响两个服务] → 固定同一 release revision，先跑双 profile 构建/测试，按 profile 顺序重启并保留独立回滚指针。
- [seed 误向错误数据库写数据] → 参数与 `DEPLOYMENT_PROFILE` 必须一致，预检数据库/schema，profile-specific 断言和测试验证不产生另一 profile 资源。
- [Nginx allowlist 配错导致 internal 暴露] → internal 模板默认 `deny all`，没有显式 CIDR 时预检失败；通过外部网络视角执行拒绝验收。
- [external 安装 internal AGPL 依赖] → 使用独立 venv，预检 external 环境不存在 `fitz`，保持 ADR-016 边界。

## Migration Plan

1. 在 `DECISIONS.md` 补充 ADR-015 试用期同机例外及退出条件，并同步 `Archi.md`。
2. 生成两套环境文件和强随机密钥，准备远端 MySQL 两个 schema/账号、独立 Dify App/API Key和 MinIO service account/bucket。
3. 创建 external/internal 虚拟环境与双前端构建产物，执行无秘密预检。
4. 分别执行 migration 和 profile-aware seed，核对两个数据库只包含对应 profile 的初始化资源。
5. 启动两个 systemd backend，安装双端口 Nginx，先保持 internal 端口仅对运维 IP开放。
6. 完成 smoke、登录、营销问答、合同上传审查、风控工作台和跨入口 Cookie 隔离验收后，再扩大内网试用范围。
7. 回滚时只停止失败 profile、恢复该 profile 上一 release/静态目录并重启；不删除另一 profile 的运行目录或数据库。

## Open Questions

- external/internal 前端端口的最终值和公司内网/VPN CIDR由目标服务器网络策略确定；模板使用可替换示例值，不写死业务环境地址。
- Dify 与 MinIO 是否同样位于该应用服务器由运维资源决定；无论物理位置如何，本 change 都要求 App/API Key、service account和 bucket 逻辑隔离。
- IP SAN HTTPS是在首轮纯内网试用前完成，还是作为扩大试用范围的门槛，由部署评审确认；真实外部用户和真实高敏合同使用前必须完成。
