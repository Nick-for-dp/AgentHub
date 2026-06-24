from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    allowed_origins = settings.embed_allowed_parent_origin_list

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
    )
    if allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=allowed_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    @app.middleware("http")
    async def add_security_headers(request, call_next):
        response = await call_next(request)
        # frame-ancestors：默认 'none' 拒绝任何 iframe 嵌入；只有显式配置 origin
        # 白名单时才放行对应域名。这样即使误关 EMBED_ENABLED，也不会被任意站点
        # 套进 iframe 做点击劫持（clickjacking）。
        if allowed_origins:
            response.headers["Content-Security-Policy"] = (
                "frame-ancestors " + " ".join(allowed_origins)
            )
        else:
            response.headers["Content-Security-Policy"] = "frame-ancestors 'none'"
        # 防 MIME 嗅探：HTTP 模式下中间人可篡改 Content-Type，此头强制浏览器
        # 按声明类型解析响应，避免被诱导执行成脚本。
        response.headers["X-Content-Type-Options"] = "nosniff"
        # 跨站跳转时只携带 origin，不暴露完整 URL 中可能包含的敏感参数。
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

    @app.get("/health", tags=["system"])
    async def health_check() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
