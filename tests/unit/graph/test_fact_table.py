from src.graph.nodes import finalizer


def test_build_fact_table_verified_only_when_official_present():
    timeline = [
        {"date": "2025-08-07", "title": "OpenAI blog announces GPT-5", "source": "https://openai.com/blog/gpt-5"},
        {"date": "2025-08-08", "title": "Tech blog repeats rumor", "source": "https://techcrunch.com/gpt5"},
    ]
    conflicts = [
        {"topic": "GPT-5 release date", "verdict": "Date unclear"}
    ]

    # With official present, only official entry becomes verified
    facts = finalizer._build_fact_table(timeline, conflicts, ["https://openai.com/blog/gpt-5"])
    assert any("OpenAI blog" in f["fact"] for f in facts["verified"])
    assert all("OpenAI blog" not in f["fact"] for f in facts["unverified"])
    assert any("Conflict resolution" in f["fact"] for f in facts["unverified"])

    # Without official, everything is unverified
    facts2 = finalizer._build_fact_table(timeline, conflicts, [])
    assert not facts2["verified"]
    assert len(facts2["unverified"]) == 3  # two timeline + one conflict
