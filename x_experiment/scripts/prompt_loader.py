"""从 YAML 模板文件加载并渲染 prompt，支持多角度观点生成"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml


@dataclass
class PromptContext:
    """渲染后的 prompt 上下文"""
    messages: list[dict] = field(default_factory=list)
    model_params: dict = field(default_factory=dict)


class PromptLoader:
    """加载 YAML 模板文件，按任务名渲染 prompt"""

    DEFAULT_TEMPLATE_DIR = Path(__file__).parent.parent / "prompts"

    def __init__(self, template_dir: Optional[Path] = None):
        self.template_dir = Path(template_dir) if template_dir else self.DEFAULT_TEMPLATE_DIR
        self.logger = logging.getLogger(__name__)
        self._data = self._load_templates()

    def _find_template_file(self) -> Path:
        """查找模板文件，优先 .yaml 其次 .yml"""
        for ext in (".yaml", ".yml"):
            candidate = self.template_dir / f"templates{ext}"
            if candidate.exists():
                return candidate
        raise FileNotFoundError(f"未找到模板文件: {self.template_dir}/templates.yaml")

    def _load_templates(self) -> dict:
        template_path = self._find_template_file()
        self.logger.info("加载 prompt 模板: %s", template_path)
        with open(template_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            raise ValueError("模板文件格式错误：顶层必须是 dict")
        if "roles" not in data or "tasks" not in data:
            raise ValueError("模板文件缺少 'roles' 或 'tasks' 字段")
        return data

    def get_role(self, role_name: str) -> str:
        """获取指定名称的系统角色"""
        role = self._data.get("roles", {}).get(role_name)
        if not role:
            available = ", ".join(self._data.get("roles", {}).keys())
            raise KeyError(f"未找到角色 '{role_name}'，可用角色: {available}")
        return role

    def render(
        self, task_name: str, *, perspective: Optional[str] = None, **kwargs: Any
    ) -> PromptContext:
        """渲染指定任务的 prompt 模板

        Args:
            task_name: 任务名（如 analyze_majority, generate_perspective）
            perspective: 观点角度（仅 generate_perspective 任务需要）
            **kwargs: 模板变量

        Returns:
            PromptContext(messages=[...], model_params={...})
        """
        task = self._data.get("tasks", {}).get(task_name)
        if not task:
            available = ", ".join(self._data.get("tasks", {}).keys())
            raise KeyError(f"未找到任务 '{task_name}'，可用任务: {available}")

        if perspective is not None:
            perspectives = task.get("generate_perspective") or task
            if not isinstance(perspectives, dict):
                raise ValueError(f"任务 '{task_name}' 不支持 perspective 参数")
            perspective_config = perspectives.get(perspective)
            if not perspective_config:
                available_p = ", ".join(perspectives.keys())
                raise KeyError(f"未找到角度 '{perspective}'，可用角度: {available_p}")
            role_name = perspective_config["role"]
            model_params = dict(perspective_config.get("model_params", {}))
            prompt_template = perspective_config["prompt"]
        else:
            role_name = task["role"]
            model_params = dict(task.get("model_params", {}))
            prompt_template = task["prompt"]

        system_message = self.get_role(role_name)
        user_message = prompt_template.format(**kwargs)

        return PromptContext(
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message},
            ],
            model_params=model_params,
        )

    def list_perspectives(self) -> list[dict]:
        """列出 generate_perspective 任务中所有可用角度"""
        task = self._data.get("tasks", {}).get("generate_perspective")
        if not task:
            return []
        return [
            {
                "key": key,
                "label": cfg.get("label", key),
                "description": cfg.get("description", ""),
            }
            for key, cfg in task.items()
        ]

    def role_names(self) -> list[str]:
        """列出所有可用角色名称"""
        return list(self._data.get("roles", {}).keys())

    def task_names(self) -> list[str]:
        """列出所有可用任务名称"""
        return list(self._data.get("tasks", {}).keys())


if __name__ == "__main__":
    loader = PromptLoader()
    print("角色:", loader.role_names())
    print("任务:", loader.task_names())
    perspectives = loader.list_perspectives()
    print(f"角度 ({len(perspectives)}):")
    for p in perspectives:
        print(f"  [{p['key']}] {p['label']}: {p['description']}")
