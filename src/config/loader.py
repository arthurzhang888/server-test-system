import yaml
from pathlib import Path
from typing import Union

from .schemas import GlobalConfig


class ConfigLoader:
    """Load and parse YAML configuration files."""

    def load_global_config(self, path: Union[str, Path]) -> GlobalConfig:
        """Load global configuration from YAML file."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")

        with open(path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        return GlobalConfig(**data)

    def load_server_type_config(self, server_type: str, config_dir: Union[str, Path]) -> GlobalConfig:
        """Load configuration for a specific server type."""
        config_dir = Path(config_dir)
        config_path = config_dir / f"{server_type}.yaml"
        return self.load_global_config(config_path)
