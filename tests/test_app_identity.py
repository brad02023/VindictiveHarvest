from viha import __app_user_model_id__
from viha.gui.theme import ICON_PATH


def test_windows_app_id_is_unique() -> None:
    assert __app_user_model_id__ == "VIHA.VindictiveHarvest.1"
    assert __app_user_model_id__ != "Panelroom.Desktop.1"


def test_taskbar_icon_exists() -> None:
    assert ICON_PATH.is_file()
