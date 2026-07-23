## Why

当前 external 营销智能体与 internal 合同审查/风控智能体已经能够按部署 profile 独立运行，但现有运维脚手架只覆盖单实例，无法安全地在没有域名的试用服务器上通过“同一 IP、不同端口”同时启动两套服务。若直接复制现有配置，会出现前端产物覆盖、Cookie 因不区分端口而串用、seed 向两个数据库写入混合演示数据、依赖与凭证边界不清等问题。

本提案落实 `PLAN-internal.md` I1 的双 profile 运维脚手架、profile-aware seed 与独立 CORS/凭证配置，以及 I8 的内部部署 README 和安全 checklist；同时把 ADR-015 的正式双机目标补充为一个有退出条件的“试用期同机双实例”过渡拓扑。正式生产仍以 external/internal 分机和网络隔离为目标。

## What Changes

- 新增 single-host dual-profile 试用部署模式：同一物理服务器从同一代码版本启动 external、internal 两个独立后端进程，并通过同一 IP 的不同前端端口分别提供营销入口和内部智能体入口。
- 新增 external/internal 两套部署模板，包括独立环境变量示例、systemd unit、Nginx upstream/server、静态产物目录、日志标识、迁移/启动/整体回滚步骤和健康检查。服务器沿用一份固定 Git checkout，不引入版本化 release 或 `current` 软链接。
- 为同 IP 不同端口场景提供安全的会话命名空间：两套实例 MUST 使用不同的 HttpOnly auth Cookie 名称；embed Cookie 在启用时同样不得冲突，并补充 profile 级默认值、配置说明和回归测试。
- 扩展前端 profile 配置，使两次构建能输出到互不覆盖的目录；external/internal 登录页显示不同的产品名称和用途说明，并保持 external 登录后进入营销问答、internal 登录后进入内部工作台。
- 将 seed 改为 profile-aware 初始化：external 只创建外部营销所需组织、用户、Agent、权限和演示数据；internal 只创建内部组织、部门、管理员、合同审查/风控 Agent 及所需权限。初始化 MUST 拒绝与运行时 `DEPLOYMENT_PROFILE` 不一致的目标 profile。
- 新增双实例部署前检查和验收脚本/清单，验证端口、路由边界、Cookie 名称、数据库目标、Dify/MinIO 凭证命名空间、external 构建不包含 internal 页面，以及 internal 入口只向允许的内网来源开放。
- 更新 ADR-015、部署架构和运维文档，记录试用期同机例外、风险接受、转正式分机的退出条件，以及无域名 HTTP 仅允许在受控内网/VPN 使用的限制。

## Non-goals

- 不把 external 与 internal 合并为一个后端进程、一个前端构建或一个数据库 schema。
- 不允许两套实例共享数据库账号、Dify API Key、MinIO service account、对象存储 bucket 或 Cookie 名称。
- 不修改营销问答、合同审查、风控助手的业务 API、TaskHandler、规则、工作流或结果契约。
- 不建设跨 profile SSO、统一用户目录、统一会话或根据用户类型在同一登录请求中动态选择后端。
- 不实现域名申请、公共 CA 证书自动化、容器编排、负载均衡或正式生产的高可用方案。
- 不为试用期维护 external/internal 独立代码版本；两套实例使用同一 checkout 并整体升级或回滚。
- 不把同机试用拓扑定义为正式生产安全基线；达到真实外部客户或高敏合同生产使用条件后仍需按 ADR-015 拆分主机/网络边界。

## Capabilities

### New Capabilities

- `single-host-dual-profile-deployment`: 在同一试用服务器上以不同端口安全运行 external/internal 双实例，覆盖构建产物、进程、入口、Cookie、初始化、依赖、凭证边界、验收和后续拆分迁移要求。

### Modified Capabilities

无。现有营销问答、合同审查 Web 工作台、合同审查任务和风控助手规格的业务行为保持不变。

## Impact

- 后端配置与安全：`backend/app/core/config.py`、Cookie 写入/清理逻辑及相关配置测试；不新增数据库字段，不需要 Alembic migration。
- 初始化：`backend/scripts/seed.py` 及 profile 隔离测试，避免内部库出现外部演示账号或外部库出现内部 Agent。
- 前端：deployment profile 展示配置、登录页文案/辅助信息、默认跳转测试、双 profile 构建输出与产物隔离检查。
- 部署：新增 `deploy/profiles/external/`、`deploy/profiles/internal/`、双端口 Nginx 配置、两套 systemd unit、环境变量模板、安装/迁移/seed/回滚/验收文档；目录结构收敛为 `/opt/agenthub/repo`、两个固定 venv 和两个 `frontend/dist` 子目录。
- 运维与安全：数据库仍部署在独立服务器并使用两个 schema/账号；Dify 和 MinIO 即使共用宿主服务，也必须使用不同 App/API Key、service account 和 bucket。internal 前端端口必须通过主机防火墙/Nginx allowlist 限制到公司内网或 VPN。
- 文档：更新 `DECISIONS.md` ADR-015、`Archi.md` 部署形态、`README.md`、`docs/deployment.md`、`PLAN-internal.md` 和 `CHANGELOG.md`。
