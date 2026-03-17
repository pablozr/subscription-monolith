from contextlib import asynccontextmanager
from fastapi.openapi.docs import get_swagger_ui_html
from core.postgresql.postgresql import postgresql
from core.redis.redis import redis_cache
from core.rabbitmq.rabbitmq import rabbitmq
from fastapi import FastAPI
# from fastapi.middleware.cors import CORSMiddleware

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Iniciando conexões...")
    await postgresql.connect()
    await redis_cache.connect()
    await rabbitmq.connect()
    print("✅ Todos os serviços conectados com sucesso!")

    yield

    print("Encerrando conexões...")
    await postgresql.disconnect()
    await redis_cache.disconnect()
    await rabbitmq.disconnect()
    print("✅ Todos os serviços desconectados com sucesso!")

app = FastAPI(lifespan=lifespan, openapi_url="/api/v1/subreminders/openapi.json", root_path="/api/v1/subreminders")

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["http://localhost:4200", "*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

@app.get("/api/v1/subreminders/docs", include_in_schema=False)
async def custom_docs():
    return get_swagger_ui_html(
        openapi_url="/api/v1/master/openapi.json",
        title="Documentação da API - Master",
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5685)