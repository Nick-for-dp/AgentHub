## 1. 最小文件解析增强

- [x] 1.1 在 `backend/app/integrations/file_reader/pdf_reader.py` 增加低文本/扫描水印判断和 `SCANNED_TEXT_UNAVAILABLE` warning；用空页、水印页、正常文本页测试
- [x] 1.2 新建 `backend/app/integrations/file_reader/image_reader.py`，为 PNG/JPG 输出基础 ParsedDocumentV1 和 `IMAGE_REQUIRES_EXTRACTION` warning；在 `test_image_reader.py` 验证 metadata
- [x] 1.3 修改 `backend/app/integrations/file_reader/factory.py` 和 `modules/file_parse/service.py` 支持 png/jpg；测试 internal 接受图片、external 不加载模型依赖
- [x] 1.4 在 `backend/app/integrations/file_reader/docx_table.py` 实现合并单元格去重，并让 `DocxReader` 使用该 helper
- [x] 1.5 在 `test_docx_reader.py` 用普通非修订审批表验证段落/表格顺序和“业务模式简介”只出现一次
- [x] 1.6 运行合同审查 ParsedDocument 回归测试，确认顶层 `metadata/blocks/sections/warnings` 和全文输入不变

## 2. 极简抽取契约与 provider 选型

- [x] 2.1 新建 `backend/app/modules/risk_assessment/extraction/schemas.py`，只定义 `DocumentType`、`FieldStatus`、`ExtractedField` 和 `DocumentExtractionResult`
- [x] 2.2 新建 `test_risk_extraction_schemas.py`，验证 FOUND 必须有来源、MISSING 无默认值、UNCERTAIN 可携带 alternatives 和版本序列化
- [x] 2.3 在 `backend/app/modules/risk_assessment/extraction/ports.py` 定义单一 `DocumentExtractionProvider.extract()` Protocol，并用 fake provider 验证输入/输出
- [x] 2.4 将通用 provider 配置细化为 PaddleOCR/Qwen 独立配置：在 `Settings`、`.env` 和 `.env.example` 增加 cloud-egress 开关、PaddleOCR job URL/token/model、Qwen base URL/key/model/input mode；密钥使用 `SecretStr`，配置不依赖全局 deployment profile，测试未启用出网和缺少任一密钥时均 fail closed
- [x] 2.5 使用非 production spike 入口对采购合同、销售合同和结算单调用 PaddleOCR-VL-1.6：multipart 上传、有界轮询、JSONL 下载，验证页数/页序、表格数字、Pxxx-Bxxx 稳定锚点、quote 和 bbox；审批表记录 DOCX 原生解析基线
- [x] 2.6 使用 Qwen3.7-Plus 对四类样本比较 `ocr_text` 与 `image_and_ocr`：每份文档单次 Qwen 调用、JSON Mode、`enable_thinking=false`，记录关键字段正确率、source ID/quote 回映率、耗时、Token/成本和图片大小限制
- [x] 2.7 在 `backend/app/core/config.py` 增加惰性 provider 配置和 fail-closed factory；测试任意 deployment profile 导入时不主动初始化 provider、日志/repr 不泄漏密钥
- [x] 2.8 根据 2.5/2.6 更新 `docs/risk-assistant/document-ai-spike.md` 和 `DECISIONS.md` ADR-016，确认 production input mode、两家云平台的数据/日志留存边界、配额、超时及回滚开关
- [x] 2.9 仅在 2.8 完成后，在 `backend/app/integrations/document_extraction/` 实现异步 PaddleOCR client：multipart job、总超时/退避、终态处理、JSONL 大小限制、HTTPS/结果主机白名单和不记录 token/签名 URL
- [x] 2.10 仅在 2.8 完成后实现异步 Qwen client：只发送带稳定锚点的 OCR/ParsedDocument 文本，使用 JSON Mode、关闭思考模式、每份文档一次调用和响应结构校验；production 拒绝 `image_and_ocr`
- [x] 2.11 实现 `PaddleOcrQwenDocumentExtractionProvider`：扫描件走 PaddleOCR→Qwen，DOCX 跳过 OCR；Qwen 只返回 value/quote/source_ids，adapter 映射到 PaddleOCR page/bbox，缺失锚点、quote 不匹配或数值冲突统一输出 UNCERTAIN
- [x] 2.12 增加 provider contract/security tests：每份文档最多一次 Qwen、production 不上传 Qwen 图片、Qwen bbox 被忽略、未知 source ID/quote 与 raw value 均不匹配/轮询超时/恶意结果 URL 失败、未授权或 external visibility Agent 不能调用、结果和日志不包含 API key、base64、原始响应或签名 URL

## 3. 四类专用 extractor

- [x] 3.1 新建 `backend/app/modules/risk_assessment/extraction/base.py` 和 `registry.py`，按调用方声明的 DocumentType 直接选择 extractor
- [x] 3.2 在 registry 测试中验证缺少声明类型直接失败、四类 extractor 不自动互相切换、每次选择返回新实例
- [x] 3.3 新建 `extractors/purchase_contract.py`，用 fake provider 验证供应商、合同号、日期、货物、数量、单价、金额、优惠和保证金字段
- [x] 3.4 新建 `extractors/sales_contract.py`，验证下游客户、合同号、日期、交货地点、数量、单价和金额字段
- [x] 3.5 新建 `extractors/approval_form.py`，只抽取业务模式原文、上游/下游原文和审批表量化字段
- [x] 3.6 新建 `extractors/settlement_statement.py`，验证浮动费、占用天数、结算数量/金额和补款字段
- [x] 3.7 为四个 extractor 增加声明类型一致性检查；明显不符时输出 `DOCUMENT_TYPE_SUSPECTED` 且不切换 extractor
- [x] 3.8 增加参数化测试，证明四类 extractor 使用独立 schema/prompt、每份文档最多调用一次 provider

## 4. 极简抽取 service

- [x] 4.1 新建 `backend/app/modules/risk_assessment/extraction/service.py`，输入 file_parse_task、declared_document_type 和 provider，加载 ParsedDocument/source_uri 后调用专用 extractor
- [x] 4.2 在 `service.py` 内实现最小字段归一化和来源校验；不创建 route、perception、candidate、fact 或 validation 中间对象
- [x] 4.3 实现 FOUND/MISSING/UNCERTAIN 组装规则，并测试冲突、低置信度、证据不足统一进入 UNCERTAIN
- [x] 4.4 确保 `DocumentExtractionResult` 不包含 provider 原始响应、base64、密钥或模型推理文本
- [x] 4.5 增加测试证明 `FileParseService` 不调用模型；真实 provider 只由第二阶段风险任务 handler 在 invocation 生命周期内调用

## 5. 集成回归与完成门禁

- [x] 5.1 新建 `backend/app/tests/unit/test_risk_document_extraction.py`，用 fake provider 验证四类 DocumentExtractionResult
- [x] 5.2 新建 `backend/app/tests/integration/test_risk_sample_file_package.py`，对脱敏四文件包执行 parse→declared extractor→result
- [x] 5.3 增加 MISSING、UNCERTAIN、声明类型疑似错误和来源缺失回归用例
- [x] 5.4 运行 `uv run pytest app/tests/unit/test_docx_reader.py app/tests/unit/test_file_parse_service.py app/tests/unit/test_risk_document_extraction.py`
- [x] 5.5 更新 `Archi.md` 的极简数据流和三个核心对象，更新 `PLAN-internal.md` I3/I7、`CHANGELOG.md`
- [x] 5.6 运行 `openspec validate add-risk-document-extraction-foundation --type change --strict`、后端全量测试和 external profile import smoke test
- [x] 5.7 production adapter 完成后重新运行 provider contract tests、四样本受控 smoke、OpenSpec strict validation、后端全量测试和 external profile import smoke test
