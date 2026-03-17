import json, csv

with open('artifacts/smoke/r2_02_clean.json') as f:
    data = json.load(f)

steps = data.get('steps', [])
print(f'Total steps: {len(steps)}')
print()
header = f"{'Step':>4} | {'avg_mem':>8} | {'max_mem':>8} | {'avg_ctx':>8} | {'max_ctx':>8} | {'user':>5} | {'asst':>5} | {'tool':>5} | {'ctx_ms':>8}"
print(header)
print('-' * len(header))

csv_rows = []
for s in steps:
    cm = s.get('context_metrics', {})
    step = s.get('step', 0)
    avg_mem = cm.get('avg_memory_records', 0)
    max_mem = cm.get('max_memory_records', 0)
    avg_ctx = cm.get('avg_context_tokens', 0)
    max_ctx = cm.get('max_context_tokens', 0)
    user = cm.get('total_user_records', 0)
    asst = cm.get('total_assistant_records', 0)
    tool = cm.get('total_tool_records', 0)
    ctx_ms = cm.get('avg_get_context_ms', 0)
    print(f"{step:>4} | {avg_mem:>8.1f} | {max_mem:>8} | {avg_ctx:>8.1f} | {max_ctx:>8} | {user:>5} | {asst:>5} | {tool:>5} | {ctx_ms:>8.1f}")
    csv_rows.append({
        'step': step, 'avg_memory_records': avg_mem, 'max_memory_records': max_mem,
        'avg_context_tokens': avg_ctx, 'max_context_tokens': max_ctx,
        'total_user_records': user, 'total_assistant_records': asst,
        'total_tool_records': tool, 'avg_get_context_ms': ctx_ms
    })

# Save CSV
with open('artifacts/smoke/r2_02_context_metrics.csv', 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=csv_rows[0].keys())
    writer.writeheader()
    writer.writerows(csv_rows)
print(f"\nCSV saved: artifacts/smoke/r2_02_context_metrics.csv")

# Memory growth analysis
if len(steps) >= 2:
    first_mem = steps[0].get('context_metrics', {}).get('avg_memory_records', 0)
    last_mem = steps[-1].get('context_metrics', {}).get('avg_memory_records', 0)
    first_ctx = steps[0].get('context_metrics', {}).get('avg_context_tokens', 0)
    last_ctx = steps[-1].get('context_metrics', {}).get('avg_context_tokens', 0)
    print(f"\n=== Memory Growth Analysis ===")
    print(f"  avg_memory_records: step1={first_mem:.1f} -> step{len(steps)}={last_mem:.1f} (delta={last_mem-first_mem:+.1f})")
    print(f"  avg_context_tokens: step1={first_ctx:.1f} -> step{len(steps)}={last_ctx:.1f} (delta={last_ctx-first_ctx:+.1f})")
    growth_rate = (last_mem - first_mem) / max(len(steps) - 1, 1)
    print(f"  Memory growth rate: {growth_rate:.2f} records/step")
    if growth_rate > 1.5:
        print("  ⚠️  LINEAR GROWTH DETECTED - no compaction")
    elif growth_rate > 0.5:
        print("  ⚠️  MODERATE GROWTH - partial compaction or no compaction")
    else:
        print("  ✅ CONTROLLED GROWTH")

# EpisodeRecord check
print("\n=== EpisodeRecord check ===")
found_episode = False
episode_samples = []
for s in steps:
    for k, v in s.items():
        if 'episode' in str(k).lower() or (isinstance(v, (dict, list)) and 'episode' in str(v).lower()):
            print(f"  Step {s.get('step')}: {k} = {str(v)[:100]}")
            found_episode = True
            episode_samples.append({'step': s.get('step'), 'key': k, 'value': v})
if not found_episode:
    print("  ❌ No EpisodeRecord found in any step output")
    print("  CONCLUSION: Episodic Compaction NOT YET IMPLEMENTED (Issue #26 is open)")

with open('artifacts/smoke/r2_02_episode_samples.json', 'w') as f:
    json.dump(episode_samples if episode_samples else {"status": "not_implemented", "issue": "#26"}, f, indent=2)
print(f"\nEpisode samples saved: artifacts/smoke/r2_02_episode_samples.json")
