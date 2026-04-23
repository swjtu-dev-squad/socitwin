from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
import os

# 导入核心模块
from core.config import OUTPUT_HTML, OUTPUT_DIR
from core.database import get_db_connection, load_topics
from core.analyzer import compute_divergence, cluster_topics
from core.visualizer import generate_html, save_html_file

# FastAPI 应用
app = FastAPI(
    title="话题扩散聚类分析 API",
    description="基于话题内容交叉关系的扩散指数计算 + ECharts 可视化",
    version="1.0.0"
)

# 挂载静态文件目录（用于访问生成的 HTML）
app.mount("/output", StaticFiles(directory=OUTPUT_DIR), name="output")

# --------------------- API 接口 ---------------------
@app.get("/", summary="首页")
def home():
    return {"message": "话题扩散聚类分析服务运行中", "docs": "/docs"}

@app.get("/api/analyze", summary="执行全量话题分析并生成图表")
def run_full_analysis():
    try:
        # 1. 连接数据库
        conn = get_db_connection()
        topics = load_topics(conn)

        if not topics:
            return JSONResponse(status_code=404, content={"error": "无话题数据"})

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

@app.get("/chart", summary="直接查看可视化图表")
def show_chart():
    if not os.path.exists(OUTPUT_HTML):
        raise HTTPException(status_code=404, detail="图表未生成，请先访问 /api/analyze")
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


@app.get("/chart/high", response_class=HTMLResponse, summary="查看高扩散话题图表")
async def chart_high():
    try:
        topic_results = _get_analyzed_results()
        html = generate_html(topic_results, filter_type="high")
        return HTMLResponse(content=html)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"分析失败：{str(e)}")


@app.get("/chart/middle", response_class=HTMLResponse, summary="查看中等扩散话题图表")
async def chart_middle():
    try:
        topic_results = _get_analyzed_results()
        html = generate_html(topic_results, filter_type="middle")
        return HTMLResponse(content=html)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"分析失败：{str(e)}")


@app.get("/chart/low", response_class=HTMLResponse, summary="查看低扩散话题图表")
async def chart_low():
    try:
        topic_results = _get_analyzed_results()
        html = generate_html(topic_results, filter_type="low")
        return HTMLResponse(content=html)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"分析失败：{str(e)}")