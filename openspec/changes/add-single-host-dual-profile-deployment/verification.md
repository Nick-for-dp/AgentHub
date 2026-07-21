## 实施验证记录

验证日期：2026-07-21

### 后端

- Unit 定向回归：485 passed、1 skipped；两个受 Windows 用户临时目录权限影响的 `tmp_path` 用例改用项目内 basetemp 后 3/3 passed。
- MySQL 全量：488 passed、1 skipped（217.80s）。
- migration：未新增 version migration；临时创建 external/internal 两个 MySQL schema，分别以对应 `DEPLOYMENT_PROFILE` 执行 `alembic upgrade head`，均到达 `f93a61d7c402`，随后删除临时 schema。
- migration 验证发现并修复 URL 编码密码含 `%` 时 Alembic `ConfigParser` 插值失败的问题；运行时 URL 写入配置前将 `%` 转义为 `%%`。

### 前端

- Vitest：9 files、34 tests passed。
- `npm run build:profiles`：external/internal 均构建成功。
- `npm run check:profile-builds`：通过；external 不含 internal 路由、文案或页面 chunk。
- UI：external/internal 在 1366×768、375×812 及移动端错误态均通过，详见 `ui-review.md`。

### 部署工具

- preflight 回归：11 tests passed，覆盖合法配置及端口/Cookie/数据库/密钥/bucket/allowlist/依赖冲突与输出脱敏。
- smoke fixture：2 tests passed，成功路径返回 0，失败路径返回非零且不输出密码、Cookie 值、Authorization 或 API Key。
- 模板语义：5 tests passed，确认 systemd/Nginx 端口、upstream、static root、allowlist 默认拒绝、SSE/长请求参数。
- `systemd-analyze verify`：两套 unit 通过；仅出现 WSL 自带 snapd unit 的无关版本警告。
- `nginx -t`：使用临时解压的 Ubuntu nginx-core 对配置执行真实语法检查，结果 successful。

### 本地等价双实例

`deploy/verification/local_dual_instance.py` 临时创建两个 MySQL schema，分别 migration+profile seed，启动 8240/8241 两个 FastAPI 与 8080/8081 两个 Vite 入口，并用同一 CookieJar 模拟同一浏览器：

- 同时保留 `agenthub_session` 与 `agenthub_internal_session`；
- 两个入口的 session 均有效；
- external 登出后 internal session 仍有效；
- internal backend 停止/重启期间 external health/session 不受影响；
- internal session 在 backend 重启后仍有效；
- 结束后停止全部临时进程并删除两个临时 schema。

### 仍需目标环境完成

真实 external 营销问答/Dify SSE、internal 合同审查 MinIO+Dify、风控助手业务流以及非 allowlist 网络来源拒绝，需要目标服务器及其 Dify、MinIO、网络策略和试用账号，当前本地环境不能替代，故任务 7.5–7.8 保持未完成。
