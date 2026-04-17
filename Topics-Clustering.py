"""
话题扩散聚类分析程序
基于话题之间的内容交叉关系，计算每个话题的"扩散指数"（divergence_index），
判断话题是否容易分化成其他话题，并生成 ECharts 可视化图表。

核心思路：如果一个话题下的内容同时也属于很多其他话题，说明这个话题容易发散/分化。
不使用任何情感分析，纯粹基于话题关联关系。
"""

import sqlite3
import os
import json
import math

# ======================== 配置 ========================
DB_PATH = r"e:\MyProject\公司的工作\人工智能\Mission\topic_polarization\oasis_datasets.db"
OUTPUT_DIR = r"e:\MyProject\公司的工作\人工智能\Mission\topic_polarization\Output"
OUTPUT_HTML = os.path.join(OUTPUT_DIR, "topic_polarization_chart.html")


# ======================== 数据读取 ========================
def load_topics(conn):
    """从 topics 表读取所有话题"""
    cursor = conn.execute(
        "SELECT platform, topic_key, topic_label, post_count, reply_count, user_count FROM topics"
    )
    topics = []
    for row in cursor.fetchall():
        topics.append({
            "platform": row[0],
            "topic_key": row[1],
            "topic_label": row[2],
            "post_count": row[3] or 0,
            "reply_count": row[4] or 0,
            "user_count": row[5] or 0,
        })
    return topics


# ======================== 话题扩散指数计算 ========================
def compute_divergence(conn, platform, topic_key):
    """
    计算某个话题的扩散指数。

    步骤：
    1. 获取该话题下所有关联内容
    2. 对每条内容，查看它还关联了哪些其他话题
    3. 统计跨话题内容数量、涉及的其他话题集合、每条内容的平均话题数
    4. divergence_index = multi_topic_ratio * log2(1 + unique_other_topics)
    """
    # 获取话题 T 下的所有内容 ID
    cursor = conn.execute(
        "SELECT external_content_id FROM content_topics WHERE topic_key = ? AND platform = ?",
        (topic_key, platform)
    )
    content_ids = [row[0] for row in cursor.fetchall()]
    content_count = len(content_ids)

    # 边界情况：话题没有任何关联内容
    if content_count == 0:
        return {
            "content_count": 0,
            "multi_topic_count": 0,
            "multi_topic_ratio": 0.0,
            "unique_other_topics": 0,
            "avg_topics_per_content": 0.0,
            "divergence_index": 0.0,
        }

    # 一次性联查：获取话题 T 的内容关联的所有其他话题及对应内容数
    cursor = conn.execute(
        """
        SELECT ct2.topic_key, COUNT(DISTINCT ct1.external_content_id)
        FROM content_topics ct1
        JOIN content_topics ct2
          ON ct1.platform = ct2.platform
          AND ct1.external_content_id = ct2.external_content_id
        WHERE ct1.topic_key = ? AND ct1.platform = ?
          AND ct2.topic_key != ct1.topic_key
        GROUP BY ct2.topic_key
        """,
        (topic_key, platform)
    )
    other_topic_rows = cursor.fetchall()

    # 涉及的其他不同话题数量
    unique_other_topics = len(other_topic_rows)

    # 收集所有"同时属于其他话题"的内容 ID（去重）
    # 用联查方式获取跨话题的内容 ID 集合
    cursor = conn.execute(
        """
        SELECT DISTINCT ct1.external_content_id
        FROM content_topics ct1
        JOIN content_topics ct2
          ON ct1.platform = ct2.platform
          AND ct1.external_content_id = ct2.external_content_id
        WHERE ct1.topic_key = ? AND ct1.platform = ?
          AND ct2.topic_key != ct1.topic_key
        """,
        (topic_key, platform)
    )
    multi_topic_content_ids = set(row[0] for row in cursor.fetchall())
    multi_topic_count = len(multi_topic_content_ids)

    # 跨话题内容比例
    multi_topic_ratio = multi_topic_count / content_count

    # 计算每条内容平均关联的话题数（包括 T 本身）
    cursor = conn.execute(
        """
        SELECT ct1.external_content_id, COUNT(ct2.topic_key) as topic_cnt
        FROM content_topics ct1
        JOIN content_topics ct2
          ON ct1.platform = ct2.platform
          AND ct1.external_content_id = ct2.external_content_id
        WHERE ct1.topic_key = ? AND ct1.platform = ?
        GROUP BY ct1.external_content_id
        """,
        (topic_key, platform)
    )
    topic_counts = [row[1] for row in cursor.fetchall()]
    avg_topics_per_content = sum(topic_counts) / len(topic_counts) if topic_counts else 1.0

    # 扩散指数 = 跨话题比例 × log2(1 + 涉及的其他话题数)
    divergence_index = multi_topic_ratio * math.log2(1 + unique_other_topics)

    return {
        "content_count": content_count,
        "multi_topic_count": multi_topic_count,
        "multi_topic_ratio": multi_topic_ratio,
        "unique_other_topics": unique_other_topics,
        "avg_topics_per_content": avg_topics_per_content,
        "divergence_index": divergence_index,
    }


# ======================== 聚类 ========================
def cluster_topics(topic_results):
    """
    根据扩散指数数值将话题分为3类：
    - 高扩散（容易分化）：divergence_index > 0.1，红色
    - 中等扩散：0 < divergence_index <= 0.1，橙色
    - 低扩散（不易分化）：divergence_index = 0，绿色
    """
    # 注意：这里不再需要排序，因为分类是基于数值而非排名
    for topic in topic_results:
        di = topic["divergence_index"]

        if di > 0.1:
            topic["cluster"] = "高扩散（容易分化）"
            topic["color"] = "#e74c3c"
        elif di > 0 and di < 0.1 or di == 0.1:  # 即 0 < di <= 0.1
            topic["cluster"] = "中等扩散"
            topic["color"] = "#f39c12"
        else:  # di == 0
            topic["cluster"] = "低扩散（不易分化）"
            topic["color"] = "#27ae60"

    # 返回结果（保持原样，不排序）
    return topic_results

# ======================== ECharts HTML 生成 ========================
def generate_html(topic_results):
    """生成包含两个 ECharts 图表的 HTML 页面"""

    # 按扩散指数降序排列
    sorted_topics = sorted(topic_results, key=lambda x: x["divergence_index"], reverse=True)

    # 准备图表1数据：X 轴标签（截断长名称）
    labels = []
    for t in sorted_topics:
        label = t["topic_label"] or t["topic_key"]
        if len(label) > 20:
            label = label[:20] + "..."
        labels.append(label)

    # 柱状图数据（包含颜色与 tooltip 所需的全部信息）
    bar_data = []
    for t in sorted_topics:
        bar_data.append({
            #图表包含信息：话题名称、扩散指数、聚类类别、内容总数、跨话题比例、涉及其他话题数、平均关联话题数
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

    # 准备图表2数据：各聚类类别的话题数量
    cluster_names = ["高扩散（容易分化）", "中等扩散", "低扩散（不易分化）"]
    cluster_counts = {name: 0 for name in cluster_names}
    for t in sorted_topics:
        cluster_counts[t["cluster"]] += 1

    labels_json = json.dumps(labels, ensure_ascii=False)
    bar_data_json = json.dumps(bar_data, ensure_ascii=False)
    cluster_labels_json = json.dumps(cluster_names, ensure_ascii=False)
    cluster_values_json = json.dumps([
        {"value": cluster_counts["高扩散（容易分化）"], "itemStyle": {"color": "#e74c3c"}},
        {"value": cluster_counts["中等扩散"], "itemStyle": {"color": "#f39c12"}},
        {"value": cluster_counts["低扩散（不易分化）"], "itemStyle": {"color": "#27ae60"}},
    ], ensure_ascii=False)

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
        // ========== 图表1：所有话题的扩散指数柱状图 ==========
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

        // ========== 图表2：各聚类类别的话题数量柱状图 ==========
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

        // 自适应窗口大小
        window.addEventListener('resize', function() {{
            chart1.resize();
            chart2.resize();
        }});
    </script>
</body>
    </html>"""
    return html


# ======================== 主流程 ========================
def main():
    print("=" * 65)
    print("  话题扩散聚类分析")
    print("  基于话题内容交叉关系，判断话题是否容易分化成其他话题")
    print("=" * 65)

    # 连接数据库
    if not os.path.exists(DB_PATH):
        print(f"[错误] 数据库文件不存在: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    try:
        # 1. 读取所有话题
        topics = load_topics(conn)
        print(f"\n共读取 {len(topics)} 个话题")

        if not topics:
            print("[警告] 没有找到任何话题数据")
            return

        # 2. 逐个话题计算扩散指数
        topic_results = []
        for i, topic in enumerate(topics):
            label = topic["topic_label"] or topic["topic_key"]
            print(f"\n[{i + 1}/{len(topics)}] 分析话题: {label}")

            # 计算扩散指标
            metrics = compute_divergence(conn, topic["platform"], topic["topic_key"])

            topic_results.append({
                "topic_label": label,
                "topic_key": topic["topic_key"],
                "platform": topic["platform"],
                "post_count": topic["post_count"],
                **metrics,
            })

            print(f"  内容总数: {metrics['content_count']} | "
                  f"跨话题内容: {metrics['multi_topic_count']} ({metrics['multi_topic_ratio']:.1%})")
            print(f"  涉及其他话题: {metrics['unique_other_topics']} 个 | "
                  f"平均关联话题: {metrics['avg_topics_per_content']:.2f}")
            print(f"  扩散指数: {metrics['divergence_index']:.4f}")

        # 3. 聚类
        topic_results = cluster_topics(topic_results)

        # 4. 打印摘要表格
        print("\n" + "=" * 85)
        print("  分析结果摘要（按扩散指数降序）")
        print("=" * 85)
        header = f"{'话题':<28} {'扩散指数':>8} {'内容数':>6} {'跨话题%':>8} {'其他话题':>8} {'聚类类别'}"
        print(header)
        print("-" * 85)
        for t in topic_results:
            label_display = t["topic_label"]
            if len(label_display) > 24:
                label_display = label_display[:21] + "..."
            print(f"{label_display:<28} {t['divergence_index']:>8.4f} {t['content_count']:>6} "
                  f"{t['multi_topic_ratio'] * 100:>7.1f}% {t['unique_other_topics']:>8} "
                  f"  {t['cluster']}")

        # 统计各聚类数量
        cluster_summary = {}
        for t in topic_results:
            cluster_summary[t["cluster"]] = cluster_summary.get(t["cluster"], 0) + 1
        print(f"\n聚类统计: "
              f"高扩散={cluster_summary.get('高扩散（容易分化）', 0)} | "
              f"中等扩散={cluster_summary.get('中等扩散', 0)} | "
              f"低扩散={cluster_summary.get('低扩散（不易分化）', 0)}")

        # 5. 确保输出目录存在并生成 HTML
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        html_content = generate_html(topic_results)
        with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
            f.write(html_content)

        print(f"\n✅ ECharts 图表已生成: {OUTPUT_HTML}")

    except Exception as e:
        print(f"\n[错误] 程序执行异常: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
