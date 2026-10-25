"""Fictional cast coherence without using names as behavioral or visual proxies."""
import copy

import pytest

from backend.app.schemas import ScenarioConfig, WarningConfig
from backend.app.simulation.campus_engine import CampusSimulation
from backend.app.simulation.campus_identity import (
    IDENTITY_VERSION,
    NAME_STYLES,
    family_identity,
    resident_identity,
)
from backend.app.simulation.campus_life import appearance, make_campus_profiles
from backend.app.simulation.campus_world import make_campus_city
from backend.app.simulation.world import uniform


@pytest.mark.parametrize("seed", [0, 42, 2026])
def test_name_allocation_is_unique_stable_and_does_not_reset_for_each_household(seed):
    def cast(count):
        used = set()
        return [resident_identity(seed, i, used, family_identity(seed, "family-1") if i < 3 else None)
                for i in range(count)]
    first = cast(1000)
    assert len({name.casefold() for name, _ in first}) == 1000
    assert first == cast(1000)
    assert first[:300] == cast(300)
    assert len({identity["family_name"] for _, identity in first[:3]}) == 1
    assert len({identity["given_name"] for _, identity in first[:3]}) == 3
    for name, identity in first:
        assert name == f"{identity['given_name']} {identity['family_name']}"
        assert identity["source"] == "authored_fictional"
        assert identity["version"] == IDENTITY_VERSION
        assert identity["given_name"] in NAME_STYLES[identity["given_name_style"]]["given"]


def test_cross_cultural_preferred_names_remain_possible_and_do_not_determine_skin():
    identities = [resident_identity(42, i, set(), ("south_asian", "Patel"))[1] for i in range(1000)]
    preferred = [i for i, identity in enumerate(identities) if identity["given_name_style"] == "english_language"]
    assert 40 < len(preferred) < 120
    assert len({appearance(42, i)["skin"] for i in preferred}) == 8
    # The name generator has no appearance argument, and it cannot mutate the
    # separate seeded art recipe just by choosing a different naming style.
    before = appearance(42, 7)
    resident_identity(42, 7, set(), ("korean_romanized", "Park"))
    assert before == appearance(42, 7)


def test_hair_palette_is_age_aware_and_dyed_color_is_an_occasional_style_choice():
    children = [appearance(91, i, "child") for i in range(2000)]
    adults = [appearance(91, i) for i in range(2000)]
    older = [appearance(91, i, "older") for i in range(2000)]
    assert all(look["hair"] < 6 for look in children)
    assert {look["hair"] for look in children} == set(range(6))
    assert 20 < sum(look["hair"] == 7 for look in adults) < 80
    assert sum(look["hair"] < 6 for look in adults) > 1800
    assert 1300 < sum(look["hair"] == 6 for look in older) < 1550


def test_family_art_uses_its_own_household_seed_and_preserves_mobility_sampling():
    for seed in (7, 42, 109):
        for household in range(25):
            ids = [household*3+i for i in range(3)]
            looks = [appearance(seed, resident, "child" if i == 2 else "adult", family_id=f"family-{household}")
                     for i, resident in enumerate(ids)]
            assert max(look["skin"] for look in looks)-min(look["skin"] for look in looks) <= 2
            for i, resident in enumerate(ids):
                expected = "wheelchair" if i != 2 and uniform(seed, "appearance", resident, "mobility") < .035 else "walk"
                assert looks[i]["mobility"] == expected
            assert looks[2]["hair"] < 6


def test_current_campus_profiles_have_unique_names_and_saved_coherent_identity():
    profiles, households = make_campus_profiles(300, 42, make_campus_city())
    assert len({profile["name"].casefold() for profile in profiles}) == 300
    families = [household for household in households if household["type"] == "family"]
    assert len(families) == 2
    for household in families:
        members = [profiles[i] for i in household["members"]]
        assert len({p["identity"]["family_name"] for p in members}) == 1
        assert len({p["identity"]["given_name"] for p in members}) == len(members)
        assert max(p["appearance"]["skin"] for p in members)-min(p["appearance"]["skin"] for p in members) <= 2
    for profile in profiles:
        assert profile["biography"] and len(profile["biography"]) < 200
        assert profile["identity"]["source"] == "authored_fictional"
        assert profile["appearance"] == appearance(42, profile["id"], profile["age"], profile["role"],
                                                   profile["household_id"] if profile["household_type"] == "family" else None)


def test_display_identity_never_enters_the_operational_decision_context():
    sim = CampusSimulation(ScenarioConfig(layout="campus", population=10, duration_ticks=12, decision_mode="rules"),
                           WarningConfig(name="Exercise", text="Simulation: seek shelter."))
    person, meta = sim.life.people[0], sim.meta[0]
    before = copy.deepcopy(sim.context(person, meta))
    assert before["town_life"]["name"] == "Resident 1"
    profile = sim.life.profiles[0]
    profile.update(name="A Different Fictional Name", identity={"naming_style": "different"}, biography="A different biography.")
    profile["appearance"].update(skin=7, hair=7)
    assert sim.context(person, meta) == before
    assert not {"identity", "appearance", "biography", "naming_style"}.intersection(before["town_life"])
