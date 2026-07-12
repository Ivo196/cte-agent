from src import profile_extractor


def test_profile_prompt_includes_subtype_and_treatment_timing(monkeypatch) -> None:
    captured = {}

    def fake_ask_json(prompt: str) -> dict:
        captured["prompt"] = prompt
        return {"condition": "breast cancer"}

    monkeypatch.setattr(profile_extractor, "ask_json", fake_ask_json)

    profile_extractor.extract_patient_profile("HER2-positive breast cancer")

    assert '"cancer_subtype"' in captured["prompt"]
    assert '"disease_status"' in captured["prompt"]
    assert '"treatment_timing"' in captured["prompt"]
