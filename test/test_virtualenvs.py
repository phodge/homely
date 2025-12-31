from pathlib import Path
from textwrap import dedent

from homely._virtualenv import PythonManager, RepoVirtualenvConfig


class TestReadVirtualenvConfig:
    def test_no_virtualenv_wanted(self, tmp_path: Path) -> None:
        # no virtualenv config is present
        config1 = tmp_path / 'config1.toml'
        config1.write_text(dedent(
            """
            [project]
            name = "some_project"
            """
        ))

        cfg1 = RepoVirtualenvConfig.from_pyproject_toml(config1)
        assert cfg1.want_virtualenv is False

        # virtualenv is turned OFF
        config2 = tmp_path / 'config1.toml'
        config2.write_text(dedent(
            """
            [tool.homely.virtualenv]
            minimum_python_version = "3.10"
            install_python_with = ["uv", "pyenv", "homebrew"]
            use_virtualenv = false
            virtualenv_path = "<desired_venv_path>"
            """
        ))

        cfg2 = RepoVirtualenvConfig.from_pyproject_toml(config2)
        assert cfg2.want_virtualenv is False

    def test_valid_virtualenv_config(self, tmp_path: Path) -> None:
        # minimal config
        config1 = tmp_path / 'config1.toml'
        config1.write_text(dedent(
            """
            [tool.homely.virtualenv]
            use_virtualenv = true
            minimum_python_version = "3.11"
            """
        ))

        cfg1 = RepoVirtualenvConfig.from_pyproject_toml(config1)
        assert cfg1.want_virtualenv is True
        assert cfg1.venv_path is None
        assert cfg1.min_python_version == (3, 11, 0)
        assert cfg1.install_with == []
        assert cfg1.config_warnings == []

        # config with all fields
        config2 = tmp_path / 'config2.toml'
        config2.write_text(dedent(
            """
            [tool.homely.virtualenv]
            use_virtualenv = true
            minimum_python_version = "3.10"
            install_python_with = ["uv", "pyenv", "homebrew"]
            virtualenv_path = "/path/to/venv"
            """
        ))

        cfg2 = RepoVirtualenvConfig.from_pyproject_toml(config2)
        assert cfg2.want_virtualenv is True
        assert cfg2.venv_path == Path("/path/to/venv")
        assert cfg2.min_python_version == (3, 10, 0)
        assert cfg2.install_with == [
            PythonManager.UV,
            PythonManager.PYENV,
            PythonManager.HOMEBREW,
        ]
        assert cfg2.config_warnings == []

    def test_virtualenv_config_needs_python_version_specifier(self, tmp_path: Path) -> None:
        # config with all fields
        config1 = tmp_path / 'config1.toml'
        config1.write_text(dedent(
            """
            [tool.homely.virtualenv]
            use_virtualenv = true
            install_python_with = ["uv"]
            """
        ))

        cfg1 = RepoVirtualenvConfig.from_pyproject_toml(config1)
        assert cfg1.want_virtualenv is True
        assert any("minimum_python_version is missing" in warning for warning in cfg1.config_warnings)

    def test_virtualenv_config_notices_invalid_installer(self, tmp_path: Path) -> None:
        # invalid installer name
        config1 = tmp_path / 'config1.toml'
        config1.write_text(dedent(
            """
            [tool.homely.virtualenv]
            use_virtualenv = true
            minimum_python_version = "3.10"
            install_python_with = ["magic"]
            """
        ))

        cfg1 = RepoVirtualenvConfig.from_pyproject_toml(config1)
        assert cfg1.want_virtualenv is True
        assert any("install_python_with contains" in warning for warning in cfg1.config_warnings)

        # invalid installer value (string instead of list)
        config2 = tmp_path / 'config2.toml'
        config2.write_text(dedent(
            """
            [tool.homely.virtualenv]
            use_virtualenv = true
            minimum_python_version = "3.10"
            install_python_with = "uv"
            """
        ))

        cfg2 = RepoVirtualenvConfig.from_pyproject_toml(config2)
        assert cfg2.want_virtualenv is True
        assert any("must be a list" in warning for warning in cfg2.config_warnings)
