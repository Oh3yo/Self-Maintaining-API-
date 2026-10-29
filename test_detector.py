import json

import detector as d


def spec(**over):
    base = {
        "openapi": "3.0.3",
        "info": {"title": "t", "version": "1.0"},
        "paths": {
            "/users": {
                "post": {
                    "operationId": "createUser",
                    "requestBody": {"required": True, "content": {"application/json": {
                        "schema": {"$ref": "#/components/schemas/NewUser"}}}},
                    "responses": {"201": {"description": "ok", "content": {"application/json": {
                        "schema": {"$ref": "#/components/schemas/User"}}}}},
                },
                "get": {"parameters": [{"name": "limit", "in": "query", "schema": {"type": "integer"}}],
                        "responses": {"200": {"description": "ok"}}},
            },
            "/users/{id}": {"delete": {"responses": {"204": {"description": "gone"}}}},
        },
        "components": {"schemas": {
            "NewUser": {"type": "object", "required": ["email"],
                        "properties": {"email": {"type": "string"},
                                       "role": {"type": "string", "enum": ["admin", "user"]}}},
            "User": {"type": "object", "required": ["id"],
                     "properties": {"id": {"type": "integer"}, "email": {"type": "string"},
                                    "friends": {"type": "array", "items": {"$ref": "#/components/schemas/User"}}}},
        }},
    }
    base.update(over)
    return base


def kinds(changes, severity=None):
    return {c.kind for c in changes if severity is None or c.severity == severity}


def test_identical_specs_have_no_changes():
    assert d.diff_openapi("x", spec(), spec()) == []


def test_removed_operation_and_path_are_breaking():
    new = spec()
    del new["paths"]["/users"]["get"]
    del new["paths"]["/users/{id}"]
    ch = d.diff_openapi("x", spec(), new)
    assert {"operation_removed", "path_removed"} <= kinds(ch, "breaking")


def test_path_param_rename_is_not_a_removal():
    new = spec()
    new["paths"]["/users/{userId}"] = new["paths"].pop("/users/{id}")
    ch = d.diff_openapi("x", spec(), new)
    assert "path_removed" not in kinds(ch)
    assert "path_param_renamed" in kinds(ch, "info")


def test_request_schema_rules():
    new = spec()
    s = new["components"]["schemas"]["NewUser"]
    s["required"].append("name")                       # new required prop
    s["properties"]["name"] = {"type": "string"}
    s["properties"]["email"] = {"type": "integer"}     # incompatible type
    s["properties"]["role"]["enum"] = ["admin"]        # enum value removed
    ch = d.diff_openapi("x", spec(), new)
    assert {"required_property_added", "type_changed", "enum_value_removed"} <= kinds(ch, "breaking")


def test_response_property_removed_and_type_changed_are_breaking():
    new = spec()
    u = new["components"]["schemas"]["User"]
    del u["properties"]["email"]
    u["properties"]["id"] = {"type": "string"}
    ch = d.diff_openapi("x", spec(), new)
    assert {"property_removed", "type_changed"} <= kinds(ch, "breaking")


def test_recursive_schema_does_not_hang_and_nested_change_found():
    new = spec()
    # change inside the recursive User.friends[] should still be detected at least once
    new["components"]["schemas"]["User"]["properties"]["id"] = {"type": "string"}
    ch = d.diff_openapi("x", spec(), new)
    assert any("friends[]" in c.location for c in ch) or any(c.kind == "type_changed" for c in ch)


def test_optional_param_added_is_info_required_is_breaking():
    new = spec()
    new["paths"]["/users"]["get"]["parameters"] += [
        {"name": "q", "in": "query", "schema": {"type": "string"}},
        {"name": "tenant", "in": "header", "required": True, "schema": {"type": "string"}},
    ]
    ch = d.diff_openapi("x", spec(), new)
    assert "parameter_added" in kinds(ch, "info")
    assert "required_parameter_added" in kinds(ch, "breaking")


def test_auth_added_is_breaking():
    new = spec(security=[{"apiKey": []}])
    assert "auth_added" in kinds(d.diff_openapi("x", spec(), new), "breaking")


def test_widening_request_type_is_not_breaking():
    old, new = spec(), spec()
    old["components"]["schemas"]["NewUser"]["properties"]["role"] = {"type": "integer"}
    new["components"]["schemas"]["NewUser"]["properties"]["role"] = {"type": "number"}
    assert "type_changed" not in kinds(d.diff_openapi("x", old, new), "breaking")


def test_swagger2_rejected():
    try:
        d.parse_spec(json.dumps({"swagger": "2.0"}))
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def test_changelog_flags_breaking_and_deprecation():
    old = "# Changelog\n- 1.0 added foo\n"
    new = ("# Changelog\n- 1.1 BREAKING: removed the /v1/charges endpoint\n"
           "- 1.1 deprecated `source` parameter\n- 1.1 added bar\n- 1.0 added foo\n")
    ch = d.diff_changelog("x", old, new)
    assert [c.severity for c in ch] == ["breaking", "warning"]


def test_changelog_html_noise_ignored():
    old = "<html><body><h1>Log</h1><p>one</p></body></html>"
    assert d.diff_changelog("x", old, old) == []


def test_sdk_versions():
    assert d.diff_sdk("x", "pypi", "1.2.3", "2.0.0")[0].severity == "breaking"
    assert d.diff_sdk("x", "pypi", "1.2.3", "1.3.0")[0].severity == "info"
    assert d.diff_sdk("x", "pypi", "0.4.1", "0.5.0")[0].severity == "warning"
    assert d.diff_sdk("x", "pypi", "1.2.3", "1.2.3") == []


def test_end_to_end_baseline_then_change(tmp_path):
    v1, v2 = tmp_path / "v1.json", tmp_path / "spec.json"
    v2.write_text(json.dumps(spec()))
    cfg = {"state_dir": str(tmp_path / "state"),
           "apis": [{"name": "demo", "sources": [{"type": "openapi", "url": str(v2)}]}]}

    r1 = d.run_once(cfg)
    assert r1["results"][0]["status"] == "baseline" and r1["summary"]["breaking"] == 0

    assert d.run_once(cfg)["results"][0]["status"] == "unchanged"

    changed = spec()
    del changed["paths"]["/users"]["get"]
    v2.write_text(json.dumps(changed))
    r3 = d.run_once(cfg)
    assert r3["results"][0]["status"] == "changed"
    assert r3["summary"]["breaking"] >= 1

    # new snapshot is now the baseline, and the old one was archived
    assert d.run_once(cfg)["results"][0]["status"] == "unchanged"
    assert list((tmp_path / "state" / "demo" / "archive").iterdir())


def test_broken_source_is_isolated(tmp_path):
    cfg = {"state_dir": str(tmp_path / "s"), "apis": [{"name": "a", "sources": [
        {"type": "openapi", "url": str(tmp_path / "missing.json")}]}]}
    r = d.run_once(cfg)
    assert r["results"][0]["status"] == "error" and r["summary"]["errors"] == 1
