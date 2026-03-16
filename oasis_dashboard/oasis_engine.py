"""
OASIS Engine Integration for OASIS Dashboard

This module integrates the real OASIS (Open-ended Autonomous Social Intelligence Simulation)
engine with the OASIS Dashboard backend. It provides a Python-based simulation engine
that uses local LLM models (e.g., Qwen3-8B via Ollama) for agent decision-making.

Key Features:
- Real OASIS engine integration (not a simulator)
- Local LLM support via Ollama
- Async/await support for non-blocking operations
- RESTful API endpoints for dashboard control
"""

import asyncio
import os
import json
from typing import Dict, List, Optional, Any
from datetime import datetime

# Lazy imports to speed up startup
# These will be imported when actually needed
# from camel.models import ModelFactory
# from camel.types import ModelPlatformType, ModelType
# import oasis
# from oasis import (...)


class OASISEngine:
    """
    OASIS Engine wrapper for dashboard integration.
    
    This class manages the OASIS simulation lifecycle, including:
    - Agent initialization and management
    - Environment setup and configuration
    - Simulation execution (step-by-step or continuous)
    - State tracking and reporting
    """
    
    def __init__(
        self,
        model_platform: Optional[str] = None,
        model_type: Optional[str] = None,
        db_path: str = "./oasis_simulation.db",
    ):
        """
        Initialize the OASIS Engine.
        
        Args:
            model_platform: LLM platform; defaults to OASIS_MODEL_PLATFORM
            model_type: Model type; defaults to OASIS_MODEL_TYPE
            db_path: Path to the simulation database
        """
        self.model_platform = model_platform or os.environ.get(
            "OASIS_MODEL_PLATFORM", "ollama"
        )
        self.model_type = model_type or os.environ.get(
            "OASIS_MODEL_TYPE", "qwen3:8b"
        )
        self.db_path = db_path
        
        self.agent_graph: Optional[Any] = None  # AgentGraph
        self.env: Optional[Any] = None
        self.model: Optional[Any] = None
        
        self.current_step = 0
        self.total_posts = 0
        self.active_agents = 0
        self.is_running = False
        
        self.agents: List[Any] = []  # List[SocialAgent]
        self.logs: List[Dict] = []
        
    async def initialize(
        self,
        agent_count: int = 10,
        platform: str = "reddit",
        available_actions: Optional[List] = None,
    ) -> Dict:
        """
        Initialize the OASIS simulation environment.
        
        Args:
            agent_count: Number of agents to create
            platform: Social platform type (e.g., "reddit", "twitter")
            available_actions: List of available action types for agents
            
        Returns:
            Status dictionary with initialization results
        """
        try:
            # Lazy import OASIS libraries
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
            )
            
            # Create the model
            if self.model_platform.lower() == "ollama":
                self.model = ModelFactory.create(
                    model_platform=ModelPlatformType.OLLAMA,
                    model_type=self.model_type,
                    model_config_dict={"temperature": 0.7},
                )
            else:
                self.model = ModelFactory.create(
                    model_platform=ModelPlatformType.OPENAI,
                    model_type=ModelType.GPT_4O_MINI,
                )
            
            # Define available actions
            if available_actions is None:
                available_actions = [
                    ActionType.LIKE_POST,
                    ActionType.CREATE_POST,
                    ActionType.CREATE_COMMENT,
                    ActionType.FOLLOW,
                ]
            
            # Initialize agent graph
            self.agent_graph = AgentGraph()
            
            # Create agents
            for i in range(agent_count):
                agent = SocialAgent(
                    agent_id=i,
                    user_info=UserInfo(
                        user_name=f"agent_{i}",
                        name=f"Agent {i}",
                        description=f"AI agent {i} in OASIS simulation",
                        profile=None,
                        recsys_type=platform,
                    ),
                    agent_graph=self.agent_graph,
                    model=self.model,
                    available_actions=available_actions,
                )
                self.agent_graph.add_agent(agent)
                self.agents.append(agent)
            
            # Set database path
            os.environ["OASIS_DB_PATH"] = os.path.abspath(self.db_path)
            
            # Delete old database if exists
            if os.path.exists(self.db_path):
                os.remove(self.db_path)
            
            # Create environment
            platform_type = (
                oasis.DefaultPlatformType.REDDIT
                if platform.lower() == "reddit"
                else oasis.DefaultPlatformType.TWITTER
            )
            
            self.env = oasis.make(
                agent_graph=self.agent_graph,
                platform=platform_type,
                database_path=self.db_path,
            )
            
            # Reset environment
            await self.env.reset()
            
            self.active_agents = agent_count
            self.is_running = True
            self.current_step = 0
            
            return {
                "status": "ok",
                "message": f"Initialized {agent_count} agents successfully",
                "agent_count": agent_count,
                "platform": platform,
            }
            
        except Exception as e:
            return {
                "status": "error",
                "message": f"Initialization failed: {str(e)}",
            }
    
    async def step(self) -> Dict:
        """
        Execute one simulation step.
        
        Returns:
            Status dictionary with step results
        """
        if not self.is_running or self.env is None:
            return {
                "status": "error",
                "message": "Simulation not initialized or not running",
            }
        
        try:
            # Lazy import LLMAction
            from oasis import LLMAction
            
            # Define LLM actions for all agents
            all_agents_llm_actions = {
                agent: LLMAction()
                for agent in self.agents
            }
            
            # Execute step
            await self.env.step(all_agents_llm_actions)
            
            self.current_step += 1
            
            # Update statistics (placeholder - actual implementation would query the database)
            self.total_posts += len(self.agents)  # Simplified
            
            # Log the step
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "step": self.current_step,
                "total_posts": self.total_posts,
                "active_agents": self.active_agents,
            }
            self.logs.append(log_entry)
            
            return {
                "status": "ok",
                "current_step": self.current_step,
                "total_posts": self.total_posts,
                "active_agents": self.active_agents,
            }
            
        except Exception as e:
            return {
                "status": "error",
                "message": f"Step execution failed: {str(e)}",
            }
    
    async def reset(self) -> Dict:
        """
        Reset the simulation to initial state.
        
        Returns:
            Status dictionary with reset results
        """
        if self.env is not None:
            await self.env.close()
        
        self.current_step = 0
        self.total_posts = 0
        self.is_running = False
        self.logs = []
        
        return {
            "status": "ok",
            "message": "Simulation reset successfully",
        }
    
    def get_status(self) -> Dict:
        """
        Get current simulation status.
        
        Returns:
            Status dictionary with current state
        """
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
        """
        Close the simulation environment and cleanup resources.
        
        Returns:
            Status dictionary with close results
        """
        if self.env is not None:
            await self.env.close()
        
        self.is_running = False
        
        return {
            "status": "ok",
            "message": "Simulation closed successfully",
        }


# Global engine instance
_engine: Optional[OASISEngine] = None


def get_engine() -> OASISEngine:
    """Get or create the global OASIS engine instance."""
    global _engine
    if _engine is None:
        _engine = OASISEngine()
    return _engine


# Example usage
async def main():
    """Example usage of the OASIS Engine."""
    engine = get_engine()
    
    # Initialize with 5 agents
    init_result = await engine.initialize(agent_count=5, platform="reddit")
    print(f"Initialization: {init_result}")
    
    # Run 3 simulation steps
    for i in range(3):
        step_result = await engine.step()
        print(f"Step {i+1}: {step_result}")
    
    # Get status
    status = engine.get_status()
    print(f"Status: {status}")
    
    # Close
    close_result = await engine.close()
    print(f"Close: {close_result}")


# JSON-RPC Server for stdin/stdout communication
async def handle_rpc_request(request: Dict) -> Dict:
    """Handle a single JSON-RPC request."""
    engine = get_engine()
    
    method = request.get("method")
    params = request.get("params", {})
    
    try:
        if method == "initialize":
            result = await engine.initialize(
                agent_count=params.get("agentCount", 5),
                platform=params.get("platform", "reddit"),
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
            result = {"status": "error", "message": f"Unknown method: {method}"}
        
        return {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "result": result,
        }
    except Exception as e:
        return {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "error": {
                "code": -32603,
                "message": str(e),
            },
        }


async def run_rpc_server():
    """Run JSON-RPC server on stdin/stdout."""
    import sys
    
    # Send ready signal
    print(json.dumps({"status": "ready"}), flush=True)
    
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            
            request = json.loads(line.strip())
            response = await handle_rpc_request(request)
            print(json.dumps(response), flush=True)
        except Exception as e:
            error_response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32700,
                    "message": f"Parse error: {str(e)}",
                },
            }
            print(json.dumps(error_response), flush=True)


if __name__ == "__main__":
    import sys
    
    # Check if running in RPC mode
    if len(sys.argv) > 1 and sys.argv[1] == "--rpc":
        asyncio.run(run_rpc_server())
    else:
        # Run example usage
        asyncio.run(main())
