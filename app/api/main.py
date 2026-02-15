from fastapi import FastAPI

from app.api.dependencies import close_publisher, init_publisher


def create_app() -> FastAPI:
    app = FastAPI(
        title="Crosstalk Network Builder API",
        version="0.1.0",
    )

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    # Routes
    from app.api.routes.messages import router as messages_router
    from app.api.routes.centroids import router as centroids_router
    app.include_router(messages_router)
    app.include_router(centroids_router)

    @app.on_event("startup")
    async def startup():
        await init_publisher()

    @app.on_event("shutdown")
    async def shutdown():
        await close_publisher()

    return app


app = create_app()
