"""Contract tests: every registered source exposes a sane schema()."""
from cti import registry

STATES = registry.discover()


def test_at_least_the_core_sources_registered():
    ids = set(STATES)
    assert {"bgp", "rootmon", "shodan", "netlas", "atera", "cloud_status",
            "assets", "correlation", "news_feed", "acn_misp"} <= ids


_WIDGET_SOURCES = {"intel", "providerbar", "feeds"}


def test_every_source_schema_is_valid():
    for sid, st in STATES.items():
        sch = st.module.schema()
        assert isinstance(sch, dict), sid
        assert sch.get("title"), f"{sid} schema missing title"

        widget = sch.get("widget")
        if widget in _WIDGET_SOURCES:
            # widget-based sources render through dedicated JS renderers,
            # not via the generic table builder — no table/sections required
            continue

        # non-widget sources must describe rows via table or sections
        has_table = "table" in sch
        has_sections = "sections" in sch
        assert has_table or has_sections, f"{sid} schema has no table/sections"
        tables = [sch["table"]] if has_table else [s["table"] for s in sch["sections"]]
        for t in tables:
            assert "rows_key" in t and "columns" in t, sid
            for col in t["columns"]:
                assert "key" in col and "label" in col, sid


def test_every_source_has_fetch_parse():
    for sid, st in STATES.items():
        assert callable(getattr(st.module, "fetch", None)), sid
        assert callable(getattr(st.module, "parse", None)), sid
