from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional


class PythonManager(Enum):
    UV = "uv"
    PYENV = "pyenv"
    HOMEBREW = "homebrew"


@dataclass
class RepoVirtualenvConfig:
    want_virtualenv: bool
    venv_path: Optional[Path]
    min_python_version: tuple[int, int, int]
    install_with: list[PythonManager]
    config_warnings: list[str]

    @classmethod
    def from_pyproject_toml(cls, pyproject_path: Path) -> "RepoVirtualenvConfig":
        try:
            # we need a type-ignore here because tomllib is only in Python
            # 3.11+ and mypy is configured to check against 3.10 stdlib.
            import tomllib  # type: ignore
        except ImportError:
            import tomli as tomllib

        with pyproject_path.open('rb') as f:
            try:
                toml_dict = tomllib.load(f)
            except tomllib.TOMLDecodeError:
                # FIXME: raise a better exception here
                raise

        try:
            venv_table = toml_dict['tool']['homely']['virtualenv']
        except KeyError:
            return RepoVirtualenvConfig(
                want_virtualenv=False,
                venv_path=None,
                min_python_version=(0, 0, 0),
                install_with=[],
                config_warnings=[],
            )

        config_warnings = []

        try:
            venv_path = Path(venv_table['virtualenv_path'])
        except TypeError:
            config_warnings.append("Error parsing tool.homely.virtualenv.virtualenv_path. It must be a string file path.")
            venv_path = None
        except KeyError:
            venv_path = None

        try:
            min_python_version = _parse_python_version(
                venv_table['minimum_python_version'],
                "tool.homely.virtualenv.minimum_python_version",
                config_warnings,
            )
        except KeyError:
            min_python_version = (0, 0, 0)
            config_warnings.append(
                "tool.homely.virtualenv.minimum_python_version is missing.",
            )

        install_with = []
        install_with_raw = venv_table.get('install_python_with', [])
        if not isinstance(install_with_raw, list):
            config_warnings.append(
                "Error parsing tool.homely.virtualenv.install_python_with."
                " It must be a list of zero or more of these strings: 'uv', 'pyenv', 'homebrew'.")
        else:
            for value in install_with_raw:
                if value == 'uv':
                    install_with.append(PythonManager.UV)
                elif value == 'pyenv':
                    install_with.append(PythonManager.PYENV)
                elif value == 'homebrew':
                    install_with.append(PythonManager.HOMEBREW)
                else:
                    config_warnings.append(
                        f"tool.homely.virtualenv.install_python_with contains invalid value {value!r}."
                        " It must be a list of zero or more of these strings: 'uv', 'pyenv', 'homebrew'."
                    )

        return RepoVirtualenvConfig(
            want_virtualenv=venv_table.get('use_virtualenv', False),
            venv_path=venv_path,
            min_python_version=min_python_version,
            install_with=install_with,
            config_warnings=config_warnings,
        )


def _parse_python_version(version_str: str, label: str, config_warnings: list[str]) -> tuple[int, int, int]:
    if not isinstance(version_str, str):
        config_warnings.append(f"Error parsing {label}. Expected a string like '3.13'.")
        return (0, 0, 0)

    parts = version_str.split('.')

    try:
        major = int(parts[0])
        minor = int(parts[1]) if len(parts) > 1 else 0
        patch = int(parts[2]) if len(parts) > 2 else 0
    except Exception:
        config_warnings.append(f"Error parsing {label}. Expected a string like '3.13'.")
        return (0, 0, 0)

    return (major, minor, patch)
