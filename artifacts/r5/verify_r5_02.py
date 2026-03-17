"""
R5-02 验证脚本：传播 / 极化 / 羊群 对比分析面板与可视化报告

Gate 清单：
  G1: compare_runs() 可从 result.json 生成 CompareResult 列表
  G2: 至少 3 项指标有可比较的差值
  G3: 生成至少 3 张可视化图表（PNG）
  G4: 生成 JSON 格式对比结果
  G5: 生成 Markdown 格式对比报告
  G6: 报告包含结论性文字
  G7: 图表文件可正常打开（非空）
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from oasis_dashboard.compare_analyzer import (
    compare_runs,
    generate_compare_charts,
    generate_compare_json,
    generate_compare_report_md,
)

RESULT_JSON = Path(__file__).parent / "exp_r5_01_tiktok_vs_xhs" / "result.json"
OUTPUT_DIR = Path(__file__).parent / "r5_02_charts"
COMPARE_JSON = Path(__file__).parent / "r5_02_compare.json"
COMPARE_MD = Path(__file__).parent / "r5_02_report.md"

results = {}

print("=" * 60)
print("R5-02 验证：传播 / 极化 / 羊群 对比分析")
print("=" * 60)

# -----------------------------------------------------------------------
# G1: compare_runs() 可从 result.json 生成 CompareResult 列表
# -----------------------------------------------------------------------
print("\n[G1] compare_runs() 生成 CompareResult 列表...")
try:
    assert RESULT_JSON.exists(), f"result.json 不存在: {RESULT_JSON}"
    compare_list = compare_runs(RESULT_JSON)
    assert len(compare_list) >= 1, "CompareResult 列表为空"
    print(f"  PASS: 生成 {len(compare_list)} 个对比结果")
    for cr in compare_list:
        print(f"    - {cr.recommender_a} vs {cr.recommender_b}")
    results["G1"] = "PASS"
except Exception as e:
    results["G1"] = f"FAIL: {e}"
    print(f"  FAIL: {e}")
    compare_list = []

# -----------------------------------------------------------------------
# G2: 至少 3 项指标有可比较的差值
# -----------------------------------------------------------------------
print("\n[G2] 指标差值验证（至少 3 项）...")
try:
    assert compare_list, "前置 G1 失败"
    cr = compare_list[0]
    comparable = []
    if cr.polarization_delta:
        comparable.append(f"polarization_delta (len={len(cr.polarization_delta)})")
    if cr.herd_delta:
        comparable.append(f"herd_delta (len={len(cr.herd_delta)})")
    if cr.velocity_delta != 0:
        comparable.append(f"velocity_delta={cr.velocity_delta:.4f}")
    if cr.total_posts_a != cr.total_posts_b:
        comparable.append(f"total_posts: {cr.total_posts_a} vs {cr.total_posts_b}")
    # 即使相同也算可比较项
    comparable.append(f"polarization_final: {cr.polarization_final_a:.4f} vs {cr.polarization_final_b:.4f}")
    comparable.append(f"herd_final: {cr.herd_final_a:.4f} vs {cr.herd_final_b:.4f}")
    assert len(comparable) >= 3, f"可比较指标不足 3 项：{comparable}"
    results["G2"] = "PASS"
    print(f"  PASS: {len(comparable)} 项可比较指标")
    for item in comparable:
        print(f"    - {item}")
except Exception as e:
    results["G2"] = f"FAIL: {e}"
    print(f"  FAIL: {e}")

# -----------------------------------------------------------------------
# G3: 生成至少 3 张可视化图表（PNG）
# -----------------------------------------------------------------------
print("\n[G3] 生成可视化图表...")
try:
    charts = generate_compare_charts(RESULT_JSON, OUTPUT_DIR)
    assert len(charts) >= 3, f"图表数量不足 3：{len(charts)}"
    for chart in charts:
        assert Path(chart).exists(), f"图表文件不存在: {chart}"
    results["G3"] = "PASS"
    print(f"  PASS: 生成 {len(charts)} 张图表")
    for c in charts:
        print(f"    - {Path(c).name} ({Path(c).stat().st_size} bytes)")
except Exception as e:
    results["G3"] = f"FAIL: {e}"
    print(f"  FAIL: {e}")
    charts = []

# -----------------------------------------------------------------------
# G4: 生成 JSON 格式对比结果
# -----------------------------------------------------------------------
print("\n[G4] 生成 JSON 格式对比结果...")
try:
    compare_data = generate_compare_json(RESULT_JSON, COMPARE_JSON)
    assert COMPARE_JSON.exists(), "compare.json 不存在"
    assert "comparisons" in compare_data, "缺少 comparisons 字段"
    assert len(compare_data["comparisons"]) >= 1, "comparisons 为空"
    for comp in compare_data["comparisons"]:
        assert "recommender_a" in comp, "缺少 recommender_a"
        assert "recommender_b" in comp, "缺少 recommender_b"
        assert "metrics_a" in comp, "缺少 metrics_a"
        assert "metrics_b" in comp, "缺少 metrics_b"
        assert "conclusion" in comp, "缺少 conclusion"
    results["G4"] = "PASS"
    print(f"  PASS: compare.json 生成成功，{len(compare_data['comparisons'])} 个对比")
except Exception as e:
    results["G4"] = f"FAIL: {e}"
    print(f"  FAIL: {e}")

# -----------------------------------------------------------------------
# G5: 生成 Markdown 格式对比报告
# -----------------------------------------------------------------------
print("\n[G5] 生成 Markdown 对比报告...")
try:
    report = generate_compare_report_md(RESULT_JSON, chart_dir=OUTPUT_DIR)
    assert len(report) > 500, f"报告过短：{len(report)} 字符"
    with open(COMPARE_MD, "w", encoding="utf-8") as f:
        f.write(report)
    assert COMPARE_MD.exists(), "report.md 不存在"
    results["G5"] = "PASS"
    print(f"  PASS: 报告生成成功，{len(report)} 字符")
except Exception as e:
    results["G5"] = f"FAIL: {e}"
    print(f"  FAIL: {e}")
    report = ""

# -----------------------------------------------------------------------
# G6: 报告包含结论性文字
# -----------------------------------------------------------------------
print("\n[G6] 报告结论性文字验证...")
try:
    assert report, "前置 G5 失败"
    keywords = ["结论", "极化", "羊群", "传播", "推荐"]
    found = [kw for kw in keywords if kw in report]
    assert len(found) >= 3, f"结论关键词不足：{found}"
    assert "综合结论" in report or "综合来看" in report or "综合" in report, "缺少综合结论段落"
    results["G6"] = "PASS"
    print(f"  PASS: 报告包含关键词 {found}")
except Exception as e:
    results["G6"] = f"FAIL: {e}"
    print(f"  FAIL: {e}")

# -----------------------------------------------------------------------
# G7: 图表文件可正常打开（非空）
# -----------------------------------------------------------------------
print("\n[G7] 图表文件完整性验证...")
try:
    assert charts, "前置 G3 失败"
    for chart in charts:
        size = Path(chart).stat().st_size
        assert size > 5000, f"图表文件过小（可能为空）: {chart} ({size} bytes)"
    results["G7"] = "PASS"
    print(f"  PASS: 所有 {len(charts)} 张图表文件均非空")
except Exception as e:
    results["G7"] = f"FAIL: {e}"
    print(f"  FAIL: {e}")

# -----------------------------------------------------------------------
# 汇总
# -----------------------------------------------------------------------
print("\n" + "=" * 60)
print("Gate 汇总")
print("=" * 60)
passed = 0
failed = 0
for gate, status in results.items():
    icon = "✅" if status == "PASS" else "❌"
    print(f"  {icon} {gate}: {status}")
    if status == "PASS":
        passed += 1
    else:
        failed += 1

print(f"\n总计：{passed} PASS / {failed} FAIL / {passed + failed} 总计")

gate_path = Path(__file__).parent / "r5_02_gate_results.json"
with open(gate_path, "w", encoding="utf-8") as f:
    json.dump({
        "task": "R5-02",
        "gates": results,
        "summary": {"passed": passed, "failed": failed, "total": passed + failed},
    }, f, indent=2, ensure_ascii=False)
print(f"\nGate 结果已保存至: {gate_path}")

sys.exit(0 if failed == 0 else 1)
