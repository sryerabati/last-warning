from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class ScenarioConfig(StrictModel):
    name: str = Field(default="Riverside", min_length=1, max_length=100)
    population: int = Field(default=300, ge=10, le=1000)
    seed: int = Field(default=42, ge=0, le=2**32 - 1)
    duration_ticks: int = Field(default=120, ge=12, le=360)
    tick_seconds: int = Field(default=5, ge=1, le=120)
    disaster_type: Literal["flood", "wildfire", "tornado", "blizzard", "hailstorm", "thunderstorm", "public_safety"] = "flood"
    decision_mode: Literal["rules", "bedrock"] = "rules"
    layout: Literal["grid", "organic", "campus"] = "grid"
    town_life: bool = False
    campus_day_type: Literal["teaching", "weekend", "class_break", "closed"] = "teaching"
    transit_enabled: bool = True
    town_start_tick: int = Field(default=0, ge=0, le=287)
    town_start_minutes: float | None = Field(default=None, ge=0, lt=1440)
    hazard_origin: tuple[int, int] = (19, 4)
    hazard_spread: float = Field(default=1.0, ge=0.1, le=3)

    @model_validator(mode="before")
    @classmethod
    def origin_for_disaster(cls, value: Any):
        if isinstance(value, dict):
            value = dict(value)
            if value.get("layout") == "campus":
                from .simulation.campus_world import DEFAULT_ORIGINS

                kind = value.get("disaster_type", "flood")
                value.setdefault("tick_seconds", {"blizzard": 120, "hailstorm": 30,
                                                   "thunderstorm": 30, "public_safety": 10}.get(kind, 5))
                value.setdefault("hazard_origin", DEFAULT_ORIGINS.get(kind, DEFAULT_ORIGINS["flood"]))
            if "hazard_origin" not in value:
                value["hazard_origin"] = {
                    "flood": (19, 4), "wildfire": (6, 12), "tornado": (3, 35),
                }.get(value.get("disaster_type", "flood"), (19, 4))
        return value

    @model_validator(mode="after")
    def valid_origin(self):
        if self.town_life and self.layout not in {"organic", "campus"}:
            raise ValueError("Town life requires the organic town or campus layout")
        from .simulation.campus_world import CAMPUS_SIZE

        size = CAMPUS_SIZE if self.layout == "campus" else 40
        if not all(0 <= v < size for v in self.hazard_origin):
            raise ValueError(f"Hazard origin must be inside the {size} × {size} city")
        if self.layout == "campus":
            if self.disaster_type == "blizzard" and self.duration_ticks * self.tick_seconds < 10800:
                raise ValueError("A campus blizzard scenario must span at least 3 simulated hours (10800 seconds)")
            if self.disaster_type in {"thunderstorm", "hailstorm"} and self.duration_ticks * self.tick_seconds < 3600:
                raise ValueError("Campus thunderstorm and hail scenarios need 1 simulated hour to include the lightning shelter hold")
            return self
        if self.tick_seconds > 30:
            raise ValueError("Legacy town scenarios support at most 30 seconds per tick")
        if self.disaster_type not in {"flood", "wildfire", "tornado"}:
            raise ValueError("The new weather and public-safety scenarios require the campus layout")
        if self.hazard_origin in {(3, 3), (37, 37)}:
            raise ValueError("Hazard origin cannot be a designated refuge")
        from .simulation.geometry import river_cells

        if self.disaster_type == "wildfire" and self.hazard_origin in river_cells(self.layout):
            raise ValueError("Wildfire ignition must be on land, outside the river")
        if self.disaster_type == "tornado" and self.hazard_origin in {
            (9, 9), (9, 27), (15, 15), (27, 9), (27, 27), (33, 21),
        }:
            raise ValueError("Hazard origin cannot be a designated storm shelter")
        return self


class WarningConfig(StrictModel):
    name: str = Field(min_length=1, max_length=100)
    text: str = Field(min_length=1, max_length=5000)
    delivery_reach_probability: float = Field(default=0.8, ge=0, le=1)
    notice_probability: float = Field(default=0.65, ge=0, le=1)
    action_probability: float = Field(default=0.6, ge=0, le=1)
    response_delay: int = Field(default=10, ge=0, le=120, description="Ticks before preparation")
    social_share_probability: float = Field(default=0.35, ge=0, le=1)
    broadcast_tick: int = Field(default=0, ge=0, le=360)
    broadcast_seconds: float | None = Field(default=None, ge=0, le=43200)
    preparation_seconds: float | None = Field(default=None, ge=0, le=3600)
    channels: list[Literal["mobile", "siren", "social"]] = Field(default_factory=lambda: ["mobile", "social"])

    @model_validator(mode="after")
    def unique_channels(self):
        if len(set(self.channels)) != len(self.channels):
            raise ValueError("Delivery channels must be unique")
        return self


class RunRequest(StrictModel):
    scenario_id: str
    warning_id: str
    baseline_run_id: str | None = None
    neural_analysis_id: str | None = None
    coupling_strength: float = Field(default=0, ge=-1, le=1)


class RunJobRequest(RunRequest):
    idempotency_key: str = Field(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$")
    analyze_warning: bool = False


class ComparisonRequest(StrictModel):
    baseline_run_id: str
    alternative_run_id: str


class NeuralCompareRequest(StrictModel):
    baseline_analysis_id: str
    alternative_analysis_id: str


class LocalInferenceRequest(StrictModel):
    stimulus_id: str


GENERIC = WarningConfig(
    name="Generic advisory",
    text="Flooding is possible in your area. Stay informed and exercise caution.",
    delivery_reach_probability=0.7, notice_probability=0.48, action_probability=0.42,
    response_delay=14, social_share_probability=0.25,
)
ACTIONABLE = WarningConfig(
    name="Actionable warning",
    text="FLASH FLOOD WARNING: North District. Move to high ground now. Avoid Riverside Road and follow marked evacuation routes.",
    delivery_reach_probability=0.9, notice_probability=0.9, action_probability=0.86,
    response_delay=3, social_share_probability=0.7,
    channels=["mobile", "siren", "social"],
)
