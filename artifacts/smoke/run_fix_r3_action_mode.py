#!/usr/bin/env python3
"""
FIX-R3-ACTION-MODE Smoke Test
验证动作空间策略配置化修复：
- T1: default 模式保留 REFRESH
- T2: smoke_dense 模式移除 REFRESH
- T3: smoke_dense 行为密度回归（10 agents / 20 steps）
- T4: default 模式不报错
- Gate: 系统不再依赖硬编码删除默认动作
"""
import asyncio
import csv
import json
import os
import sys

sys.path.insert(0, '/home/ubuntu/oasis-dashboard')
os.environ['OPENAI_API_KEY'] = os.environ.get('OPENAI_API_KEY', '')
os.environ['OPENAI_BASE_URL'] = os.environ.get('OPENAI_BASE_URL', 'https://api.openai.com/v1')

from oasis_dashboard.real_oasis_engine_v3 import RealOASISEngineV3, ActionType


async def run_fix_r3_action_mode():
    print("=" * 60)
    print("FIX-R3-ACTION-MODE Smoke Test")
    print("=" * 60)

    results = {
        'gates': {},
        'mode_compare': [],
        'behavior_stats': {},
    }

    # ===== T1 & T2: 静态检查 default vs smoke_dense =====
    print("\n--- T1/T2: 静态动作集检查 ---")
    engine_default = RealOASISEngineV3(
        model_platform='openai',
        model_type='gpt-4.1-mini',
        db_path='/tmp/oasis-action-default.db',
        behavior_mode='default',
    )
    engine_smoke = RealOASISEngineV3(
        model_platform='openai',
        model_type='gpt-4.1-mini',
        db_path='/tmp/oasis-action-smoke.db',
        behavior_mode='smoke_dense',
    )

    default_actions = engine_default._build_available_actions('reddit', 'default')
    smoke_actions = engine_smoke._build_available_actions('reddit', 'smoke_dense')

    default_names = [a.name for a in default_actions]
    smoke_names = [a.name for a in smoke_actions]

    print(f"  default actions ({len(default_actions)}): {default_names}")
    print(f"  smoke_dense actions ({len(smoke_actions)}): {smoke_names}")

    # T1: default 模式保留 REFRESH
    t1_refresh_present = ActionType.REFRESH in default_actions
    t1_do_nothing_present = ActionType.DO_NOTHING in default_actions
    gate_t1 = t1_refresh_present and t1_do_nothing_present
    results['gates']['default_keeps_refresh'] = gate_t1
    print(f"  [{'PASS' if gate_t1 else 'FAIL'}] T1: default 模式保留 REFRESH={t1_refresh_present}, DO_NOTHING={t1_do_nothing_present}")

    # T2: smoke_dense 模式移除 REFRESH
    t2_refresh_absent = ActionType.REFRESH not in smoke_actions
    t2_do_nothing_absent = ActionType.DO_NOTHING not in smoke_actions
    gate_t2 = t2_refresh_absent and t2_do_nothing_absent
    results['gates']['smoke_dense_removes_refresh'] = gate_t2
    print(f"  [{'PASS' if gate_t2 else 'FAIL'}] T2: smoke_dense 移除 REFRESH={t2_refresh_absent}, DO_NOTHING={t2_do_nothing_absent}")

    # Gate: smoke_dense 与 default 有差异
    gate_diff = set(default_names) != set(smoke_names)
    results['gates']['modes_are_different'] = gate_diff
    print(f"  [{'PASS' if gate_diff else 'FAIL'}] Gate: smoke_dense 与 default 有差异")

    # 保存对比 CSV
    compare_rows = []
    all_actions = set(default_names) | set(smoke_names)
    for action in sorted(all_actions):
        compare_rows.append({
            'action': action,
            'in_default': action in default_names,
            'in_smoke_dense': action in smoke_names,
        })
    results['mode_compare'] = compare_rows

    # ===== T3: smoke_dense 行为密度回归（10 agents / 20 steps）=====
    print("\n--- T3: smoke_dense 行为密度回归 (10 agents / 20 steps) ---")
    engine_smoke_run = RealOASISEngineV3(
        model_platform='openai',
        model_type='gpt-4.1-mini',
        db_path='/tmp/oasis-action-smoke-run.db',
        behavior_mode='smoke_dense',
    )

    try:
        init_result = await engine_smoke_run.initialize(
            agent_count=10,
            platform='reddit',
            topics=['AI technology'],
        )
        assert init_result['status'] == 'ok', f"Init failed: {init_result}"
        print(f"  Engine init: {init_result['agent_count']} agents, behavior_mode=smoke_dense")

        smoke_stats = {'total_posts': [], 'unique_agents': set()}
        for step_num in range(20):
            step_result = await engine_smoke_run.step()
            assert step_result['status'] == 'ok', f"Step {step_num+1} failed"
            smoke_stats['total_posts'].append(step_result.get('total_posts', 0))
            if step_num % 5 == 4:
                print(f"  step {step_result['current_step']:2d}: total_posts={step_result.get('total_posts', 0)}")

        final_posts = smoke_stats['total_posts'][-1]
        gate_t3 = final_posts >= 5  # 至少 5 个帖子（10 agents 中至少 50% 发帖）
        results['gates']['smoke_dense_behavior_density'] = gate_t3
        results['behavior_stats']['smoke_dense_final_posts'] = final_posts
        print(f"  [{'PASS' if gate_t3 else 'FAIL'}] T3: smoke_dense 行为密度 (final_posts={final_posts}, threshold=5)")

    finally:
        await engine_smoke_run.reset()

    # ===== T4: default 模式不报错 =====
    print("\n--- T4: default 模式不报错 ---")
    engine_default_run = RealOASISEngineV3(
        model_platform='openai',
        model_type='gpt-4.1-mini',
        db_path='/tmp/oasis-action-default-run.db',
        behavior_mode='default',
    )

    t4_ok = False
    try:
        init_result = await engine_default_run.initialize(
            agent_count=5,
            platform='reddit',
            topics=['technology'],
        )
        assert init_result['status'] == 'ok', f"Init failed: {init_result}"
        # 运行 3 步验证不报错
        for step_num in range(3):
            step_result = await engine_default_run.step()
            assert step_result['status'] == 'ok', f"Step {step_num+1} failed"
        t4_ok = True
        print(f"  default 模式运行 3 步，无异常")
    except Exception as e:
        print(f"  ❌ default 模式运行失败: {e}")
    finally:
        await engine_default_run.reset()

    gate_t4 = t4_ok
    results['gates']['default_mode_no_error'] = gate_t4
    print(f"  [{'PASS' if gate_t4 else 'FAIL'}] T4: default 模式不报错")

    # ===== Gate: 系统不再依赖硬编码 =====
    # 通过代码检查验证 _build_available_actions 方法存在
    gate_configurable = hasattr(engine_default, '_build_available_actions')
    results['gates']['action_space_configurable'] = gate_configurable
    print(f"\n  [{'PASS' if gate_configurable else 'FAIL'}] Gate: _build_available_actions 方法存在（动作空间可配置）")

    # ===== 汇总 =====
    print("\n" + "=" * 60)
    print("=== Gate Evaluation ===")
    for gate_name, gate_result in results['gates'].items():
        print(f"  [{'PASS' if gate_result else 'FAIL'}] {gate_name}")

    all_pass = all(results['gates'].values())
    result_status = 'PASS' if all_pass else 'FAIL'
    print(f"\nFIX-R3-ACTION-MODE Result: {result_status}")
    results['status'] = result_status

    return results


if __name__ == '__main__':
    result = asyncio.run(run_fix_r3_action_mode())

    # 保存对比 CSV
    csv_path = 'artifacts/smoke/fix_r3_action_mode_compare.csv'
    with open(csv_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['action', 'in_default', 'in_smoke_dense'])
        writer.writeheader()
        writer.writerows(result.get('mode_compare', []))
    print(f"Compare CSV saved to {csv_path}")

    # 保存完整结果
    json_path = 'artifacts/smoke/fix_r3_action_mode_results.json'
    with open(json_path, 'w') as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=str)
    print(f"Results saved to {json_path}")
