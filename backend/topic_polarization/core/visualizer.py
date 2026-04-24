import json
from core.config import OUTPUT_HTML

# 过滤类型与聚类名称/颜色的映射
FILTER_MAP = {
    "high": {"cluster": "高扩散（容易分化）", "color": "#e74c3c", "title": "高扩散话题分析"},
    "middle": {"cluster": "中等扩散", "color": "#f39c12", "title": "中等扩散话题分析"},
    "low": {"cluster": "低扩散（不易分化）", "color": "#27ae60", "title": "低扩散话题分析"},
}


def generate_html(topic_results, filter_type="all"):
    """
    生成 ECharts 图表页面

    参数:
        topic_results: 全部话题分析结果列表
        filter_type: 过滤类型
            - "all": 显示全部（默认，保留低扩散合并+展开功能）
            - "high": 只显示高扩散话题
            - "middle": 只显示中等扩散话题
            - "low": 只显示低扩散话题
    """
    if filter_type != "all":
        return _generate_filtered_html(topic_results, filter_type)

    # 1. 先按扩散指数排序
    sorted_topics = sorted(topic_results, key=lambda x: x["divergence_index"], reverse=True)

    # 2. 拆分：高扩散 + 中等扩散 = 正常显示；低扩散 = 合并成一组
    high_medium_topics = []
    low_diffusion_topics = []  # 低扩散话题集合（你要的数据集合）
    low_diffusion_labels = []
    low_diffusion_bar_data = []

    for t in sorted_topics:
        if t["cluster"] == "低扩散（不易分化）":
            low_diffusion_topics.append(t)  # 存入集合
            label = t["topic_label"] or t["topic_key"]
            low_diffusion_labels.append(label[:20] + "..." if len(label) > 20 else label)
            low_diffusion_bar_data.append({
                "value": round(t["divergence_index"], 4),
                "itemStyle": {"color": t["color"]},
                "topic_label": t["topic_label"] or t["topic_key"],
                "cluster": t["cluster"],
                "content_count": t["content_count"],
                "multi_topic_count": t["multi_topic_count"],
                "multi_topic_ratio": round(t["multi_topic_ratio"] * 100, 1),
                "unique_other_topics": t["unique_other_topics"],
                "avg_topics_per_content": round(t["avg_topics_per_content"], 2),
            })
        else:
            high_medium_topics.append(t)

    # 3. 构建主图表数据：高/中等 + 【低扩散合并项】
    main_labels = []
    main_bar_data = []

    # 高扩散 + 中等扩散
    for t in high_medium_topics:
        label = t["topic_label"] or t["topic_key"]
        main_labels.append(label[:20] + "..." if len(label) > 20 else label)
        main_bar_data.append({
            "value": round(t["divergence_index"], 4),
            "itemStyle": {"color": t["color"]},
            "topic_label": t["topic_label"] or t["topic_key"],
            "cluster": t["cluster"],
            "content_count": t["content_count"],
            "multi_topic_count": t["multi_topic_count"],
            "multi_topic_ratio": round(t["multi_topic_ratio"] * 100, 1),
            "unique_other_topics": t["unique_other_topics"],
            "avg_topics_per_content": round(t["avg_topics_per_content"], 2),
        })

    # 加入【可展开的低扩散合并柱】
    if low_diffusion_topics:
        main_labels.append("低扩散话题（点击展开）")
        main_bar_data.append({
            "value": 0,  # 占位值
            "itemStyle": {"color": "#27ae60"},
            "topic_label": "低扩散话题（点击展开）",
            "cluster": "低扩散（不易分化）",
            "content_count": sum(t["content_count"] for t in low_diffusion_topics),
            "multi_topic_count": sum(t["multi_topic_count"] for t in low_diffusion_topics),
            "multi_topic_ratio": round(
                sum(t["multi_topic_count"] for t in low_diffusion_topics)
                / max(sum(t["content_count"] for t in low_diffusion_topics), 1)
                * 100, 1
            ),
            "unique_other_topics": sum(t["unique_other_topics"] for t in low_diffusion_topics),
            "avg_topics_per_content": round(
                sum(t["avg_topics_per_content"] for t in low_diffusion_topics)
                / max(len(low_diffusion_topics), 1), 2
            ),
            "isLowDiffusionGroup": True  # 标记：这是可展开的合并组
        })

    # 4. 聚类统计（保持不变）
    cluster_names = ["高扩散（容易分化）", "中等扩散", "低扩散（不易分化）"]
    cluster_counts = {name: 0 for name in cluster_names}
    for t in sorted_topics:
        cluster_counts[t["cluster"]] += 1

    # 5. JSON 序列化
    main_labels_json = json.dumps(main_labels, ensure_ascii=False)
    main_bar_data_json = json.dumps(main_bar_data, ensure_ascii=False)
    low_labels_json = json.dumps(low_diffusion_labels, ensure_ascii=False)
    low_bar_data_json = json.dumps(low_diffusion_bar_data, ensure_ascii=False)
    cluster_labels_json = json.dumps(cluster_names, ensure_ascii=False)
    cluster_values_json = json.dumps([
        {"value": cluster_counts["高扩散（容易分化）"], "itemStyle": {"color": "#e74c3c"}},
        {"value": cluster_counts["中等扩散"], "itemStyle": {"color": "#f39c12"}},
        {"value": cluster_counts["低扩散（不易分化）"], "itemStyle": {"color": "#27ae60"}},
    ], ensure_ascii=False)

    # 6. 完整 HTML（增加展开/收起逻辑）
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>话题扩散聚类分析</title>
    <script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif;
            background: linear-gradient(135deg, #0c0e1a 0%, #151930 50%, #1a1f3a 100%);
            min-height: 100vh;
            padding: 40px 20px;
            color: #e0e0e0;
        }}
        .page-title {{
            text-align: center;
            font-size: 34px;
            font-weight: 700;
            color: #fff;
            margin-bottom: 10px;
            letter-spacing: 3px;
        }}
        .page-subtitle {{
            text-align: center;
            font-size: 14px;
            color: #7a8bb5;
            margin-bottom: 40px;
            line-height: 1.6;
        }}
        .chart-container {{
            max-width: 1200px;
            margin: 0 auto 40px;
            background: rgba(255,255,255,0.03);
            border: 1px solid rgba(255,255,255,0.07);
            border-radius: 16px;
            padding: 30px;
            backdrop-filter: blur(12px);
        }}
        .chart-title {{
            font-size: 20px;
            font-weight: 600;
            color: #fff;
            margin-bottom: 20px;
            padding-left: 14px;
            border-left: 4px solid #5b8def;
        }}
        #chart1 {{ width: 100%; height: 520px; }}
        #chart2 {{ width: 100%; height: 380px; }}
        .legend-bar {{
            display: flex;
            justify-content: center;
            gap: 32px;
            margin-bottom: 16px;
        }}
        .legend-item {{
            display: flex;
            align-items: center;
            gap: 7px;
            font-size: 13px;
            color: #b0b8d0;
        }}
        .legend-dot {{
            width: 12px;
            height: 12px;
            border-radius: 3px;
        }}
    </style>
</head>
<body>
    <div class="page-title">话题扩散聚类分析</div>
    <div class="page-subtitle">
        基于话题内容交叉关系 · 扩散指数 = 跨话题内容比例 × log<sub>2</sub>(1 + 涉及其他话题数)
    </div>

    <div class="chart-container">
        <div class="chart-title">所有话题的扩散指数</div>
        <div class="legend-bar">
            <div class="legend-item"><div class="legend-dot" style="background:#e74c3c"></div>高扩散（容易分化）</div>
            <div class="legend-item"><div class="legend-dot" style="background:#f39c12"></div>中等扩散</div>
            <div class="legend-item"><div class="legend-dot" style="background:#27ae60"></div>低扩散（不易分化）</div>
        </div>
        <div id="chart1"></div>
    </div>

    <div class="chart-container">
        <div class="chart-title">各聚类类别的话题数量</div>
        <div id="chart2"></div>
    </div>

    <script>
        var chart1 = echarts.init(document.getElementById('chart1'));
        var isLowExpanded = false; // 低扩散是否展开状态
        var mainLabels = {main_labels_json};
        var mainBarData = {main_bar_data_json};
        var lowLabels = {low_labels_json};
        var lowBarData = {low_bar_data_json};

        // 初始化渲染主数据
        renderChart(mainLabels, mainBarData);

        function renderChart(labels, data) {{
            chart1.setOption({{
                tooltip: {{
                    trigger: 'axis',
                    axisPointer: {{ type: 'shadow' }},
                    backgroundColor: 'rgba(15,18,35,0.95)',
                    borderColor: 'rgba(91,139,239,0.3)',
                    textStyle: {{ color: '#ddd', fontSize: 13 }},
                    formatter: function(params) {{
                        var d = data[params[0].dataIndex];
                        return '<b style="font-size:14px">' + d.topic_label + '</b><br/>'
                            + '<span style="color:#888">聚类类别：</span>' + d.cluster + '<br/>'
                            + '<span style="color:#888">扩散指数：</span><b style="color:#5b8def">' + d.value + '</b><br/>'
                            + '<span style="color:#888">内容总数：</span>' + d.content_count + '<br/>'
                            + '<span style="color:#888">跨话题内容数：</span>' + d.multi_topic_count + '<br/>'
                            + '<span style="color:#888">跨话题比例：</span>' + d.multi_topic_ratio + '%<br/>'
                            + '<span style="color:#888">涉及其他话题数：</span>' + d.unique_other_topics + '<br/>'
                            + '<span style="color:#888">平均关联话题数：</span>' + d.avg_topics_per_content;
                    }}
                }},
                grid: {{ left: 60, right: 30, bottom: 130, top: 20 }},
                xAxis: {{
                    type: 'category',
                    data: labels,
                    axisLabel: {{
                        rotate: 40,
                        color: '#8a95b5',
                        fontSize: 11,
                        interval: 0
                    }},
                    axisLine: {{ lineStyle: {{ color: '#2a3050' }} }},
                    axisTick: {{ lineStyle: {{ color: '#2a3050' }} }}
                }},
                yAxis: {{
                    type: 'value',
                    name: '扩散指数',
                    nameTextStyle: {{ color: '#8a95b5', fontSize: 13 }},
                    axisLabel: {{ color: '#8a95b5' }},
                    splitLine: {{ lineStyle: {{ color: 'rgba(255,255,255,0.05)' }} }},
                    axisLine: {{ lineStyle: {{ color: '#2a3050' }} }}
                }},
                series: [{{
                    type: 'bar',
                    data: data,
                    barMaxWidth: 38,
                    itemStyle: {{ borderRadius: [4, 4, 0, 0] }}
                }}]
            }}, true);
        }}

        // 点击事件：展开/收起低扩散
        chart1.on('click', function(params) {{
            var item = params.data;
            if (!item.isLowDiffusionGroup) return;

            isLowExpanded = !isLowExpanded;
            if (isLowExpanded) {{
                // 展开：替换为低扩散子列表
                var newLabels = mainLabels.slice(0, -1).concat(lowLabels);
                var newData = mainBarData.slice(0, -1).concat(lowBarData);
                renderChart(newLabels, newData);
            }} else {{
                // 收起：恢复合并状态
                renderChart(mainLabels, mainBarData);
            }}
        }});

        // 第二个图表不变
        var chart2 = echarts.init(document.getElementById('chart2'));
        var clusterLabels = {cluster_labels_json};
        var clusterValues = {cluster_values_json};

        chart2.setOption({{
            tooltip: {{
                trigger: 'axis',
                axisPointer: {{ type: 'shadow' }},
                backgroundColor: 'rgba(15,18,35,0.95)',
                borderColor: 'rgba(91,139,239,0.3)',
                textStyle: {{ color: '#ddd', fontSize: 13 }}
            }},
            grid: {{ left: 80, right: 80, bottom: 50, top: 20 }},
            xAxis: {{
                type: 'category',
                data: clusterLabels,
                axisLabel: {{ color: '#8a95b5', fontSize: 13 }},
                axisLine: {{ lineStyle: {{ color: '#2a3050' }} }},
                axisTick: {{ lineStyle: {{ color: '#2a3050' }} }}
            }},
            yAxis: {{
                type: 'value',
                name: '话题数量',
                nameTextStyle: {{ color: '#8a95b5', fontSize: 13 }},
                axisLabel: {{ color: '#8a95b5' }},
                splitLine: {{ lineStyle: {{ color: 'rgba(255,255,255,0.05)' }} }},
                axisLine: {{ lineStyle: {{ color: '#2a3050' }} }},
                minInterval: 1
            }},
            series: [{{
                type: 'bar',
                data: clusterValues,
                barWidth: 90,
                itemStyle: {{ borderRadius: [6, 6, 0, 0] }},
                label: {{
                    show: true,
                    position: 'top',
                    color: '#fff',
                    fontSize: 16,
                    fontWeight: 'bold'
                }}
            }}]
        }});

        window.addEventListener('resize', function() {{
            chart1.resize();
            chart2.resize();
        }});
    </script>
</body>
</html>"""
    return html, low_diffusion_topics  # 返回：html内容 + 低扩散话题集合


def _generate_filtered_html(topic_results, filter_type):
    """生成按类别过滤的 HTML 页面"""
    info = FILTER_MAP[filter_type]
    cluster_name = info["cluster"]
    color = info["color"]
    page_title = info["title"]

    # 筛选该类别话题并排序
    filtered = sorted(
        [t for t in topic_results if t["cluster"] == cluster_name],
        key=lambda x: x["divergence_index"],
        reverse=True
    )

    if not filtered:
        # 无数据时的友好提示页面
        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{page_title}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif;
            background: linear-gradient(135deg, #0c0e1a 0%, #151930 50%, #1a1f3a 100%);
            min-height: 100vh;
            padding: 40px 20px;
            color: #e0e0e0;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
        }}
        .empty-msg {{
            font-size: 24px;
            color: #7a8bb5;
            margin-bottom: 30px;
        }}
        .back-link {{
            color: #5b8def;
            text-decoration: none;
            font-size: 16px;
            border: 1px solid rgba(91,139,239,0.4);
            padding: 10px 24px;
            border-radius: 8px;
            transition: background 0.2s;
        }}
        .back-link:hover {{ background: rgba(91,139,239,0.1); }}
    </style>
</head>
<body>
    <div class="empty-msg">暂无{cluster_name}的话题数据</div>
    <a class="back-link" href="/chart">← 返回全部话题</a>
</body>
</html>"""
        return html

    # 构建图表数据
    labels = []
    bar_data = []
    for t in filtered:
        label = t["topic_label"] or t["topic_key"]
        labels.append(label[:20] + "..." if len(label) > 20 else label)
        bar_data.append({
            "value": round(t["divergence_index"], 4),
            "itemStyle": {"color": color},
            "topic_label": t["topic_label"] or t["topic_key"],
            "cluster": t["cluster"],
            "content_count": t["content_count"],
            "multi_topic_count": t["multi_topic_count"],
            "multi_topic_ratio": round(t["multi_topic_ratio"] * 100, 1),
            "unique_other_topics": t["unique_other_topics"],
            "avg_topics_per_content": round(t["avg_topics_per_content"], 2),
        })

    labels_json = json.dumps(labels, ensure_ascii=False)
    bar_data_json = json.dumps(bar_data, ensure_ascii=False)

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{page_title}</title>
    <script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif;
            background: linear-gradient(135deg, #0c0e1a 0%, #151930 50%, #1a1f3a 100%);
            min-height: 100vh;
            padding: 40px 20px;
            color: #e0e0e0;
        }}
        .page-title {{
            text-align: center;
            font-size: 34px;
            font-weight: 700;
            color: #fff;
            margin-bottom: 10px;
            letter-spacing: 3px;
        }}
        .page-subtitle {{
            text-align: center;
            font-size: 14px;
            color: #7a8bb5;
            margin-bottom: 40px;
            line-height: 1.6;
        }}
        .chart-container {{
            max-width: 1200px;
            margin: 0 auto 40px;
            background: rgba(255,255,255,0.03);
            border: 1px solid rgba(255,255,255,0.07);
            border-radius: 16px;
            padding: 30px;
            backdrop-filter: blur(12px);
        }}
        .chart-title {{
            font-size: 20px;
            font-weight: 600;
            color: #fff;
            margin-bottom: 20px;
            padding-left: 14px;
            border-left: 4px solid {color};
        }}
        #chart1 {{ width: 100%; height: 520px; }}
        .back-link {{
            display: block;
            text-align: center;
            margin-bottom: 30px;
            color: #5b8def;
            text-decoration: none;
            font-size: 15px;
        }}
        .back-link:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    <div class="page-title">{page_title}</div>
    <div class="page-subtitle">
        共 {len(filtered)} 个话题 · 类别：{cluster_name}
    </div>
    <a class="back-link" href="/chart">← 返回全部话题</a>

    <div class="chart-container">
        <div class="chart-title">{cluster_name} - 扩散指数</div>
        <div id="chart1"></div>
    </div>

    <script>
        var chart1 = echarts.init(document.getElementById('chart1'));
        var labels = {labels_json};
        var barData = {bar_data_json};

        chart1.setOption({{
            tooltip: {{
                trigger: 'axis',
                axisPointer: {{ type: 'shadow' }},
                backgroundColor: 'rgba(15,18,35,0.95)',
                borderColor: 'rgba(91,139,239,0.3)',
                textStyle: {{ color: '#ddd', fontSize: 13 }},
                formatter: function(params) {{
                    var d = barData[params[0].dataIndex];
                    return '<b style="font-size:14px">' + d.topic_label + '</b><br/>'
                        + '<span style="color:#888">聚类类别：</span>' + d.cluster + '<br/>'
                        + '<span style="color:#888">扩散指数：</span><b style="color:#5b8def">' + d.value + '</b><br/>'
                        + '<span style="color:#888">内容总数：</span>' + d.content_count + '<br/>'
                        + '<span style="color:#888">跨话题内容数：</span>' + d.multi_topic_count + '<br/>'
                        + '<span style="color:#888">跨话题比例：</span>' + d.multi_topic_ratio + '%<br/>'
                        + '<span style="color:#888">涉及其他话题数：</span>' + d.unique_other_topics + '<br/>'
                        + '<span style="color:#888">平均关联话题数：</span>' + d.avg_topics_per_content;
                }}
            }},
            grid: {{ left: 60, right: 30, bottom: 130, top: 20 }},
            xAxis: {{
                type: 'category',
                data: labels,
                axisLabel: {{
                    rotate: 40,
                    color: '#8a95b5',
                    fontSize: 11,
                    interval: 0
                }},
                axisLine: {{ lineStyle: {{ color: '#2a3050' }} }},
                axisTick: {{ lineStyle: {{ color: '#2a3050' }} }}
            }},
            yAxis: {{
                type: 'value',
                name: '扩散指数',
                nameTextStyle: {{ color: '#8a95b5', fontSize: 13 }},
                axisLabel: {{ color: '#8a95b5' }},
                splitLine: {{ lineStyle: {{ color: 'rgba(255,255,255,0.05)' }} }},
                axisLine: {{ lineStyle: {{ color: '#2a3050' }} }}
            }},
            series: [{{
                type: 'bar',
                data: barData,
                barMaxWidth: 38,
                itemStyle: {{ borderRadius: [4, 4, 0, 0] }}
            }}]
        }});

        window.addEventListener('resize', function() {{
            chart1.resize();
        }});
    </script>
</body>
</html>"""
    return html


def save_html_file(content: str):
    """保存 HTML 到文件"""
    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(content)