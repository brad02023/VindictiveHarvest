from viha.bootstrap import MIN_VERSION, project_root


def test_project_root_has_pyproject():
    root = project_root()
    assert (root / "pyproject.toml").exists()
    text = (root / "pyproject.toml").read_text(encoding="utf-8")
    assert 'requires-python = ">=3.10"' in text


def test_minimum_python_is_3_10():
    assert MIN_VERSION == (3, 10)
