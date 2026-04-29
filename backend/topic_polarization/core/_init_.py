# backend/topic_polarization/__init__.py

# 导出核心功能函数，让外部项目可以直接调用
from .core.analyzer import start_analysis
from .core.visualizer import generate_chart
from .core.config import Config

# 定义模块版本（可选）
__version__ = "1.0.0"