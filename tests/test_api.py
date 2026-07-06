from src.clinicaltrials_client import TRIAL_FIELDS, search_trials


class FakeResponse:
    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return {"studies": [{"protocolSection": {}}]}


def test_search_trials_sends_recruiting_filter_and_fields(monkeypatch) -> None:
    captured = {}

    def fake_get(url: str, params: dict, timeout: int) -> FakeResponse:
        captured["url"] = url
        captured["params"] = params
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("src.clinicaltrials_client.requests.get", fake_get)

    studies = search_trials("breast cancer", country="Denmark", page_size=200)

    assert studies == [{"protocolSection": {}}]
    assert captured["params"]["query.cond"] == "breast cancer"
    assert captured["params"]["filter.overallStatus"] == "RECRUITING"
    assert captured["params"]["filter.advanced"] == 'AREA[LocationCountry]"Denmark"'
    assert captured["params"]["pageSize"] == 100
    assert captured["params"]["fields"] == ",".join(TRIAL_FIELDS)
    assert captured["timeout"] == 20
