import os

from cti import config


def test_expand_env(monkeypatch):
    monkeypatch.setenv("FOO_KEY", "secret123")
    out = config._expand({"a": "${FOO_KEY}", "b": ["${FOO_KEY}", "x"], "c": 5})
    assert out == {"a": "secret123", "b": ["secret123", "x"], "c": 5}


def test_expand_missing_env_is_empty(monkeypatch):
    monkeypatch.delenv("MISSING_XYZ", raising=False)
    assert config._expand("${MISSING_XYZ}") == ""


def test_source_cfg_defaults():
    cfg = {"sources": {"bgp": {"enabled": True, "interval": 900}}}
    assert config.source_cfg(cfg, "bgp")["interval"] == 900
    assert config.source_cfg(cfg, "absent") == {}
    assert config.source_cfg({}, "x") == {}
