from app.agents.pathway_ext_agent import _entry_count


def test_entry_count_handles_current_reactome_list_schema():
    assert _entry_count({"entries": [{"dbId": 1}, {"dbId": 2}]}) == 2


def test_entry_count_handles_numeric_and_missing_schema_variants():
    assert _entry_count({"entries": 3}) == 3
    assert _entry_count({"entries": 2.0}) == 2
    assert _entry_count({}) == 0
    assert _entry_count({"entries": None}) == 0
    assert _entry_count({"entries": "3"}) == 0
