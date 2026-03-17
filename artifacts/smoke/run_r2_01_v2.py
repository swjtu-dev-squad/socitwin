"""
R2-01 Multi-Agent Non-Empty Behavior Smoke Test (v2 - after camel patch)
配置A: 3 agents, 10 steps
配置B: 5 agents, 20 steps
"""
import requests
import time
import json

BASE = "http://localhost:3000"

def reset():
    r = requests.post(f"{BASE}/api/sim/reset")
    return r.json()

def initialize(agent_count, platform="reddit", topics=["AI"], recsys="hot-score"):
    r = requests.post(f"{BASE}/api/sim/config", json={
        "agentCount": agent_count,
        "platform": platform,
        "topics": topics,
        "recsys": recsys,
        "regions": []
    })
    return r.json()

def start():
    # initialize already sets running=true, no separate start needed
    # just resume in case it's paused
    r = requests.post(f"{BASE}/api/sim/resume")
    return r.status_code

def step():
    r = requests.post(f"{BASE}/api/sim/step")
    return r.json()

def status():
    r = requests.get(f"{BASE}/api/sim/status")
    return r.json()

def logs():
    r = requests.get(f"{BASE}/api/sim/logs")
    return r.json()

def run_config(label, agent_count, num_steps):
    print(f"\n{'='*60}")
    print(f"[{label}] agents={agent_count}, steps={num_steps}")
    print('='*60)
    
    reset()
    time.sleep(1)
    
    init_result = initialize(agent_count)
    print(f"Init: {init_result.get('status', 'unknown')}")
    
    start()
    time.sleep(1)
    
    step_posts = []
    step_times = []
    errors = []
    
    for i in range(1, num_steps + 1):
        t0 = time.time()
        result = step()
        elapsed = time.time() - t0
        
        total_posts = result.get('totalPosts', 0)
        step_posts.append(total_posts)
        step_times.append(elapsed)
        
        if elapsed > 2.0:
            print(f"  Step {i:2d}: posts={total_posts:3d}, time={elapsed:.1f}s ✅ (LLM called)")
        else:
            print(f"  Step {i:2d}: posts={total_posts:3d}, time={elapsed:.2f}s ⚠️  (fast - no LLM?)")
        
        if result.get('status') == 'error':
            errors.append(f"Step {i}: {result.get('message', 'unknown error')}")
    
    # Get logs
    log_data = logs()
    log_list = log_data if isinstance(log_data, list) else log_data.get('logs', [])
    
    final_posts = step_posts[-1] if step_posts else 0
    max_posts = max(step_posts) if step_posts else 0
    avg_time = sum(step_times) / len(step_times) if step_times else 0
    llm_steps = sum(1 for t in step_times if t > 2.0)
    
    result = {
        "label": label,
        "agent_count": agent_count,
        "num_steps": num_steps,
        "final_posts": final_posts,
        "max_posts": max_posts,
        "total_logs": len(log_list),
        "avg_step_time": round(avg_time, 2),
        "llm_active_steps": llm_steps,
        "errors": errors,
        "step_posts_trace": step_posts,
        "pass": final_posts > 0 and llm_steps > 0
    }
    
    print(f"\n  Summary: posts={final_posts}, logs={len(log_list)}, llm_steps={llm_steps}/{num_steps}, avg_time={avg_time:.1f}s")
    print(f"  RESULT: {'✅ PASS' if result['pass'] else '❌ FAIL'}")
    return result

if __name__ == "__main__":
    results = []
    
    # Config A: 3 agents, 10 steps
    r_a = run_config("Config-A", agent_count=3, num_steps=10)
    results.append(r_a)
    
    time.sleep(2)
    
    # Config B: 5 agents, 20 steps
    r_b = run_config("Config-B", agent_count=5, num_steps=20)
    results.append(r_b)
    
    # Save results
    with open("artifacts/smoke/r2_01_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print("\n" + "="*60)
    print("R2-01 FINAL RESULTS")
    print("="*60)
    for r in results:
        status = "✅ PASS" if r["pass"] else "❌ FAIL"
        print(f"  {r['label']}: {status} | posts={r['final_posts']} | logs={r['total_logs']} | llm_steps={r['llm_active_steps']}/{r['num_steps']}")
    
    all_pass = all(r["pass"] for r in results)
    print(f"\nOverall: {'✅ ALL PASS' if all_pass else '❌ SOME FAILED'}")
