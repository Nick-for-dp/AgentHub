## 1. 架构边界与部署契约

- [x] 1.1 在 `DECISIONS.md` ADR-015 中记录“试用期同机双实例”例外、仍须隔离的数据库/Dify/MinIO/Cookie边界、HTTP限制和正式分机退出条件。
- [x] 1.2 在 `Archi.md` 部署形态中补充同IP双端口拓扑、backend loopback端口、前端origin和后续迁移路径，确认不改变业务endpoint/service/repository/integration边界。
- [x] 1.3 固化external/internal部署目录、默认示例端口、静态产物目录、环境文件位置和日志标识约定，供后续脚本、systemd和Nginx模板共同引用。

## 2. 后端Cookie与profile配置隔离

- [x] 2.1 在 `Settings` 中实现profile-aware auth Cookie有效名称，保持external现有名称兼容，并为internal提供不冲突的安全默认值和空值校验。
- [x] 2.2 调整auth Cookie写入、探测、刷新、登出和删除路径，统一使用解析后的当前实例Cookie名称，避免写入与清理名称不一致。
- [x] 2.3 为embed Cookie补充同机冲突防护和internal默认关闭约束，确保显式启用时可配置独立名称且不放松既有issuer/audience/origin校验。
- [x] 2.4 在后端环境变量模板中补齐 `AUTH_COOKIE_NAME`、`AUTH_COOKIE_SECURE`、`AUTH_COOKIE_SAMESITE`、`AUTH_COOKIE_DOMAIN` 及双实例/IP访问说明。
- [x] 2.5 增加配置和安全单元测试，覆盖external/internal默认Cookie名称、显式覆盖、空名称拒绝、Set-Cookie/Delete-Cookie一致性、两个profile同时登录及一侧登出不影响另一侧。
- [x] 2.6 回归认证、手机号密码、Session刷新/过期和embed安全测试，确认Cookie隔离未改变现有认证与权限语义。

## 3. Profile-aware初始化

- [x] 3.1 为 `backend/scripts/seed.py` 增加external/internal参数解析，默认读取 `DEPLOYMENT_PROFILE`，并在参数与运行时profile不一致时于任何写库操作前失败。
- [x] 3.2 将现有seed重构为共享平台bootstrap helper、external初始化helper和internal初始化helper，保持service/repository调用和幂等语义。
- [x] 3.3 收敛external seed，只创建平台管理员、外部营销组织/用户、营销Agent、知识库、API Key和权限，不创建合同审查/风控Agent及内部业务部门。
- [x] 3.4 收敛internal seed，只创建内部公司/部门/管理员、合同审查Agent、风控Agent和权限，不创建外部演示用户、营销Agent或外部演示API Key。
- [x] 3.5 调整production seed输出，禁止打印密码、原始API Key、Dify Key、数据库URL和对象存储密钥，仅保留资源标识、状态与安全前缀。
- [x] 3.6 增加seed定向测试，覆盖两个profile首次初始化、重复执行幂等、profile不匹配fail closed、跨profile资源不存在及production输出脱敏。

## 4. 前端入口区分与双构建

- [x] 4.1 在deployment profile配置中新增external/internal产品展示元数据，集中维护登录页标题、用途说明和普通用户默认入口。
- [x] 4.2 改造 `LoginPage.vue`：external显示营销智能体入口，internal显示合同审查与风控入口；复用现有表单、认证、错误提示和管理员跳转。
- [x] 4.3 增加登录页和profile路由测试，覆盖两套品牌文案、external跳转 `/chat`、internal跳转 `/internal/contract-review`、管理员跳转管理端以及external不注册internal路由。
- [x] 4.4 为Vite增加可选构建输出目录配置，并补充 `build:external`、`build:internal`、`build:profiles` 或等价命令，使两套产物可连续生成且不互相清空。
- [x] 4.5 增加前端产物隔离检查，验证external构建不包含internal路由、导航、合同审查/风控页面chunk和内部工作台文案，internal构建包含预期入口。
- [x] 4.6 按UI规范检查external/internal登录页在1366×768和375×812视口下的品牌、表单、错误态和文本溢出，并保存验收记录。

## 5. 双实例部署脚手架

- [x] 5.1 新增 `deploy/profiles/external/` 与 `deploy/profiles/internal/` 环境变量模板，分别声明profile、端口、Cookie、数据库、Dify、MinIO、CORS、embed和日志配置，且不包含真实密钥。
- [x] 5.2 新增两套systemd unit，使用独立系统用户、EnvironmentFile、external/internal虚拟环境、不同loopback端口和日志标识，并允许单独启动、停止和重启。
- [x] 5.3 新增同IP双端口Nginx配置：两个独立upstream/server/static root，external与internal `/api`只代理对应backend，internal默认 `deny all` 并要求显式内网/VPN CIDR allowlist。
- [x] 5.4 保留SSE和blocking workflow所需的代理超时/禁用缓冲设置，确保营销流式问答、合同审查长请求和风控工作台在各自入口正常工作。
- [x] 5.5 新增双profile构建/安装脚本，在一份固定 Git checkout 上重建两个固定 venv 和两个前端 dist；external只安装基础依赖，internal安装internal extra，不维护版本化 release/软链接。
- [x] 5.6 新增按profile执行Alembic migration和seed的安全命令/脚本，显式加载目标EnvironmentFile并防止同一数据库URL被用于两次部署。
- [x] 5.7 新增无秘密双实例预检，检查profile、端口、Cookie、数据库schema/账号、签名/Auth/Dify/MinIO凭证复用、bucket命名空间、internal allowlist、embed开关、venv依赖和前端产物。
- [x] 5.8 为预检增加脱敏配置夹具测试，覆盖合法配置、端口/Cookie/数据库/密钥/bucket冲突、缺失allowlist、external含fitz、internal缺解析依赖，并断言输出不含原始敏感值。
- [x] 5.9 扩展logrotate、journald标识和备份说明，使external/internal日志与两个远端MySQL数据库备份可分别定位、保留和恢复。

## 6. 部署Runbook与验收自动化

- [x] 6.1 编写single-host双实例runbook，沿用原单实例“拉代码、配环境、构建、迁移、启动”顺序，覆盖固定目录、独立系统用户、远端MySQL双schema/账号、Dify/MinIO命名空间、防火墙和整体回滚。
- [x] 6.2 在runbook中明确无域名HTTP仅限可信内网/VPN、Cookie Secure切换、IP SAN HTTPS方案、MinIO带端口origin CORS和真实外部用户/高敏合同前的安全门槛。
- [x] 6.3 新增双实例smoke脚本，验证两个health、登录页品牌、external internal API为404、internal未登录API为401、Set-Cookie名称不同及静态产物版本信息。
- [x] 6.4 为smoke脚本增加可本地运行的fixture/测试，确保失败时返回非零状态且不打印密码、Cookie值、Authorization或API Key。
- [x] 6.5 使用 `nginx -t`、`systemd-analyze verify` 或目标系统等价检查验证两套模板语法、端口/upstream映射和internal allowlist默认拒绝行为。

## 7. 回归与人工试用验收

- [x] 7.1 运行后端配置、安全、认证、internal路由、seed及合同审查/风控相关定向测试，修复由profile隔离引入的回归。
- [x] 7.2 运行后端MySQL全量测试并确认本change不新增Alembic migration，现有migration链可分别升级external/internal测试库。
- [x] 7.3 运行前端全量Vitest、external/internal类型检查和生产构建，并执行产物隔离检查。
- [x] 7.4 在同一测试主机或等价环境启动两个backend和两个前端入口，验证同一浏览器可同时保持external/internal登录，任一侧登出或重启不影响另一侧。
- [ ] 7.5 完成external营销问答SSE人工验收，确认会话恢复、语音可选能力和调用记录仍写入external数据库。
- [ ] 7.6 完成internal合同审查人工验收，确认预签名上传、解析、Dify执行、规则判敏、原文高亮和调用记录只进入internal数据库/MinIO命名空间。
- [ ] 7.7 完成internal风控助手人工验收，确认多文件任务、人工复核和Excel导出只使用internal入口与资源。
- [ ] 7.8 从非allowlist来源验证internal端口被Nginx拒绝，并确认backend 8240/8241不能从其它机器直接访问。

## 8. 文档同步与OpenSpec收尾

- [x] 8.1 更新根 `README.md` 和 `docs/deployment.md`，补充单实例开发与同机双实例试用两种启动方式、配置矩阵和安全限制。
- [x] 8.2 更新 `PLAN-internal.md` I1/I8进度和剩余正式分机事项，避免把试用期同机部署误记为完成正式物理隔离。
- [x] 8.3 在 `CHANGELOG.md` 记录双实例部署、Cookie隔离、profile-aware seed、登录入口和验证结果。
- [x] 8.4 运行 `openspec validate add-single-host-dual-profile-deployment --strict`，修复proposal/design/spec/tasks一致性问题并确认change达到apply-ready。
