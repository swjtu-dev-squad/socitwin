from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.controlled_agents import router as controlled_agents_router
from app.api.metrics import router as metrics_router
from app.api.person_dataset import router as person_dataset_router
from app.api.persona import router as persona_router
from app.api.simulation import router as simulation_router
from app.api.topics import router as topics_router
from app.core.config import get_settings
from app.core.dependencies import setup_dependencies

#from topic_polarization.core.analyzer import start_analysis
#from topic_polarization.core.visualizer import generate_chart

# --------------- 新增：话题极化模块依赖 ---------------
from fastapi import HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
import os

# 导入你的模块核心功能
from topic_polarization.core.config import OUTPUT_HTML, OUTPUT_DIR
from topic_polarization.core.database import get_db_connection, load_topics
from topic_polarization.core.analyzer import compute_divergence, cluster_topics
from topic_polarization.core.visualizer import generate_html, save_html_file

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
app.include_router(controlled_agents_router, prefix="/api")
app.include_router(persona_router, prefix="/api")
app.include_router(person_dataset_router, prefix="/api")


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

# ==============================================================================
# 新增：话题情感极化分析接口（整合到主项目）
# ==============================================================================
@app.get("/api/topic-polar/analyze", summary="执行全量话题分析并生成图表")
def run_full_analysis():
    try:
        # 1. 连接数据库
        conn = get_db_connection()
        topics = load_topics(conn)

        if not topics:
            return {"status": "error", "detail": "无话题数据"}

        # 2. 计算每个话题扩散指数
        topic_results = []
        for topic in topics:
            metrics = compute_divergence(conn, topic["platform"], topic["topic_key"])
            topic_results.append({
                "topic_label": topic["topic_label"] or topic["topic_key"],
                "topic_key": topic["topic_key"],
                "platform": topic["platform"],
                **metrics
            })

        # 3. 聚类
        topic_results = cluster_topics(topic_results)

        # 4. 生成并保存图表
        html_content, _ = generate_html(topic_results)
        save_html_file(html_content)

        conn.close()

        return {
            "status": "success",
            "total_topics": len(topic_results),
            "chart_url": "/output/topic_polarization_chart.html",
            "data": topic_results
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"分析失败：{str(e)}")


@app.get("/api/topic-polar/chart", summary="直接查看可视化图表")
def show_chart():
    if not os.path.exists(OUTPUT_HTML):
        raise HTTPException(status_code=404, detail="图表未生成，请先访问 /api/topic-polar/analyze")
    return FileResponse(OUTPUT_HTML)


def _get_analyzed_results():
    """公共函数：获取数据并分析，返回聚类后的 topic_results"""
    conn = get_db_connection()
    topics = load_topics(conn)
    if not topics:
        conn.close()
        return []
    topic_results = []
    for topic in topics:
        metrics = compute_divergence(conn, topic["platform"], topic["topic_key"])
        topic_results.append({
            "topic_label": topic["topic_label"] or topic["topic_key"],
            "topic_key": topic["topic_key"],
            "platform": topic["platform"],
            **metrics
        })
    topic_results = cluster_topics(topic_results)
    conn.close()
    return topic_results


@app.get("/api/topic-polar/chart/high", response_class=HTMLResponse, summary="查看高扩散话题图表")
async def chart_high():
    try:
        topic_results = _get_analyzed_results()
        html = generate_html(topic_results, filter_type="high")
        return HTMLResponse(content=html)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"分析失败：{str(e)}")


@app.get("/api/topic-polar/chart/middle", response_class=HTMLResponse, summary="查看中等扩散话题图表")
async def chart_middle():
    try:
        topic_results = _get_analyzed_results()
        html = generate_html(topic_results, filter_type="middle")
        return HTMLResponse(content=html)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"分析失败：{str(e)}")


@app.get("/api/topic-polar/chart/low", response_class=HTMLResponse, summary="查看低扩散话题图表")
async def chart_low():
    try:
        topic_results = _get_analyzed_results()
        html = generate_html(topic_results, filter_type="low")
        return HTMLResponse(content=html)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"分析失败：{str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )
