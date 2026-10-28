from datagen import geo


def test_ten_regions_with_contract_codes():
    codes = [r["code"] for r in geo.REGIONS]
    assert codes == [
        "NORTH", "NORTH_WEST", "CENTRAL", "WEST", "WEST_CENTRAL",
        "SOUTH_WEST", "SOUTH", "SOUTH_CENTRAL", "EAST", "NORTH_EAST",
    ]  # fmt: skip
    west = next(r for r in geo.REGIONS if r["code"] == "WEST")
    assert west == {"code": "WEST", "name": "Western", "hq_city": "Mumbai"}


def test_states_map_to_contract_regions():
    assert geo.REGION_OF_STATE["MH"] == "WEST"
    assert geo.REGION_OF_STATE["TN"] == "SOUTH"
    assert geo.REGION_OF_STATE["GJ"] == "WEST_CENTRAL"
    assert geo.REGION_OF_STATE["RJ"] == "WEST_CENTRAL"
    assert geo.REGION_OF_STATE["DL"] == "NORTH_WEST"
    assert geo.REGION_OF_STATE["TR"] == "NORTH_EAST"
    assert len(geo.STATES) == 36
    assert len({s["code"] for s in geo.STATES}) == 36
    region_codes = {r["code"] for r in geo.REGIONS}
    assert all(s["region"] in region_codes for s in geo.STATES)


def test_demo_university_is_mstu():
    unis = geo.universities()
    mstu = next(u for u in unis if u["code"] == "MSTU")
    assert mstu["name"] == "Maharashtra State Technical University"
    assert mstu["state_code"] == "MH"
    assert len({u["code"] for u in unis}) == len(unis)
    assert {u["state_code"] for u in unis} == {s["code"] for s in geo.STATES}


def test_every_state_has_a_profile_and_exam():
    for s in geo.STATES:
        profile = geo.state_profile(s["code"])
        assert profile["cities"]
        assert abs(sum(profile["groups"].values()) - 1.0) < 1e-6
        assert geo.exam_for_state(s["code"])
    assert geo.exam_for_state("MH") == "MHCET"
