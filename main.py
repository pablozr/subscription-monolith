from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.middleware.cors import CORSMiddleware
from core.postgresql.postgresql import postgresql
from core.redis.redis import redis_cache
from core.rabbitmq.rabbitmq import rabbitmq
from core.logger.logger import logger
from core.config.config import settings
from routes.auth.router import router as auth_router
from routes.users.router import router as users_router
from routes.subscription.router import router as subscription_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Iniciando conexões...")
    await postgresql.connect()
    await redis_cache.connect()
    await rabbitmq.connect()
    logger.info("Todos os serviços conectados com sucesso!")

    yield

    logger.info("Encerrando conexões...")
    await postgresql.disconnect()
    await redis_cache.disconnect()
    await rabbitmq.disconnect()
    logger.info("Todos os serviços desconectados com sucesso!")

app = FastAPI(lifespan=lifespan, openapi_url="/api/v1/subreminders/openapi.json")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/v1/subreminders/docs", include_in_schema=False)
async def custom_docs():
    return get_swagger_ui_html(
        openapi_url="/api/v1/subreminders/openapi.json",
        title="Documentação da API - SubReminders",
    )

app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(users_router, prefix="/users", tags=["users"])
app.include_router(subscription_router, prefix="/subscriptions", tags=["subscriptions"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.API_PORT)
