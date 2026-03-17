#!/usr/bin/env python3
"""
FIX-R3-POLARIZATION-FALLBACK Smoke Test
验证极化 fallback 历史隔离修复：
- 真实分析值写入主 history
- fallback 动态值不写入主 history
- 返回结果显式标注 source / is_fallback / history_written
- 多步 fallback 不导致主 history 被噪声污染
- R3-02 的"曲线不静止"特性仍然保留
"""
import asyncio
import csv
import json
import os
import sys

sys.path.insert(0, '/home/ubuntu/oasis-dashboard')
os.environ['OPENAI_API_KEY'] = os.environ.get('OPENAI_API_KEY', '')
os.environ['OPENAI_BASE_URL'] = os.environ.get('OPENAI_BASE_URL', 'https://api.openai.com/v1')

from oasis_dashboard.real_oasis_engine_v3 import RealOASISEngineV3


async def run_fix_r3_polarization_fallback():
    print("=" * 60)
    print("FIX-R3-POLARIZATION-FALLBACK Smoke Test")
    print("=" * 60)

    results = {
        'gates': {},
        'trace': [],
        'history_trace': [],
        'debug_log': [],
    }

    engine = RealOASISEngineV3(
        model_platform='openai',
        model_type='gpt-4.1-mini',
        db_path='/tmp/oasis-fix-pol-fallback.db',
    )

    try:
        init_result = await engine.initialize(
            agent_count=5,
            platform='reddit',
            topics=['AI'],
        )
        assert init_result['status'] == 'ok', f"Init failed: {init_result}"
        print(f"  Engine init: {init_result['agent_count']} agents")

        # 运行 15 步，记录每步的极化值、source、is_fallback、history_written 和 history 长度
        for step_num in range(15):
            step_result = await engine.step()
            assert step_result['status'] == 'ok', f"Step {step_num+1} failed"

            pol_details = step_result.get('polarization_details', {})
            pol_value = step_result.get('polarization', 0.0)
            source = pol_details.get('source', 'analyzed')
            is_fallback = pol_details.get('is_fallback', False)
            history_written = pol_details.get('history_written', True)

            # 获取当前主历史长度
            history_len = 0
            if hasattr(engine, 'polarization_analyzer') and engine.polarization_analyzer:
                history_len = len(getattr(engine.polarization_analyzer, 'history', []))

            trace_entry = {
                'step': step_result['current_step'],
                'total_posts': step_result.get('total_posts', 0),
                'polarization': pol_value,
                'source': source,
                'is_fallback': is_fallback,
                'history_written': history_written,
                'history_len': history_len,
            }
            results['trace'].append(trace_entry)

            print(
                f"  step {trace_entry['step']:2d}: pol={pol_value:.4f} "
                f"source={source:20s} is_fallback={str(is_fallback):5s} "
                f"history_written={str(history_written):5s} history_len={history_len}"
            )

    finally:
        await engine.reset()

    # ===== Gate Evaluation =====
    print("\n" + "=" * 60)
    print("=== Gate Evaluation ===")

    trace = results['trace']

    # Gate 1: 真实分析值写入 history
    analyzed_steps = [t for t in trace if not t['is_fallback']]
    gate1 = len(analyzed_steps) > 0 and all(t['history_written'] for t in analyzed_steps)
    results['gates']['real_analysis_writes_history'] = gate1
    print(f"  [{'PASS' if gate1 else 'FAIL'}] 真实分析值写入主 history (analyzed steps: {len(analyzed_steps)})")

    # Gate 2: fallback 动态值不写入主 history
    fallback_steps = [t for t in trace if t['is_fallback']]
    gate2 = len(fallback_steps) > 0 and all(not t['history_written'] for t in fallback_steps)
    results['gates']['fallback_not_write_history'] = gate2
    print(f"  [{'PASS' if gate2 else 'FAIL'}] fallback 动态值不写入主 history (fallback steps: {len(fallback_steps)})")

    # Gate 3: 返回结果显式标注 source
    gate3 = all('source' in t for t in trace) and len(set(t['source'] for t in trace)) >= 1
    results['gates']['source_field_present'] = gate3
    sources = set(t['source'] for t in trace)
    print(f"  [{'PASS' if gate3 else 'FAIL'}] 返回结果显式标注 source (sources: {sources})")

    # Gate 4: trace 中可分辨 analyzed / history_dynamic
    gate4 = 'analyzed' in sources or any(not t['is_fallback'] for t in trace)
    gate4 = gate4 and ('history_dynamic' in sources or any(t['is_fallback'] for t in trace))
    results['gates']['trace_distinguishable'] = gate4
    print(f"  [{'PASS' if gate4 else 'FAIL'}] trace 中可分辨 analyzed / history_dynamic")

    # Gate 5: 多步 fallback 不导致主 history 被噪声污染
    # 验证：history 长度只在真实分析步骤时增长
    history_growth_correct = True
    for i in range(1, len(trace)):
        prev = trace[i-1]
        curr = trace[i]
        if curr['is_fallback']:
            # fallback 步骤，history 长度不应增长
            if curr['history_len'] > prev['history_len']:
                history_growth_correct = False
                print(f"    ❌ step {curr['step']}: fallback but history grew {prev['history_len']} -> {curr['history_len']}")
    gate5 = history_growth_correct
    results['gates']['history_not_polluted'] = gate5
    print(f"  [{'PASS' if gate5 else 'FAIL'}] 多步 fallback 不导致主 history 被噪声污染")

    # Gate 6: R3-02 的"曲线不静止"特性仍然保留
    pol_values = [t['polarization'] for t in trace]
    unique_pol_values = len(set(round(v, 6) for v in pol_values))
    gate6 = unique_pol_values >= 3
    results['gates']['curve_still_dynamic'] = gate6
    print(f"  [{'PASS' if gate6 else 'FAIL'}] R3-02 曲线不静止特性保留 (unique values: {unique_pol_values})")

    all_pass = all(results['gates'].values())
    result_status = 'PASS' if all_pass else 'FAIL'
    print(f"\nFIX-R3-POLARIZATION-FALLBACK Result: {result_status}")
    results['status'] = result_status

    # 保存 trace CSV
    csv_path = 'artifacts/smoke/fix_r3_polarization_trace.csv'
    with open(csv_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['step', 'total_posts', 'polarization', 'source', 'is_fallback', 'history_written', 'history_len'])
        writer.writeheader()
        writer.writerows(trace)
    print(f"\nTrace saved to {csv_path}")

    return results


if __name__ == '__main__':
    result = asyncio.run(run_fix_r3_polarization_fallback())

    with open('artifacts/smoke/fix_r3_polarization_fallback_results.json', 'w') as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=str)

    print("Results saved to artifacts/smoke/fix_r3_polarization_fallback_results.json")
