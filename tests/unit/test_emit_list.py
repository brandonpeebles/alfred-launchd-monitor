from launchd_monitor import Config, JobRecord, emit_list


def _rec(label="com.brandon.job"):
    return JobRecord(label, None, 4821, 0, True, False, None, None)


def test_emit_list_item_shape():
    out = emit_list([_rec()], Config.from_env({}))
    item = out["items"][0]
    assert item["title"] == "com.brandon.job"
    assert item["arg"] == "com.brandon.job"
    assert item["valid"] is True
    assert item["mods"]["cmd"]["arg"] == "restart:com.brandon.job"
    assert item["mods"]["alt"]["arg"] == "tail-term:com.brandon.job"
    assert item["mods"]["ctrl"]["arg"] == "peek:com.brandon.job"


def test_emit_list_empty_returns_placeholder():
    out = emit_list([], Config.from_env({"LABEL_GLOB": "com.nope.*"}))
    assert len(out["items"]) == 1
    only = out["items"][0]
    assert only["valid"] is False
    assert "com.nope.*" in only["title"]
