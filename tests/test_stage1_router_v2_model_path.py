from pathlib import Path

from orchestration.stage1 import _router_v2_model_path


def test_explicit_router_v2_model_path_wins(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("KG_G5_ROUTER_V2_MODEL", "env-router.json")

    assert _router_v2_model_path("explicit-router.json") == (
        "explicit-router.json"
    )


def test_env_router_v2_model_path_wins(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("KG_G5_ROUTER_V2_MODEL", "env-router.json")

    assert _router_v2_model_path(None) == "env-router.json"


def test_default_router_v2_model_path_is_used_when_present(
    monkeypatch,
    tmp_path,
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("KG_G5_ROUTER_V2_MODEL", raising=False)
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    (outputs / "router_v2.json").write_text("{}", encoding="utf-8")

    assert Path(_router_v2_model_path(None)) == Path("outputs") / "router_v2.json"


def test_packaged_router_v2_model_path_is_used_as_fallback(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("KG_G5_ROUTER_V2_MODEL", raising=False)

    assert Path(_router_v2_model_path(None)).parts[-2:] == ("orchestration", "router_v2.json")
