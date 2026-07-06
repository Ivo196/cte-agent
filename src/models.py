from pydantic import BaseModel, Field


class PatientProfile(BaseModel):
    age: int | None = None
    sex: str | None = None
    condition: str | None = None
    disease_stage: str | None = None
    prior_treatments: list[str] = Field(default_factory=list)
    biomarkers: list[str] = Field(default_factory=list)
    country: str | None = None
    travel_preference: str | None = None


class SemanticMatchResult(BaseModel):
    label: str
    reason: str
    missing_information: list[str] = Field(default_factory=list)
