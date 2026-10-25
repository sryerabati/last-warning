"""Authored educational campus scenarios; matched delivery isolates warning wording."""
from .schemas import GENERIC, ScenarioConfig
from .simulation.campus_world import DEFAULT_ORIGINS

CAMPUS_SCENARIO = {"name": "Ohio State · Campus & neighborhood", "population": 300, "seed": 42,
                   "layout": "campus", "town_life": True, "town_start_tick": 140,
                   "town_start_minutes": 700, "disaster_type": "thunderstorm",
                   "decision_mode": "bedrock", "duration_ticks": 120, "tick_seconds": 30,
                   "hazard_origin": DEFAULT_ORIGINS["thunderstorm"], "hazard_spread": 1}

# These messages belong to a simulation, not to the university's alert service.
MESSAGES = {
    "flood": ("Flood advisory", "Simulation: Flooding is developing near Mirror Lake. Stay informed and use caution.",
              "Flood safety warning", "SIMULATION — FLOOD WARNING near Mirror Lake. Leave low ground and move away from the affected area along open paths. Do not walk or drive through floodwater. Help household members reach a dry indoor location and monitor updates."),
    "wildfire": ("Fire advisory", "Simulation: An outdoor fire is affecting part of the academic core. Stay informed and use caution.",
                 "Fire evacuation warning", "SIMULATION — OUTDOOR FIRE. Leave the marked affected area using an open route away from fire and smoke. Keep your household together. Do not cross burning or closed paths. Follow updates before returning."),
    "tornado": ("Tornado advisory", "Simulation: A tornado is approaching the academic core. Stay informed and use caution.",
                "Tornado shelter warning", "SIMULATION — TORNADO WARNING. Enter a substantial building immediately. Move to an interior room on the lowest available floor, away from windows. Do not try to outrun the storm in a car. Remain sheltered until the all-clear."),
    "blizzard": ("Winter weather advisory", "Simulation: A blizzard is expected across the academic core for several hours. Stay informed and use caution.",
                 "Blizzard shelter warning", "SIMULATION — BLIZZARD WARNING. Strong winds, blowing snow and very low visibility will persist for several hours. Stay inside a warm building. Postpone nonessential trips and avoid driving. Check on household members by phone. Follow updates before leaving shelter."),
    "hailstorm": ("Hail advisory", "Simulation: A hailstorm is moving across the academic core. Stay informed and use caution.",
                  "Hail shelter warning", "SIMULATION — HAILSTORM. Move into a substantial building immediately and stay away from windows. Leave outdoor gathering places; do not shelter under trees. Avoid unnecessary driving. Remain indoors for at least 30 minutes after the last thunder."),
    "thunderstorm": ("Severe storm advisory", "Simulation: A very severe thunderstorm is moving toward the academic core. Stay informed and use caution.",
                     "Severe storm shelter warning", "SIMULATION — DESTRUCTIVE THUNDERSTORM. Dangerous winds, large hail and lightning are approaching. Go inside a substantial building now. Move away from windows and avoid trees and open ground. Check that your household has shelter. Stay indoors for at least 30 minutes after the last thunder."),
    "public_safety": ("Public safety advisory", "Simulation: A major public safety threat affects the marked area of the academic core. Stay informed and use caution.",
                      "Public safety instructions", "SIMULATION — MAJOR PUBLIC SAFETY THREAT. Avoid the marked restricted area. If already inside a nearby building, remain indoors and follow the simulated protective instructions. If outside, use an open route away from the affected area. Contact household members remotely. Do not return until the all-clear."),
}


def campus_seed_records():
    yield "scenarios", "osu-campus", ScenarioConfig(**CAMPUS_SCENARIO).model_dump(mode="json")
    for hazard, (generic_name, generic_text, clear_name, clear_text) in MESSAGES.items():
        for mode, name, text in (("generic", generic_name, generic_text), ("actionable", clear_name, clear_text)):
            yield "warnings", f"campus-{mode}-{hazard}", {
                **GENERIC.model_dump(mode="json"), "name": name, "text": text,
                "delivery_reach_probability": .92, "notice_probability": .85,
                "action_probability": .75, "response_delay": 1,
                "social_share_probability": .2, "broadcast_tick": 0,
                "channels": ["mobile", "social"],
            }
