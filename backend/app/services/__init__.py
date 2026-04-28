"""
服务层模块

提供应用程序的业务逻辑服务。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

__all__ = ["SimulationService"]

if TYPE_CHECKING:
    # 仅用于类型检查；运行时避免导入 SimulationService 触发 oasis 依赖。
    from app.services.simulation_service import SimulationService as SimulationService


def __getattr__(name: str):
    """惰性导入，避免 `import app.services` 时拉起重依赖。

    例如运行 `python -m app.services.persona.legacy_pipeline.topics_classify` 只需要子模块，
    不应因为 SimulationService 的第三方依赖（如 oasis）未安装而失败。
    """

    if name == "SimulationService":
        from app.services.simulation_service import SimulationService as _SimulationService

        return _SimulationService
    raise AttributeError(name)
