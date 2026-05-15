from types import SimpleNamespace

from warhammer40k_ai.utility import aura_effects


def test_aura_description_normalization_is_reused_for_same_text():
    aura_effects.clear_aura_parse_cache()

    raw = "<p>While a friendly WORLD EATERS unit is   within 6\" of this model.</p>"
    assert aura_effects._normalize_desc(raw) == 'While a friendly WORLD EATERS unit is within 6" of this model.'
    misses_after_first = aura_effects._normalize_desc_text.cache_info().misses

    assert aura_effects._normalize_desc(raw) == 'While a friendly WORLD EATERS unit is within 6" of this model.'
    info = aura_effects._normalize_desc_text.cache_info()
    assert info.misses == misses_after_first
    assert info.hits >= 1


def test_aura_detection_reuses_normalized_ability_text():
    aura_effects.clear_aura_parse_cache()

    ability = SimpleNamespace(
        name="Battle Lust",
        description='While a friendly WORLD EATERS unit is within 6" of this model, add 1 to the Hit roll.',
    )

    assert aura_effects._is_aura_ability(ability)
    misses_after_first = aura_effects._is_aura_ability_text.cache_info().misses

    assert aura_effects._is_aura_ability(ability)
    info = aura_effects._is_aura_ability_text.cache_info()
    assert info.misses == misses_after_first
    assert info.hits >= 1


def test_keyword_phrase_normalization_is_reused_for_same_text():
    aura_effects.clear_aura_parse_cache()

    assert aura_effects._normalize_keyword_phrase("WORLD EATERS") == "world eaters"
    misses_after_first = aura_effects._normalize_keyword_phrase_text.cache_info().misses

    assert aura_effects._normalize_keyword_phrase("WORLD EATERS") == "world eaters"
    info = aura_effects._normalize_keyword_phrase_text.cache_info()
    assert info.misses == misses_after_first
    assert info.hits >= 1


def test_cached_parse_aura_spec_reuses_same_ability_object_before_normalized_key(monkeypatch):
    aura_effects.clear_aura_parse_cache()
    ability = SimpleNamespace(
        name="The Fiery Heart (Aura)",
        description='While a friendly ADEPTA SORORITAS unit is within 6" of this model, add 2" to that unit.',
        parameter="",
    )

    first = aura_effects._cached_parse_aura_spec("test_parser", ability, lambda _ability: {"range": 6})
    assert first == {"range": 6}

    def unexpected_key_build(*_args, **_kwargs):
        raise AssertionError("same ability object should hit the object-level parse cache")

    monkeypatch.setattr(aura_effects, "_aura_parse_cache_key", unexpected_key_build)
    second = aura_effects._cached_parse_aura_spec("test_parser", ability, lambda _ability: {"range": 12})
    assert second == {"range": 6}


def test_enemy_move_oc_penalty_reuses_map_generation_cache(monkeypatch):
    aura_effects.clear_aura_parse_cache()
    ability = SimpleNamespace(name="Dread Presence (Aura)", description="", parameter="")
    source = SimpleNamespace(
        _id="source",
        possible_abilities=[ability],
        special_rules={},
        keywords=[],
        faction_keywords=[],
        deployed=True,
        is_alive=lambda: True,
    )
    target = SimpleNamespace(
        _id="target",
        special_rules={},
        keywords=[],
        faction_keywords=[],
        deployed=True,
        is_alive=lambda: True,
    )
    game_map = SimpleNamespace(
        state_generation=1,
        get_enemy_units=lambda _unit: [source],
    )
    monkeypatch.setattr(
        aura_effects,
        "_cached_parse_aura_spec",
        lambda _parser_key, _ability, _parser: {"range": 6, "move": -2, "oc": -1},
    )
    monkeypatch.setattr(aura_effects, "_unit_within_aura_range", lambda *_args, **_kwargs: True)

    first = aura_effects.get_enemy_aura_move_oc_penalties(target, game_map=game_map)
    assert first == (-2, -1)

    def unexpected_iter(_unit):
        raise AssertionError("cached move/OC aura penalties should not re-scan abilities")

    monkeypatch.setattr(aura_effects, "_iter_possible_abilities", unexpected_iter)
    second = aura_effects.get_enemy_aura_move_oc_penalties(target, game_map=game_map)
    assert second == first


def test_aura_move_characteristic_bonus_reuses_map_generation_cache(monkeypatch):
    aura_effects.clear_aura_parse_cache()
    ability = SimpleNamespace(name="Swift Host (Aura)", description="", parameter="")
    source = SimpleNamespace(
        _id="source",
        possible_abilities=[ability],
        special_rules={},
        keywords=[],
        faction_keywords=[],
        deployed=True,
        is_alive=lambda: True,
    )
    target = SimpleNamespace(
        _id="target",
        special_rules={},
        keywords=[],
        faction_keywords=[],
        deployed=True,
        is_alive=lambda: True,
    )
    game_map = SimpleNamespace(
        state_generation=1,
        get_friendly_units=lambda _unit: [source],
    )
    monkeypatch.setattr(
        aura_effects,
        "_cached_parse_aura_spec",
        lambda _parser_key, _ability, _parser: {"range": 6, "amount": 2},
    )
    monkeypatch.setattr(aura_effects, "_unit_within_aura_range", lambda *_args, **_kwargs: True)

    first = aura_effects.get_aura_move_characteristic_bonus(target, game_map=game_map)
    assert first == (2, ("Aura: +2 Move from Swift Host (Aura)",))

    def unexpected_iter(_unit):
        raise AssertionError("cached move aura bonus should not re-scan abilities")

    monkeypatch.setattr(aura_effects, "_iter_possible_abilities", unexpected_iter)
    second = aura_effects.get_aura_move_characteristic_bonus(target, game_map=game_map)
    assert second == first
