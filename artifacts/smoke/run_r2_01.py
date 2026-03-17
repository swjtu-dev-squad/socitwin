"""
R2-01: 多 Agent 非空产出 Smoke Test
配置 A: 3 agents, 10 steps, reddit, AI
配置 B: 5 agents, 20 steps, reddit, AI+politics
"""
import requests
import json
import time
import csv
import os

BASE = "http://localhost:3000"

def reset():
    r = requests.post(f"{BASE}/api/sim/reset")
    return r.json()

def init_sim(agent_count, topics):
    payload = {
        "agentCount": agent_count,
        "platform": "reddit",
        "topics": topics,
        "recsys": "hot-score",
        "region": "global"
    }
    r = requests.post(f"{BASE}/api/sim/config", json=payload)
    return r.json()

def get_status():
    r = requests.get(f"{BASE}/api/sim/status")
    return r.json()

def do_step():
    r = requests.post(f"{BASE}/api/sim/step")
    return r.json()

def get_logs():
    r = requests.get(f"{BASE}/api/sim/logs")
    return r.json()

def run_config(label, agent_count, topics, steps):
    print(f"\n{'='*60}")
    print(f"[{label}] agents={agent_count}, steps={steps}, topics={topics}")
    print('='*60)

    # Reset
    reset()
    time.sleep(1)

    # Initialize
    print(f"[{label}] Initializing...")
    init_result = init_sim(agent_count, topics)
    print(f"  init result keys: {list(init_result.keys()) if isinstance(init_result, dict) else init_result}")

    # Wait for ready
    for _ in range(20):
        st = get_status()
        if st.get("oasis_ready") and st.get("activeAgents", 0) > 0:
            break
        time.sleep(2)

    st = get_status()
    print(f"  After init: activeAgents={st.get('activeAgents')}, totalPosts={st.get('totalPosts')}")

    rows = []
    for step_num in range(1, steps + 1):
        t0 = time.time()
        step_result = do_step()
        elapsed = time.time() - t0

        st = get_status()
        logs = get_logs()
        log_count = len(logs) if isinstance(logs, list) else 0

        row = {
            "step": step_num,
            "currentStep": st.get("currentStep", 0),
            "activeAgents": st.get("activeAgents", 0),
            "totalPosts": st.get("totalPosts", 0),
            "polarization": st.get("polarization", 0),
            "logCount": log_count,
            "stepTime": round(elapsed, 2),
        }
        rows.append(row)
        print(f"  Step {step_num:2d}: posts={row['totalPosts']:3d} logs={row['logCount']:3d} "
              f"polar={row['polarization']:.3f} t={row['stepTime']}s")

    # Collect sample logs
    logs = get_logs()
    samples = []
    if isinstance(logs, list):
        for log in logs[:5]:
            if isinstance(log, dict) and log.get("content"):
                samples.append({
                    "agent_id": log.get("agentId", log.get("agent_id", "?")),
                    "step": log.get("step", "?"),
                    "content": str(log.get("content", ""))[:200],
                    "action": log.get("action", log.get("type", "?")),
                })

    return rows, samples

# ---- Run Config A ----
rows_a, samples_a = run_config("Config-A", 3, ["AI"], 10)

# ---- Run Config B ----
rows_b, samples_b = run_config("Config-B", 5, ["AI", "politics"], 20)

# ---- Save CSV ----
os.makedirs("artifacts/smoke", exist_ok=True)
with open("artifacts/smoke/r2_01_steps.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["config","step","currentStep","activeAgents",
                                            "totalPosts","polarization","logCount","stepTime"])
    writer.writeheader()
    for r in rows_a:
        writer.writerow({"config": "A", **r})
    for r in rows_b:
        writer.writerow({"config": "B", **r})

# ---- Gate Check ----
final_a = rows_a[-1] if rows_a else {}
final_b = rows_b[-1] if rows_b else {}

gates = {
    "G1_config_a_posts_gt0": final_a.get("totalPosts", 0) > 0,
    "G2_config_b_posts_growing": (rows_b[-1].get("totalPosts",0) > rows_b[0].get("totalPosts",0)) if len(rows_b) > 1 else False,
    "G3_agents_gt1": final_b.get("activeAgents", 0) >= 2,
    "G4_logs_not_empty": final_b.get("logCount", 0) > 0,
    "G5_no_crash": True,  # If we got here, no crash
}

all_pass = all(gates.values())

# ---- Save Report ----
with open("artifacts/smoke/r2_01_nonempty_behavior.md", "w") as f:
    f.write("# R2-01 多 Agent 非空产出 Smoke Test — 结果报告\n\n")
    f.write(f"**执行时间**: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
    f.write(f"**总体结论**: {'✅ PASS' if all_pass else '❌ FAIL'}\n\n")
    f.write("---\n\n")

    f.write("## 配置 A（3 agents, 10 steps, AI）\n\n")
    f.write(f"- 最终 totalPosts: **{final_a.get('totalPosts', 0)}**\n")
    f.write(f"- 最终 logCount: **{final_a.get('logCount', 0)}**\n")
    f.write(f"- 最终 polarization: **{final_a.get('polarization', 0):.4f}**\n\n")

    f.write("| Step | totalPosts | logCount | polarization | stepTime(s) |\n")
    f.write("|---|---|---|---|---|\n")
    for r in rows_a:
        f.write(f"| {r['step']} | {r['totalPosts']} | {r['logCount']} | {r['polarization']:.4f} | {r['stepTime']} |\n")

    f.write("\n## 配置 B（5 agents, 20 steps, AI+politics）\n\n")
    f.write(f"- 最终 totalPosts: **{final_b.get('totalPosts', 0)}**\n")
    f.write(f"- 最终 logCount: **{final_b.get('logCount', 0)}**\n")
    f.write(f"- 最终 polarization: **{final_b.get('polarization', 0):.4f}**\n\n")

    f.write("| Step | totalPosts | logCount | polarization | stepTime(s) |\n")
    f.write("|---|---|---|---|---|\n")
    for r in rows_b:
        f.write(f"| {r['step']} | {r['totalPosts']} | {r['logCount']} | {r['polarization']:.4f} | {r['stepTime']} |\n")

    f.write("\n## 日志样本（配置 B，前5条）\n\n")
    if samples_b:
        for s in samples_b:
            f.write(f"- **Agent {s['agent_id']}** (step {s['step']}, action={s['action']}): {s['content']}\n")
    else:
        f.write("- 无有效日志样本\n")

    f.write("\n## Gate 验收\n\n")
    for k, v in gates.items():
        f.write(f"- [{'x' if v else ' '}] {k}: {'PASS' if v else 'FAIL'}\n")

print("\n" + "="*60)
print(f"R2-01 RESULT: {'✅ PASS' if all_pass else '❌ FAIL'}")
print("Gates:")
for k, v in gates.items():
    print(f"  {'✅' if v else '❌'} {k}")
print(f"\nConfig A final: posts={final_a.get('totalPosts',0)}, logs={final_a.get('logCount',0)}")
print(f"Config B final: posts={final_b.get('totalPosts',0)}, logs={final_b.get('logCount',0)}")
print(f"Samples collected: A={len(samples_a)}, B={len(samples_b)}")
