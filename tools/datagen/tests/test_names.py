import random

from datagen import names


def test_initials_variant():
    assert names.with_initials("Ravi Kumar Sharma") == "R. K. Sharma"
    assert names.with_initials("Priya Patil") == "P. Patil"
    assert names.with_initials("Karthik") == "Karthik"


def test_transliteration_variant_changes_spelling_but_keeps_shape():
    v = names.transliteration_variant("Deepak Sharma")
    assert v != "Deepak Sharma"
    assert len(v.split()) == 2
    assert v.split()[0].lower() in {"dipak", "deepak"}
    assert names.devanagari("Sharma").startswith("श")
    # Names that survive the round trip still get a variant.
    assert names.transliteration_variant("Ravi Kumar") != "Ravi Kumar"


def test_mohd_variants():
    rng = random.Random(1)
    v = names.mohd_variant("Mohammed Irfan Khan", rng)
    assert v != "Mohammed Irfan Khan"
    assert v.endswith("Irfan Khan")
    assert v.split()[0] in {"Mohammad", "Muhammad", "Mohd", "Md", "Md."}
    v2 = names.mohd_variant("Irfan Khan", rng)
    assert v2.split()[0] in {"Mohd", "Md", "Md."}


def test_generator_is_deterministic_and_regional():
    a = names.NameGenerator(random.Random(7))
    b = names.NameGenerator(random.Random(7))
    seq_a = [a.indian_name("marathi", "M") for _ in range(20)]
    seq_b = [b.indian_name("marathi", "M") for _ in range(20)]
    assert seq_a == seq_b
    surnames = {n.split()[-1] for n in seq_a}
    assert surnames & {"Patil", "Deshmukh", "Jadhav", "Kulkarni", "Joshi", "Shinde", "Pawar",
                       "More", "Gaikwad", "Bhosale", "Chavan", "Sawant", "Kadam", "Mane"}
    assert all(len(n.split()) >= 2 for n in seq_a)
    bengali = a.indian_name("bengali", "F")
    assert bengali.split()[-1] in names.load_data("names.json")["groups"]["bengali"]["surnames"]
    intl = a.international_name("BD", "F")
    assert intl


def test_every_group_has_names():
    data = names.load_data("names.json")["groups"]
    for g in names.GROUPS:
        assert len(data[g]["M"]) >= 25
        assert len(data[g]["F"]) >= 25
        assert len(data[g]["surnames"]) >= 15


def test_materially_different_name_shares_no_first_name():
    gen = names.NameGenerator(random.Random(3))
    other = names.materially_different("Priya Sharma", gen, "hindi", "F")
    assert other.split()[0] != "Priya"


def test_renamed_variants_keep_the_blocking_key():
    from datagen.matching import name_key

    gen = names.NameGenerator(random.Random(11))
    for group in names.GROUPS:
        for gender in ("M", "F"):
            for _ in range(15):
                name = gen.indian_name(group, gender)
                for variant in (names.with_initials(name), names.transliteration_variant(name)):
                    assert variant != name
                    assert name_key(variant, "2007-03-21") == name_key(name, "2007-03-21"), (
                        name, variant,
                    )  # fmt: skip


def test_materially_different_scores_below_review():
    from datagen.matching import registry_score

    gen = names.NameGenerator(random.Random(5))
    for group in names.GROUPS:
        name = gen.indian_name(group, "M")
        other = names.materially_different(name, gen, group, "M")
        assert registry_score(name, other) < 75
