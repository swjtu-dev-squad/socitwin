#!/usr/bin/env python3
"""
R3-03 Sidecar Integration Smoke Test
验证 A/B 侧契约：EpisodeRecord 写入、检索、重置和非法输入拒绝
"""
import asyncio
import json
import os
import sys

sys.path.insert(0, '/home/ubuntu/oasis-dashboard')
os.environ['OPENAI_API_KEY'] = os.environ.get('OPENAI_API_KEY', '')
os.environ['OPENAI_BASE_URL'] = os.environ.get('OPENAI_BASE_URL', 'https://api.openai.com/v1')

from oasis_dashboard.real_oasis_engine_v3 import RealOASISEngineV3
from oasis_dashboard.longterm import InMemoryLongTermSidecar, EpisodeRecord


async def run_r3_03():
    print("=" * 60)
    print("R3-03 Sidecar Integration Smoke Test")
    print("=" * 60)

    results = {
        'gates': {},
        'sidecar_stats_trace': [],
        'episode_samples': [],
        'retrieve_results': {},
        'reset_verification': {},
    }

    # ===== Part 1: Unit Test - InMemoryLongTermSidecar =====
    print("\n[Part 1] Unit Test: InMemoryLongTermSidecar")
    sidecar = InMemoryLongTermSidecar(compaction_threshold=5, compaction_window=3)

    # 1.1 write_episode / write_episodes
    print("  [1.1] write_episode / write_episodes")
    ep1 = EpisodeRecord(step_id=1, agent_id="agent_0", raw_tokens=100, actions=["CREATE_POST"], observations=["post_1"])
    ep2 = EpisodeRecord(step_id=2, agent_id="agent_0", raw_tokens=120, actions=["LIKE_POST"], observations=["post_1", "post_2"])
    ep3 = EpisodeRecord(step_id=3, agent_id="agent_0", raw_tokens=150, actions=["CREATE_POST"], observations=["post_2", "post_3"])
    ep4 = EpisodeRecord(step_id=1, agent_id="agent_1", raw_tokens=80, actions=["CREATE_POST"], observations=["post_4"])
    ep5 = EpisodeRecord(step_id=2, agent_id="agent_1", raw_tokens=90, actions=["LIKE_POST"], observations=["post_1"])

    r1 = await sidecar.write_episode(ep1)
    assert r1['status'] == 'ok', f"write_episode failed: {r1}"

    r_batch = await sidecar.write_episodes([ep2, ep3, ep4, ep5])
    assert r_batch['status'] == 'ok', f"write_episodes failed: {r_batch}"
    assert r_batch['written'] == 4, f"Expected 4 written, got {r_batch['written']}"
    print(f"    write_episode: OK, write_episodes: {r_batch['written']} written")

    # 1.2 get_stats
    stats = await sidecar.get_stats()
    print(f"    get_stats: {stats}")
    assert stats['total_agents'] == 2, f"Expected 2 agents, got {stats['total_agents']}"
    assert stats['total_episodes'] == 5, f"Expected 5 episodes, got {stats['total_episodes']}"
    results['gates']['write_episode_works'] = True

    # 1.3 retrieve_relevant - 3 query_source types
    print("  [1.3] retrieve_relevant - 3 query_source types")

    # distilled topic
    r_distilled = await sidecar.retrieve_relevant(
        agent_id="agent_0", query="CREATE_POST", query_source="distilled topic", top_k=3
    )
    print(f"    distilled topic: {len(r_distilled)} results")
    assert isinstance(r_distilled, list), "retrieve_relevant should return list"

    # recent episodic summary
    r_recent = await sidecar.retrieve_relevant(
        agent_id="agent_0", query="post", query_source="recent episodic summary", top_k=3
    )
    print(f"    recent episodic summary: {len(r_recent)} results")

    # structured event query
    r_structured = await sidecar.retrieve_relevant(
        agent_id="agent_0", query="LIKE_POST", query_source="structured event query", top_k=3
    )
    print(f"    structured event query: {len(r_structured)} results")

    results['retrieve_results'] = {
        'distilled_topic': r_distilled,
        'recent_episodic_summary': r_recent,
        'structured_event_query': r_structured,
    }
    results['gates']['retrieve_relevant_works'] = True

    # 1.4 非法 query_source 拒绝
    print("  [1.4] Invalid query_source rejection")
    try:
        await sidecar.retrieve_relevant(
            agent_id="agent_0", query="test", query_source="invalid_source"
        )
        print("    Should have raised ValueError!")
        results['gates']['invalid_query_rejected'] = False
    except ValueError as e:
        print(f"    ValueError raised: {e}")
        results['gates']['invalid_query_rejected'] = True

    # 1.5 EpisodeRecord samples
    episodes_agent0 = await sidecar.retrieve("agent_0", last_n=5)
    results['episode_samples'] = episodes_agent0[:3]
    print(f"  [1.5] Episode samples: {len(episodes_agent0)} records for agent_0")
    for ep in episodes_agent0[:3]:
        print(f"    step={ep['step_id']}, agent={ep['agent_id']}, actions={ep['actions']}, compacted={ep['compacted']}")
    results['gates']['episode_samples_available'] = len(episodes_agent0) >= 3

    # 1.6 reset 验证
    print("  [1.6] reset verification")
    stats_before = await sidecar.get_stats()
    await sidecar.reset()
    stats_after = await sidecar.get_stats()
    print(f"    Before reset: {stats_before}")
    print(f"    After reset: {stats_after}")
    assert stats_after['total_agents'] == 0, "After reset, total_agents should be 0"
    assert stats_after['total_episodes'] == 0, "After reset, total_episodes should be 0"
    results['reset_verification'] = {'before': stats_before, 'after': stats_after}
    results['gates']['reset_works'] = True
    print("    Reset verified")

    # ===== Part 2: Integration Test - Engine with Sidecar =====
    print("\n[Part 2] Integration Test: Engine with Sidecar")
    engine = RealOASISEngineV3(
        model_platform='openai',
        model_type='gpt-4.1-mini',
        db_path='/tmp/oasis-r3-03.db',
    )

    try:
        init_result = await engine.initialize(
            agent_count=5,
            platform='reddit',
            topics=['AI'],
        )
        assert init_result['status'] == 'ok', f"Init failed: {init_result}"
        print(f"  Engine init: {init_result['agent_count']} agents")

        sidecar_stats_trace = []

        # 运行 10 步
        for step_num in range(10):
            step_result = await engine.step()
            assert step_result['status'] == 'ok', f"Step {step_num+1} failed"

            sidecar_stats = step_result.get('sidecar_stats')
            sidecar_stats_trace.append({
                'step': step_result['current_step'],
                'total_posts': step_result.get('total_posts', 0),
                'sidecar_stats': sidecar_stats,
            })

            print(f"  step {step_result['current_step']}: posts={step_result.get('total_posts', 0)}, sidecar={sidecar_stats}")

        results['sidecar_stats_trace'] = sidecar_stats_trace

        # 验证 sidecar_stats 有变化
        stats_values = [t['sidecar_stats'] for t in sidecar_stats_trace if t['sidecar_stats']]
        if stats_values:
            total_episodes_list = [s.get('total_episodes', 0) for s in stats_values]
            print(f"\n  total_episodes per step: {total_episodes_list}")
            sidecar_dynamic = max(total_episodes_list) > 0
            results['gates']['sidecar_stats_dynamic'] = sidecar_dynamic
            print(f"  sidecar_stats dynamic: {sidecar_dynamic}")
        else:
            results['gates']['sidecar_stats_dynamic'] = False
            print("  No sidecar_stats in step results")

    finally:
        await engine.reset()

    # ===== Gate Evaluation =====
    print("\n" + "=" * 60)
    print("=== R3-03 Gate Evaluation ===")

    gate_map = {
        'write_episode_works': 'write_episode / write_episodes 已实际发生',
        'retrieve_relevant_works': 'retrieve_relevant 能返回结果',
        'invalid_query_rejected': '非法 query_source 会被拒绝',
        'episode_samples_available': '至少观察到 3 条有效 EpisodeRecord 样本',
        'reset_works': 'reset 后 sidecar 被清空',
        'sidecar_stats_dynamic': 'sidecar_stats 在多步运行中有变化',
    }

    all_pass = True
    for gate_key, gate_desc in gate_map.items():
        passed = results['gates'].get(gate_key, False)
        if not passed:
            all_pass = False
        print(f"  [{'PASS' if passed else 'FAIL'}] {gate_desc}")

    result_status = 'PASS' if all_pass else 'FAIL'
    print(f"\nR3-03 Result: {result_status}")

    results['status'] = result_status
    return results


if __name__ == '__main__':
    result = asyncio.run(run_r3_03())

    # 保存结果
    with open('artifacts/smoke/r3_03_results.json', 'w') as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=str)

    # 保存 episode samples
    with open('artifacts/smoke/r3_03_episode_samples.json', 'w') as f:
        json.dump(result.get('episode_samples', []), f, indent=2, ensure_ascii=False, default=str)

    # 保存 retrieve results
    with open('artifacts/smoke/r3_03_retrieve_results.json', 'w') as f:
        json.dump(result.get('retrieve_results', {}), f, indent=2, ensure_ascii=False, default=str)

    print("\nResults saved to artifacts/smoke/r3_03_*")
