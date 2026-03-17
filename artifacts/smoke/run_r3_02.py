#!/usr/bin/env python3
"""
R3-02 Polarization Dynamics Smoke Test
验证极化值在高密度行为场景下是否真正动态变化
"""
import asyncio
import json
import csv
import logging
import os
import sys
import time

# 设置日志
logging.basicConfig(level=logging.DEBUG, format='%(name)s - %(levelname)s - %(message)s')

sys.path.insert(0, '/home/ubuntu/oasis-dashboard')
os.environ['OPENAI_API_KEY'] = os.environ.get('OPENAI_API_KEY', '')
os.environ['OPENAI_BASE_URL'] = os.environ.get('OPENAI_BASE_URL', 'https://api.openai.com/v1')

from oasis_dashboard.real_oasis_engine_v3 import RealOASISEngineV3

async def run_r3_02():
    engine = RealOASISEngineV3(
        model_platform='openai',
        model_type='gpt-4.1-mini',
        db_path='/tmp/oasis-r3-02.db',
    )
    
    polarization_trace = []
    debug_log = []
    
    try:
        # 初始化
        init_result = await engine.initialize(
            agent_count=10,
            platform='reddit',
            topics=['AI', 'politics'],
        )
        assert init_result['status'] == 'ok', f"Init failed: {init_result}"
        print(f"✅ Init OK: {init_result['agent_count']} agents, topics={init_result['topics']}")
        
        # 运行 15 步
        for step_num in range(15):
            step_result = await engine.step()
            assert step_result['status'] == 'ok', f"Step {step_num+1} failed"
            
            polarization = step_result.get('polarization', 0.0)
            total_posts = step_result.get('total_posts', 0)
            step_time = step_result.get('step_time', 0)
            
            # 记录极化 trace
            trace_entry = {
                'step': step_result['current_step'],
                'total_posts': total_posts,
                'polarization': polarization,
                'step_time': round(step_time, 2),
            }
            polarization_trace.append(trace_entry)
            
            # 调试日志
            debug_log.append(
                f"[pol] step={step_result['current_step']} "
                f"total_posts={total_posts} "
                f"polarization={polarization:.4f} "
                f"step_time={step_time:.1f}s"
            )
            print(debug_log[-1])
        
        # 分析极化动态性
        pol_values = [t['polarization'] for t in polarization_trace]
        unique_pol = set(round(p, 4) for p in pol_values)
        
        print(f"\n=== R3-02 Gate Evaluation ===")
        print(f"Total steps: {len(polarization_trace)}")
        print(f"Polarization values: {[round(p, 4) for p in pol_values]}")
        print(f"Unique polarization values: {len(unique_pol)}")
        print(f"Min: {min(pol_values):.4f}, Max: {max(pol_values):.4f}")
        
        # Gate 评估
        gate_1 = len(unique_pol) >= 3  # 至少3个不同值
        gate_2 = max(pol_values) > 0.0  # 至少有非零值
        gate_3 = total_posts >= 5  # 有足够帖子
        gate_4 = True  # 无错误（已通过 assert）
        
        gates = {
            '极化值至少3个不同数值': gate_1,
            '极化值非零': gate_2,
            '帖子数 >= 5': gate_3,
            '无 traceback/错误': gate_4,
        }
        
        all_pass = all(gates.values())
        result_status = 'PASS' if all_pass else 'FAIL'
        
        for gate, passed in gates.items():
            print(f"  [{'✅' if passed else '❌'}] {gate}")
        
        print(f"\nR3-02 Result: {result_status}")
        
        return {
            'status': result_status,
            'polarization_trace': polarization_trace,
            'debug_log': debug_log,
            'gates': {k: bool(v) for k, v in gates.items()},
            'unique_pol_count': len(unique_pol),
            'pol_min': min(pol_values),
            'pol_max': max(pol_values),
            'total_posts': total_posts,
        }
    
    finally:
        await engine.reset()

if __name__ == '__main__':
    result = asyncio.run(run_r3_02())
    
    # 保存结果
    with open('artifacts/smoke/r3_02_results.json', 'w') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    # 保存 CSV
    with open('artifacts/smoke/r3_02_polarization_trace.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['step', 'total_posts', 'polarization', 'step_time'])
        writer.writeheader()
        for row in result['polarization_trace']:
            writer.writerow(row)
    
    # 保存调试日志
    with open('artifacts/smoke/r3_02_analyzer_debug.log', 'w') as f:
        f.write('\n'.join(result['debug_log']))
    
    print("\nResults saved to artifacts/smoke/r3_02_*")
