def test_engine_contract_fields_are_supported_when_installed():
    from app.analysis.service import engine_request
    from app.assets.models import Asset
    request = engine_request(Asset(id="a", name="Pump", asset_type="pump", criticality="medium", specs_json={}), [], [], {}, "ok", "starter")
    assert request.tier.value == "starter"
    assert request.asset.id == "a"
