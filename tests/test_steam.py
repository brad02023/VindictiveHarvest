from viha.core.steam import match_steam_personas, parse_steam_user_search, persona_key

HTML = """
<div class="search_row" data-panel="{}" role="button">
  <a class="searchPersonaName" href="https://steamcommunity.com/id/examplevanity">rm -rf /my/brain</a>
  <a href="https://steamcommunity.com/id/examplevanity">profile</a>
</div>
<div class="search_row">
  <a class="searchPersonaName" href="https://steamcommunity.com/id/otherperson">sudo rm -rf /</a>
  <a href="https://steamcommunity.com/id/otherperson">profile</a>
</div>
"""


def test_parse_steam_user_search():
    rows = parse_steam_user_search(HTML)
    assert rows[0] == ("rm -rf /my/brain", "https://steamcommunity.com/id/examplevanity")
    assert rows[1][0] == "sudo rm -rf /"


def test_match_requires_exact_persona_name():
    hits = match_steam_personas(HTML, "rm -rf /my/brain")
    assert hits == [("rm -rf /my/brain", "https://steamcommunity.com/id/examplevanity")]
    assert match_steam_personas(HTML, "sudo rm -rf /")[0][1].endswith("/otherperson")
    assert match_steam_personas(HTML, "rm -rf /") == []


def test_persona_key_collapses_space():
    assert persona_key("  RM -rf   /my/brain ") == "rm -rf /my/brain"
