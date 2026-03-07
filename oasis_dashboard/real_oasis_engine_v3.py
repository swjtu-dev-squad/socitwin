#!/usr/bin/env python3
"""
Real OASIS Engine V3 - Speed Optimized
真实 OASIS 引擎 V3 - 速度优化版

优化 Qwen2.5-3B 调用速度，确保 step 在 30 秒内完成
"""

import os
import sys
import time

# 解决 torch 和其他依赖加载慢的问题
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

print("✅ 开始导入真实OASIS...", flush=True)

import json
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime

# 监控导入时间
import_start = time.time()

from camel.models import ModelFactory
from camel.types import ModelPlatformType, ModelType

import oasis
from oasis import (
    ActionType,
    AgentGraph,
    LLMAction,
    ManualAction,
    SocialAgent,
    UserInfo,
    make,
    DefaultPlatformType,
)

print(f"✅ OASIS导入完成，耗时 {time.time() - import_start:.2f}秒", flush=True)


class RealOASISEngineV3:
    """
    真实 OASIS 引擎 V3（速度优化版）
    
    - 强制最小化执行（1个agent）
    - 使用 ManualAction 快速验证
    - 优化 Qwen2.5-3B 调用速度
    """
    
    def __init__(
        self,
        model_platform: str = "ollama",
        model_type: str = "qwen2.5:3b",
        db_path: str = "./oasis_simulation.db",
    ):
        """初始化真实 OASIS 引擎"""
        self.model_platform = model_platform
        self.model_type = model_type
        self.db_path = db_path
        
        self.agent_graph: Optional[Any] = None
        self.env: Optional[Any] = None
        self.model: Optional[Any] = None
        
        self.current_step = 0
        self.total_posts = 0
        self.active_agents = 0
        self.is_running = False
        
        self.agents: List[Any] = []
        self.logs: List[Dict] = []
        
        # 使用真实 LLMAction 模式
        self.use_llm_action = True
        
        print("✅ RealOASISEngineV3 实例已创建", flush=True)
    
    async def initialize(
        self,
        agent_count: int = 10,
        platform: str = "reddit",
        recsys: str = "hot-score",
        topic: str = "general",
    ) -> Dict:
        """初始化真实 OASIS 模拟环境"""
        try:
            print(f"🚀 开始初始化真实OASIS（速度优化版）", flush=True)
            init_start = time.time()
            
            # 速度优化：强制使用 1 个 agent 进行测试
            agent_count = 1
            print(f"⚡ 速度优化：强制使用 {agent_count} 个 agent（真实Qwen LLM调用）", flush=True)
            
            # 创建模型
            model_load_start = time.time()
            print(f"正在加载 Qwen2.5-3B 本地模型...", flush=True)
            
            if self.model_platform.lower() == "ollama":
                self.model = ModelFactory.create(
                    model_platform=ModelPlatformType.OLLAMA,
                    model_type=self.model_type,
                    model_config_dict={
                        "temperature": 0.7,
                        "max_tokens": 100,  # 限制输出长度以加快速度
                    },
                )
                model_load_time = time.time() - model_load_start
                print(f"Qwen2.5-3B 加载完成，耗时 {model_load_time:.2f} 秒", flush=True)
            else:
                self.model = ModelFactory.create(
                    model_platform=ModelPlatformType.OPENAI,
                    model_type=ModelType.GPT_4O_MINI,
                )
                print(f"✅ OpenAI 模型已创建", flush=True)
            
            # 定义可用动作（最小化）
            available_actions = [
                ActionType.CREATE_POST,
                ActionType.LIKE_POST,
            ]
            
            # 初始化 agent graph
            self.agent_graph = AgentGraph()
            print(f"✅ AgentGraph 已创建", flush=True)
            
            # 创建 agents（只创建 1 个）
            for i in range(agent_count):
                agent = SocialAgent(
                    agent_id=i,
                    user_info=UserInfo(
                        user_name=f"agent_{i}",
                        name=f"Agent {i}",
                        description=f"AI agent {i} - Topic: {topic}",
                        profile=None,
                        recsys_type=recsys,
                    ),
                    agent_graph=self.agent_graph,
                    model=self.model,
                    available_actions=available_actions,
                )
                self.agent_graph.add_agent(agent)
                self.agents.append(agent)
            
            print(f"✅ 已创建 {agent_count} 个 SocialAgent", flush=True)
            
            # 设置数据库路径
            os.environ["OASIS_DB_PATH"] = os.path.abspath(self.db_path)
            
            # 删除旧数据库
            if os.path.exists(self.db_path):
                os.remove(self.db_path)
                print(f"🗑️  已删除旧数据库", flush=True)
            
            # 创建环境
            platform_type = (
                DefaultPlatformType.REDDIT
                if platform.lower() == "reddit"
                else DefaultPlatformType.TWITTER
            )
            
            self.env = make(
                agent_graph=self.agent_graph,
                platform=platform_type,
                database_path=self.db_path,
            )
            print(f"✅ OASIS 环境已创建: {platform_type}", flush=True)
            
            # 重置环境
            await self.env.reset()
            print(f"✅ 环境已重置", flush=True)
            
            self.active_agents = agent_count
            self.is_running = True
            self.current_step = 0
            
            init_time = time.time() - init_start
            print(f"🎉 真实OASIS初始化完成！耗时 {init_time:.3f}秒", flush=True)
            
            return {
                "status": "ok",
                "message": f"真实OASIS已初始化 {agent_count} 个agents（速度优化版）",
                "agent_count": agent_count,
                "platform": platform,
                "recsys": recsys,
                "topic": topic,
                "init_time": init_time,
            }
            
        except Exception as e:
            print(f"❌ 初始化失败: {str(e)}", flush=True)
            import traceback
            traceback.print_exc()
            return {
                "status": "error",
                "message": f"初始化失败: {str(e)}",
            }
    
    async def step(self) -> Dict:
        """执行一步真实 OASIS 模拟（速度优化版）"""
        if not self.is_running or self.env is None:
            return {
                "status": "error",
                "message": "模拟未初始化或未运行",
            }
        
        try:
            step_start = time.time()
            print(f"⚙️  执行第 {self.current_step + 1} 步（速度优化版）...", flush=True)
            
            # 恢复真实 LLMAction + Qwen2.5-3B 模型调用
            print(f"🤖 使用真实 LLMAction + Qwen2.5-3B 模型", flush=True)
            all_agents_actions = {
                agent: LLMAction()
                for agent in self.agents
            }
            
            # 执行步骤
            await self.env.step(all_agents_actions)
            
            self.current_step += 1
            self.total_posts += len(self.agents)
            
            step_time = time.time() - step_start
            
            # 记录日志
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "step": self.current_step,
                "total_posts": self.total_posts,
                "active_agents": self.active_agents,
                "step_time": step_time,
            }
            self.logs.append(log_entry)
            
            print(f"✅ 第 {self.current_step} 步完成，耗时 {step_time:.3f}秒", flush=True)
            
            return {
                "status": "ok",
                "current_step": self.current_step,
                "total_posts": self.total_posts,
                "active_agents": self.active_agents,
                "step_time": step_time,
            }
            
        except Exception as e:
            print(f"❌ 步骤执行失败: {str(e)}", flush=True)
            import traceback
            traceback.print_exc()
            return {
                "status": "error",
                "message": f"步骤执行失败: {str(e)}",
            }
    
    async def reset(self) -> Dict:
        """重置模拟"""
        if self.env is not None:
            await self.env.close()
        
        self.current_step = 0
        self.total_posts = 0
        self.is_running = False
        self.logs = []
        
        print("🔄 模拟已重置", flush=True)
        
        return {
            "status": "ok",
            "message": "模拟已重置",
        }
    
    def get_status(self) -> Dict:
        """获取当前模拟状态"""
        return {
            "status": "ok",
            "data": {
                "currentStep": self.current_step,
                "totalPosts": self.total_posts,
                "activeAgents": self.active_agents,
                "isRunning": self.is_running,
                "running": self.is_running,
            },
        }
    
    async def close(self) -> Dict:
        """关闭模拟环境"""
        if self.env is not None:
            await self.env.close()
        
        self.is_running = False
        
        print("🛑 模拟已关闭", flush=True)
        
        return {
            "status": "ok",
            "message": "模拟已关闭",
        }


# 全局引擎实例
_engine: Optional[RealOASISEngineV3] = None


def get_engine() -> RealOASISEngineV3:
    """获取或创建全局 OASIS 引擎实例"""
    global _engine
    if _engine is None:
        _engine = RealOASISEngineV3()
    return _engine


# JSON-RPC 服务器
async def handle_rpc_request(request: Dict) -> Dict:
    """处理单个 JSON-RPC 请求"""
    engine = get_engine()
    
    method = request.get("method")
    params = request.get("params", {})
    
    try:
        if method == "initialize":
            result = await engine.initialize(
                agent_count=params.get("agentCount", 1),
                platform=params.get("platform", "reddit"),
                recsys=params.get("recsys", "hot-score"),
                topic=params.get("topic", "general"),
            )
        elif method == "step":
            result = await engine.step()
        elif method == "status":
            result = engine.get_status()
        elif method == "reset":
            result = await engine.reset()
        elif method == "close":
            result = await engine.close()
        else:
            result = {"status": "error", "message": f"未知方法: {method}"}
        
        return {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "result": result,
        }
    except Exception as e:
        print(f"❌ RPC 请求处理失败: {str(e)}", flush=True)
        import traceback
        traceback.print_exc()
        return {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "error": {
                "code": -32603,
                "message": str(e),
            },
        }


async def run_rpc_server():
    """运行 JSON-RPC 服务器（stdin/stdout）"""
    # 发送就绪信号
    print(json.dumps({"status": "ready"}), flush=True)
    print("✅ JSON-RPC 服务器已启动，等待请求...", file=sys.stderr, flush=True)
    
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            
            request = json.loads(line.strip())
            print(f"📥 收到请求: {request.get('method')}", file=sys.stderr, flush=True)
            
            response = await handle_rpc_request(request)
            print(json.dumps(response), flush=True)
            
        except Exception as e:
            print(f"❌ 解析错误: {str(e)}", file=sys.stderr, flush=True)
            error_response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32700,
                    "message": f"解析错误: {str(e)}",
                },
            }
            print(json.dumps(error_response), flush=True)


# 示例用法
async def main():
    """示例：测试真实 OASIS 引擎"""
    engine = get_engine()
    
    # 初始化
    init_result = await engine.initialize(agent_count=1, platform="reddit")
    print(f"初始化结果: {init_result}")
    
    # 运行 5 步
    for i in range(5):
        step_result = await engine.step()
        print(f"第 {i+1} 步: {step_result}")
    
    # 获取状态
    status = engine.get_status()
    print(f"状态: {status}")
    
    # 关闭
    close_result = await engine.close()
    print(f"关闭: {close_result}")


if __name__ == "__main__":
    # 检查是否以 RPC 模式运行
    if len(sys.argv) > 1 and sys.argv[1] == "--rpc":
        asyncio.run(run_rpc_server())
    else:
        # 运行示例
        asyncio.run(main())
