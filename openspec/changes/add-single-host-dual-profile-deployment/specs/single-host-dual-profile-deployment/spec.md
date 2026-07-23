## ADDED Requirements

### Requirement: 单台试用服务器运行两个独立 deployment profile

系统 SHALL 支持在同一物理服务器、同一代码版本上同时运行一个 external AgentHub实例和一个 internal AgentHub实例。两个实例 MUST 使用独立进程、独立环境配置、不同 backend loopback端口、不同前端 origin和不同日志标识；任一实例的停止、重启或失败 MUST NOT 要求停止另一实例。

external 实例 MUST 保持现有 profile 边界，不注册 `/api/v1/internal/*`；internal 实例 MUST 只在 `DEPLOYMENT_PROFILE=internal` 时注册 internal 路由。该同机模式 SHALL 被标记为受控试用拓扑，不得替代 ADR-015 的正式分机目标。

#### Scenario: 两个实例从同一版本同时启动

- **WHEN** 运维使用同一 Git checkout和两份 profile 环境配置启动服务
- **THEN** external、internal backend分别在配置的不同 loopback端口健康运行，且各自报告并执行对应 deployment profile

#### Scenario: external 不暴露 internal API

- **WHEN** 调用方通过 external 前端 origin请求 `/api/v1/internal/contract-review/tasks`
- **THEN** external 实例返回 404 或等价未注册结果，不把请求转发到 internal backend

#### Scenario: 单独重启 internal 不影响 external

- **WHEN** 运维停止或重启 internal systemd unit
- **THEN** external 健康检查和营销问答入口继续可用，external进程不被重启

### Requirement: 同一 IP 通过不同端口提供分割的前端入口

系统 SHALL 为 external 与 internal 构建和发布互不覆盖的前端静态产物，并通过同一 IP的不同端口提供两个 origin。external 登录页 MUST 明确标识营销智能体用途，internal 登录页 MUST 明确标识合同审查与风控用途；两个入口 MUST 各自只调用同 origin Nginx代理的对应 backend。

external 构建 MUST 在编译期移除 internal 路由、导航和页面资源。普通 external用户登录后 MUST进入 `/chat`；普通 internal用户登录后 MUST进入 internal工作台；管理员继续进入管理端。

#### Scenario: 两次构建产物互不覆盖

- **WHEN** 发布流程连续构建 external 和 internal 前端
- **THEN** 两套产物写入不同目录，第二次构建不会删除或替换第一次构建的 `index.html` 与 assets

#### Scenario: 两个登录页身份清晰

- **WHEN** 用户分别访问 external 和 internal 的 IP端口登录页
- **THEN** 页面显示不同的产品名称与用途说明，但继续使用现有手机号密码登录表单和错误处理

#### Scenario: 登录后进入对应智能体界面

- **WHEN** 非管理员用户在 external 或 internal入口成功登录
- **THEN** external用户进入营销问答 `/chat`，internal用户进入 `/internal/contract-review` 并可通过现有导航切换风控助手

#### Scenario: external 产物不包含 internal 页面

- **WHEN** 对 external生产构建产物执行路由、chunk和文案检查
- **THEN** 产物中不存在合同审查、风控助手的页面 chunk、导航或 internal默认入口

### Requirement: 同 IP 不同端口的会话 Cookie 必须隔离

系统 MUST 为 external 与 internal实例解析不同的 HttpOnly auth Cookie名称，因为 Cookie不按端口隔离。external 未显式配置时 SHALL 保持兼容的 `agenthub_session`；internal 未显式配置时 SHALL 使用不同的 profile级默认名称。写入、探测、刷新、登出和清理 MUST 使用当前实例解析后的同一 Cookie名称。

IP访问场景 MUST 使用 host-only Cookie，不得配置共享 Cookie Domain。若任一实例启用 embed session，其 embed Cookie名称也 MUST 与另一实例不同。部署预检和 smoke test MUST 检测名称冲突且不得输出 Cookie值或会话原文。

#### Scenario: 两个登录响应设置不同 Cookie

- **WHEN** 同一浏览器分别在 external 和 internal端口登录
- **THEN** 两个 `Set-Cookie` 响应使用不同名称，且浏览器可同时保持两个有效会话

#### Scenario: external 登出不清除 internal 会话

- **WHEN** 用户在 external入口登出后继续访问 internal入口
- **THEN** external Cookie被清除，internal Cookie仍然存在且 internal会话状态不受影响

#### Scenario: Cookie名称冲突时预检失败

- **WHEN** 两份部署配置解析出的 auth Cookie名称相同，或启用的 embed Cookie名称相同
- **THEN** 双实例预检以非零状态失败并只报告冲突字段，不启动或发布该配置

### Requirement: profile-aware seed 只初始化目标 profile 数据

初始化入口 SHALL 支持 `external` 或 `internal` profile，并默认采用当前 `DEPLOYMENT_PROFILE`。显式 seed profile与运行时 profile不一致时 MUST fail closed，不得继续写库。两条 seed路径 MUST幂等并继续通过现有 service/repository执行密码校验、Agent创建和权限落库。

external seed SHALL创建营销服务所需的平台管理员、外部组织/演示用户、营销 Agent、知识库和权限，但 MUST NOT创建合同审查 Agent、风控 Agent或内部业务部门。internal seed SHALL创建内部公司、部门、管理员、合同审查 Agent、风控 Agent和权限，但 MUST NOT创建外部客户演示账号、营销 Agent或外部演示 API Key。

production seed MUST NOT在标准输出打印默认密码、原始 API Key、Dify Key、数据库连接串或对象存储密钥。

#### Scenario: external 数据库不产生 internal 资源

- **WHEN** 在 external配置下对空数据库执行 external seed
- **THEN** 营销 Agent和外部演示资源被幂等创建，合同审查/风控 Agent及内部业务部门不存在

#### Scenario: internal 数据库不产生 external 演示资源

- **WHEN** 在 internal配置下对空数据库执行 internal seed
- **THEN** 内部管理员、部门、合同审查和风控 Agent被幂等创建，外部客户演示账号、营销 Agent和外部演示 Key不存在

#### Scenario: seed profile不匹配被拒绝

- **WHEN** `DEPLOYMENT_PROFILE=internal` 的进程尝试执行 external seed，或反向组合
- **THEN** seed在创建任何组织、用户、Agent、Key或权限前失败并给出不含敏感值的配置错误

#### Scenario: production seed不回显秘密

- **WHEN** `ENVIRONMENT=production` 下完成任一 profile seed
- **THEN** 输出只包含资源标识、状态或 Key前缀，不包含密码和任何原始密钥

### Requirement: 两个实例保持依赖、数据库和外部凭证隔离

同机部署 MUST使用不同系统用户和独立 Python虚拟环境。两份 EnvironmentFile MUST由 root 保护，运行用户不得直接读取另一 profile 的配置。external运行环境 MUST只安装基础依赖且不得安装或导入 `pymupdf/fitz`；internal运行环境 MUST安装 `internal` optional dependencies以支持 PDF/DOCX和内部工作台能力。

两个实例 MUST使用不同数据库 schema和数据库账号、不同 API Key签名密钥与 Auth密钥、不同 Dify App/API Key、不同 MinIO service account及不同 raw/parsed bucket。即使 MySQL、Dify或MinIO共用物理宿主服务，上述账号和命名空间也不得复用。

#### Scenario: external 环境不含 internal解析依赖

- **WHEN** 对external虚拟环境执行依赖预检和启动冒烟
- **THEN** 基础营销服务可启动，`fitz`不可导入，external启动路径不因缺少internal依赖失败

#### Scenario: external 运行身份不能读取 internal 环境文件

- **WHEN** external backend以其systemd用户运行
- **THEN** 该用户不能读取 `/etc/agenthub/internal.env`，internal用户同样不能读取external环境文件

#### Scenario: internal 环境具备文档解析依赖

- **WHEN** 对internal虚拟环境执行依赖预检
- **THEN** `python-docx`和`pymupdf`可用，合同审查支持的DOCX与文本型PDF可进入现有解析链路

#### Scenario: 数据库或凭证复用时预检失败

- **WHEN** 两份环境配置使用相同数据库schema/账号、相同签名密钥、相同Dify Key、相同MinIO access key或相同bucket
- **THEN** 预检失败并报告发生复用的配置类别，不回显敏感值

### Requirement: internal入口默认拒绝非内网访问

双端口Nginx模板 SHALL将两个backend仅暴露在loopback，并为internal前端端口采用显式allowlist加默认拒绝策略。未填写任何允许的公司内网/VPN CIDR时，internal入口的部署预检 MUST失败；external入口的开放范围由试用部署配置决定，但不得因此代理到internal backend。

无域名HTTP模式 SHALL只被文档化为受控内网/VPN试用能力。真实外部用户或未经脱敏的高敏合同/单据投入使用前 MUST启用HTTPS，或迁移到满足ADR-015的正式隔离入口。MinIO预签名上传CORS MUST精确允许包含端口的internal前端origin。

#### Scenario: 非允许来源不能访问internal入口

- **WHEN** 客户端来源不匹配internal Nginx allowlist
- **THEN** Nginx在请求到达Vue静态页面或FastAPI backend前拒绝访问

#### Scenario: backend端口不对网络直接开放

- **WHEN** 其它机器尝试直接访问8240或8241 backend端口
- **THEN** 连接失败，只有本机Nginx可经loopback访问对应backend

#### Scenario: MinIO允许带端口的internal origin上传

- **WHEN** internal用户从配置的IP端口获取并使用预签名PUT URL
- **THEN** MinIO CORS允许所需的PUT/OPTIONS与Content-Type，且浏览器不携带AgentHub Cookie或Authorization

### Requirement: 双实例部署具备可重复预检、简化发布、验收和整体回滚能力

仓库 SHALL提供external/internal部署模板和single-host runbook，覆盖环境文件权限、虚拟环境、双前端构建、两次migration、两次profile seed、systemd、Nginx、日志、备份、健康检查、smoke test及拆分迁移步骤。预检 MUST对敏感配置执行缺失、占位符和跨profile相等性检查，但不得输出原始值。

两个服务 MUST可分别启动、停止和重启。试用阶段代码发布和回滚 SHALL使用同一 Git checkout整体执行，不要求维护profile独立release或软链接。验收 MUST验证两个健康检查、登录页品牌、路由边界、Cookie隔离、登录后跳转、营销问答、合同上传审查和风控工作台。

#### Scenario: 预检通过后才允许启动双实例

- **WHEN** 运维准备发布single-host配置
- **THEN** 配置、端口、Cookie、数据库、凭证、bucket、依赖、前端产物和internal allowlist全部通过检查后，runbook才进入migration和启动步骤

#### Scenario: 两个数据库分别迁移

- **WHEN** 发布流程执行Alembic migration
- **THEN** 同一migration链分别使用external和internal环境连接两个数据库完成升级，不把一个数据库URL复用于两次操作

#### Scenario: 使用已验证commit整体回滚

- **WHEN** 新版本构建、启动或smoke失败
- **THEN** 运维停止两个服务，将共享checkout切回已验证commit，重建两个venv和前端产物后整体启动，且不自动执行Alembic downgrade

#### Scenario: 达到退出条件后可迁移internal到独立主机

- **WHEN** 出现真实公网营销流量、高敏合同生产处理、合规主机隔离要求、资源争抢或独立发布需求
- **THEN** 运维可迁移internal运行环境、静态产物和入口配置到独立主机，同时保留既有internal数据库、Dify和MinIO命名空间以及业务API契约
