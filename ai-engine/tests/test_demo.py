from src import demo


def test_demo_fixture_uses_one_factory_for_ingest_and_request(monkeypatch):
    calls = []
    monkeypatch.setattr(
        demo.knowledge,
        "ingest",
        lambda document, **kwargs: calls.append((document.factory_id, kwargs["factory_id"])),
    )

    request = demo.fixture_request()

    assert calls == [("demo-factory", "demo-factory")]
    assert request.factory_id == "demo-factory"
