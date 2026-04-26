from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.behavior import router as behavior_router
from app.api.controlled_agents import router as controlled_agents_router
from app.api.metrics import router as metrics_router
from app.api.person_dataset import router as person_dataset_router
from app.api.persona import router as persona_router
from app.api.proxy import router as proxy_router
from app.api.simulation import router as simulation_router
from app.api.topics import router as topics_router
from app.core.config import get_settings
from app.core.dependencies import setup_dependencies

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动事件
    await setup_dependencies(app).startup_event()
    yield
    # 关闭事件
    await setup_dependencies(app).shutdown_event()


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Backend API for Socitwin social simulation platform with OASIS integration",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(simulation_router, prefix="/api")
app.include_router(topics_router, prefix="/api")
app.include_router(metrics_router, prefix="/api")
app.include_router(behavior_router, prefix="/api")
app.include_router(controlled_agents_router, prefix="/api")
app.include_router(persona_router, prefix="/api")
app.include_router(person_dataset_router, prefix="/api")
app.include_router(proxy_router)


@app.get("/")
async def root():
    return {
        "message": "Socitwin Backend API",
        "version": "1.0.0",
        "status": "running",
        "features": {
            "oasis_integration": True,
            "multi_agent_simulation": True,
            "social_platforms": ["twitter", "reddit"],
            "controlled_agents": True,
        },
        "docs": "/docs",
        "api": "/api"
    }


@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {
        "status": "healthy",
        "project": settings.PROJECT_NAME,
        "oasis_enabled": True,
        "environment": settings.ENVIRONMENT
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )
