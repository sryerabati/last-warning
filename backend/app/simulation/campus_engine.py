"""Recorded campus emergencies: Bedrock intentions, authoritative local motion.

The geometry is sourced; weather profiles, household agendas and response
parameters are educational assumptions, not calibrated forecasts of real people.
"""
from __future__ import annotations

import copy
import hashlib
import heapq
import json
import math
from bisect import bisect_right
from collections import Counter
from itertools import pairwise

from ..bedrock import CAMPUS_ACTIONS
from .campus_hazards import CampusHazard
from .world import uniform

VERSION = "last-warning-campus/3.1"
STATES = ["UNAWARE", "ALERTED", "DECIDING", "PREPARING", "EVACUATING", "SHELTERED", "STRANDED", "EXPOSED"]
DECISION_SECONDS = (10, 40, 120, 280, 480)
# Existing warning tick fields are interpreted at the historical 5-second
# reference interval for new campus runs; old saved recordings are unchanged.
LEGACY_WARNING_SECONDS = 5


class CampusSimulation:
    def __init__(self, config, warning, notice_adjustment=0, decision_policy=None,
                 progress_callback=None, cancel_check=None):
        from .campus_life import CampusLife

        if config.decision_mode == "bedrock" and decision_policy is None:
            raise ValueError("Bedrock campus residents require an available model policy; no rule fallback is used")
        if config.decision_mode == "bedrock" and notice_adjustment:
            raise ValueError("TRIBE notice-probability coupling is only supported in rules mode")
        self.config, self.warning = config, warning
        self.policy = decision_policy if config.decision_mode == "bedrock" else None
        self.progress_callback, self.cancel_check = progress_callback, cancel_check
        self.notice_adjustment = notice_adjustment
        start = config.town_start_minutes if config.town_start_minutes is not None else config.town_start_tick * 5
        self.life = CampusLife(config.population, config.seed, start_minute=start,
                               campus_day_type=config.campus_day_type, transit_enabled=config.transit_enabled)
        self.city = self.life.city
        for profile in self.life.profiles:
            i = profile["id"]
            profile["response_timing_seconds"] = {
                "mobile": 5+int(11*self.draw("campus-mobile-delay", i)),
                "attention": 5+int(16*self.draw("campus-attention-delay", i)),
                "observation": 2+int(6*self.draw("campus-observation-delay", i)),
                "siren": 5, "social": 5,
            }
        self.places = {p["id"]: p for p in self.city.places}
        self.hazard = CampusHazard(self.city, config)
        self.hazard.step(0)
        self.blocked = lambda position: self.hazard.blocked(position)
        if config.disaster_type == "public_safety":
            # Generic avoidance zones permit monotonic egress. Flood/fire masks
            # stay conservative: danger is not made traversable to find a route.
            self.blocked.egress_score = lambda point: max(0., self.hazard.radius-math.dist(point, self.hazard.center)) if self.hazard.active else 0.
        self.tick = 0
        self._seconds = None
        self.life_origin_seconds = self.life.elapsed_seconds
        self.broadcast_at = (warning.broadcast_seconds if warning.broadcast_seconds is not None
                             else warning.broadcast_tick*LEGACY_WARNING_SECONDS)
        self.preparation_seconds = (warning.preparation_seconds if warning.preparation_seconds is not None
                                    else warning.response_delay*LEGACY_WARNING_SECONDS)
        self.broadcast_sent = False
        self.decision_anchor = self.broadcast_at
        self.base_rounds_completed = set()
        self.decision_times = []
        self.impact_history = []
        self.current_impacts = {}
        self.vehicle_impact_history = []
        self.vehicle_contacts = {}
        self._contact_sequence = 0
        self.events, self.frames, self.rounds, self.messages = [], [], [], []
        self.meta = [{"received": False, "noticed": False, "receipt_tick": None,
                      "notice_tick": None, "start_tick": None, "safe_tick": None,
                      "exposure": 0., "state": "UNAWARE", "action": None, "shared": False,
                      "decisions": [], "danger_seen": False, "target": None,
                      "clear_received": False, "attempted": False, "reroutes": 0, "unmet_need": False,
                      "latest_update": None, "siren_heard": False, "siren_tick": None,
                      "receipt_seconds": None, "notice_seconds": None, "start_seconds": None, "safe_seconds": None,
                      "siren_seconds": None, "observed_seconds": None, "contact": False, "contact_count": 0}
                     for _ in self.life.people]
        self.clear_sent = False
        self.update_sent = False
        self.update_delivered_this_tick = False
        self.route_cache = {}
        self.reservations = {}  # unit id -> destination, retained until released or superseded
        self.initial_conditions = {
            "configuration": config.model_dump(mode="json"),
            "world_version": self.city.serialize().get("world_version"),
            "agents": [{**copy.deepcopy(profile), "position": list(person["position"]),
                        "inside": person["inside"], "place_id": person.get("place_id"),
                        "mode": person.get("mode"), "vehicle_id": person.get("vehicle_id")}
                       for profile, person in zip(self.life.profiles, self.life.people, strict=True)],
            "vehicles": copy.deepcopy(self.life.vehicles),
        }
        self.initial_hash = hashlib.sha256(json.dumps(self.initial_conditions, sort_keys=True).encode()).hexdigest()

    @property
    def seconds(self):
        return self.tick*self.config.tick_seconds if self._seconds is None else self._seconds

    def draw(self, *keys):
        return uniform(self.config.seed, *keys)

    def event(self, kind, resident_id=None, **extra):
        self.events.append({"tick": self.tick, "time": self.seconds,
                            "type": kind, "agent_id": resident_id, **extra})

    def is_follower(self, person):
        return self.life.unit_for[person["id"]]["leader"] != person["id"]

    def can_admit(self, members, place_id):
        """Reserve complete households without counting occupied slots twice."""
        capacity = self.places[place_id].get("capacity", 0)
        unit_id = self.life.unit_for[members[0]]["id"]
        own = set(members)
        occupied = {p["id"] for p in self.life.people if p["inside"] and p.get("place_id") == place_id}
        incoming = {i for unit in self.life.units if unit["id"] != unit_id and self.reservations.get(unit["id"]) == place_id
                    for i in unit["members"]}
        return len(occupied | incoming | own) <= capacity

    def observe(self, person, meta):
        visible = not self.hazard.outside_scene(person, self.places) and self.hazard.danger_at(person["position"]) and (
            not person["inside"] or self.hazard.kind in {"flood", "wildfire"})
        if visible and not meta["danger_seen"]:
            meta["danger_seen"] = True
            meta["observed_seconds"] = self.seconds
            if not self.base_rounds_completed:
                self.decision_anchor = min(self.decision_anchor, self.seconds)
            self.event("hazard_observed", person["id"], source="local_observation")
        return visible

    def broadcast(self):
        self.update_delivered_this_tick = False
        if not self.broadcast_sent and self.seconds >= self.broadcast_at:
            self.broadcast_sent = True
            self.event("warning_sent", channels=self.warning.channels, simulation=True)
            if self.hazard.kind == "tornado" and getattr(self.life, "transit", None):
                self.life.transit.suspend("Tornado warning")
            for person in self.life.people:
                i = person["id"]
                if "mobile" in self.warning.channels and self.draw("reach-mobile", i) < self.warning.delivery_reach_probability:
                    delay = 5 + int(11 * self.draw("campus-mobile-delay", i))
                    heapq.heappush(self.messages, (self.broadcast_at + delay, i, -1, "mobile"))
                if "siren" in self.warning.channels and self.draw("reach-siren", i) < self.warning.delivery_reach_probability * .65:
                    heapq.heappush(self.messages, (self.broadcast_at + 5, i, -1, "siren"))
        while self.messages and self.messages[0][0] <= self.seconds:
            delivered_at, i, source, channel = heapq.heappop(self.messages)
            meta = self.meta[i]
            if channel == "siren":
                person = self.life.people[i]
                # Outdoor warning sirens are a tone cue, not delivery of the
                # authored mobile message. Indoor/off-map reception is not assumed.
                if (not person["inside"] and not self.hazard.outside_scene(person, self.places)
                        and not meta["siren_heard"]):
                    meta.update(siren_heard=True, siren_tick=self.tick, siren_seconds=delivered_at)
                    self.event("siren_heard", i, channel="siren", information="outdoor tone only")
                continue
            if not meta["received"]:
                meta.update(received=True, receipt_tick=self.tick, receipt_seconds=delivered_at)
                self.event("warning_delivered", i, source_agent_id=source, channel=channel)
        if self.hazard.kind == "public_safety" and self.hazard.seconds >= 300 and not self.update_sent:
            self.update_sent = True
            instruction = "Simulation authority: the avoidance area has expanded. Avoid marked closures; remain in a suitable building or use an available route away."
            self.event("hazard_update", instruction_version=2, instruction=instruction, simulation=True)
            for person, meta in zip(self.life.people, self.meta, strict=True):
                if self.draw("campus-update-reach", person["id"]) < self.warning.delivery_reach_probability:
                    meta["latest_update"] = instruction
                    self.update_delivered_this_tick = True
                    self.event("hazard_update_delivered", person["id"], instruction_version=2)
        if self.hazard.all_clear and not self.clear_sent:
            self.clear_sent = True
            if getattr(self.life, "transit", None):
                self.life.transit.resume_service()
            self.event("all_clear", source="scenario_authority", simulation=True,
                       instruction="The simulation authority has issued the all-clear.")
            for person, meta in zip(self.life.people, self.meta, strict=True):
                # A separate explicit delivery, not an omniscient LLM-generated assurance.
                if self.draw("campus-clear-reach", person["id"]) < self.warning.delivery_reach_probability:
                    meta["clear_received"] = True
                    meta["latest_update"] = "Simulation authority: all-clear"
                    self.event("all_clear_delivered", person["id"], channel="scenario_update")

    def can_enter(self, person, place):
        """Private residences are available to occupants, not arbitrary passersby."""
        if place["kind"] == "home":
            return self.life.profiles[person["id"]]["home_place_id"] == place["id"]
        return place.get("public_shelter", True) or self.life.profiles[person["id"]]["work_place_id"] == place["id"]

    def shelter(self, person):
        key = (person["id"], self.tick)
        if key in self.route_cache:
            return self.route_cache[key]
        unit = self.life.unit_for[person["id"]]
        origin = unit["position"]
        # Optimistic bound must cover an already chosen urgent walking pace.
        fastest_speed = max(2.4, unit["speed"])
        if person.get("mode") in {"driving", "riding", "alighting"}:
            vehicle = self.life.vehicles.get(person.get("vehicle_id") or unit.get("vehicle_id"), {})
            origin = vehicle.get("position", origin)
            fastest_speed = max(12. if vehicle.get("type") == "bus" else 6., fastest_speed)
        candidates = sorted(((math.dist(origin, p["entrance"])*self.city.meters_per_unit/fastest_speed, p) for p in self.city.places
                             if self.hazard.suitable(p) and self.can_enter(person, p)),
                            key=lambda row: (row[0], row[1]["id"]))
        selected, best = None, (math.inf, "")
        for lower_bound, place in candidates:
            # Straight-line distance is only a search bound. The selected shelter
            # minimizes feasible movement time, including any legal vehicle transfer.
            if lower_bound > best[0]:
                break
            if not self.can_admit(unit["members"], place["id"]):
                continue
            seconds = self.life.route_seconds_to(person["id"], place["id"], blocked=self.blocked)
            if seconds is None:
                continue
            score = (seconds, place["id"])
            if score < best:
                selected, best = place, score
        self.route_cache[key] = selected
        return selected

    def available_actions(self, person, meta):
        actions = ["WAIT", "CONTINUE_ROUTINE", "PREPARE", "POSTPONE_TRAVEL"]
        if person.get("mode") in {"boarding", "driving", "riding", "alighting"}:
            actions.remove("POSTPONE_TRAVEL")
        if meta["received"] and not meta["shared"] and "social" in self.warning.channels:
            actions.append("SHARE")
        if self.is_follower(person):
            return ["STAY_WITH_GROUP"] + (["SHARE"] if "SHARE" in actions else [])
        if self.hazard.outside_scene(person, self.places):
            return actions
        if not (meta["received"] or meta["danger_seen"] or meta["latest_update"] or meta["siren_heard"]):
            return actions
        if self.hazard.protected(person, self.places):
            actions.append("SHELTER_IN_PLACE")
        elif self.shelter(person):
            actions.append("SEEK_INDOOR_SHELTER")
            if self.hazard.kind in {"flood", "wildfire", "public_safety"}:
                actions.append("EVACUATE_AREA")
        return actions

    def context(self, person, meta):
        self.observe(person, meta)
        i = person["id"]
        profile = self.life.profiles[i]
        knows = meta["received"] or meta["danger_seen"] or meta["latest_update"]
        alerted = knows or meta["siren_heard"]
        place = self.shelter(person) if alerted and not self.is_follower(person) and not self.hazard.outside_scene(person, self.places) else None
        route = self.life.path_to(i, place["id"], blocked=self.blocked) if place else None
        profile_goal = profile.get("goal", "Complete my current commitments and return home")
        return {
            "id": i, "elapsed_seconds": self.seconds, "goal": profile_goal, "position": list(person["position"]),
            "state": meta["state"], "trust": profile.get("trust", .7),
            "warning_received": meta["received"],
            "perceived_warning": self.warning.text if meta["received"] else None,
            "perceived_cues": ([{"type": "outdoor_siren", "tick": meta["siren_tick"],
                                 "information": "An outdoor warning tone was audible. It did not communicate a message or identify the hazard."}]
                               if meta["siren_heard"] else []),
            "latest_update": meta["latest_update"],
            "hazard": {"type": self.hazard.kind if knows else None, "observed": meta["danger_seen"],
                       "visible_here": self.hazard.danger_at(person["position"]) if not person["inside"] else None,
                       "all_clear": self.hazard.all_clear if meta["clear_received"] else None,
                       "shelter_hold_seconds_remaining": self.hazard.state()["shelter_hold_seconds_remaining"] if knows else None},
            "route": {"available": route is not None,
                      "destination": {"id": place["id"], "name": place["name"]} if place else None,
                      "distance_metres": round(sum(math.dist(a, b) for a, b in pairwise(route)) * self.city.meters_per_unit, 1) if route else None,
                      "capacity_provenance": "authored simulation capacity"},
            "town_life": {"name": f"Resident {i+1}", "role": profile.get("role"),
                          "household_id": profile.get("household_id"), "group_id": person.get("group_id"),
                          "household_members": [p["id"] for p in self.life.profiles if p.get("household_id") == profile.get("household_id")],
                          "activity": person["activity"], "inside": person["inside"],
                          "outside_scene": self.hazard.outside_scene(person, self.places),
                          "place_id": person.get("place_id"), "mode": person.get("mode"),
                          "vehicle_id": person.get("vehicle_id"), "home_place_id": profile.get("home_place_id")},
            "coordination": {"travel_leader_id": self.life.unit_for[i]["leader"],
                             "controls_shared_motion": not self.is_follower(person)},
            "memory": meta["decisions"][-3:], "available_actions": self.available_actions(person, meta),
        }

    def apply(self, person, meta, action, decided_by, target_id=None):
        i = person["id"]
        meta["action"] = action
        if action == "STAY_WITH_GROUP":
            return
        if action == "SHARE":
            meta["shared"] = True
            for target in self.life.profiles[i].get("social_connections", []):
                if 0 <= target < len(self.meta):
                    heapq.heappush(self.messages, (self.seconds+5, target, i, "social"))
            self.event("warning_shared", i, decided_by=decided_by)
            return
        if action == "CONTINUE_ROUTINE":
            if not self.is_follower(person):
                self.life.resume(i)
                self.reservations.pop(self.life.unit_for[i]["id"], None)
            meta["target"] = None
            meta["unmet_need"] = False
            self.route_cache.clear()
            return
        if action in {"WAIT", "PREPARE", "POSTPONE_TRAVEL", "SHELTER_IN_PLACE"}:
            if not self.is_follower(person):
                self.life.hold(i, activity={"WAIT": "waiting", "PREPARE": "preparing",
                    "POSTPONE_TRAVEL": "travel postponed", "SHELTER_IN_PLACE": "sheltering indoors"}[action])
            if action == "SHELTER_IN_PLACE" and meta["start_tick"] is None:
                meta["start_tick"] = self.tick
                meta["start_seconds"] = self.seconds
            return
        if action in {"SEEK_INDOOR_SHELTER", "EVACUATE_AREA", "EVACUATE"}:
            # Prior model choices in this batch may have reserved this place.
            self.route_cache.clear()
            target = self.places.get(target_id) if target_id else self.shelter(person)
            members = self.life.unit_for[i]["members"]
            success = (target is not None and self.hazard.suitable(target) and self.can_enter(person, target) and self.can_admit(members, target["id"])
                       and self.life.route_to(i, target["id"], activity="seeking shelter", blocked=self.blocked))
            if success:
                self.reservations[self.life.unit_for[i]["id"]] = target["id"]
                meta["unmet_need"] = False
                meta["target"] = target["id"]
                meta["reroutes"] += 1
                if meta["start_tick"] is None:
                    meta["start_tick"] = self.tick
                    meta["start_seconds"] = self.seconds
                    self.event("agent_started_evacuating", i, decided_by=decided_by)
                self.event("route_replanned", i, destination_place_id=target["id"])
            else:
                self.event("agent_action_unavailable", i, action=action,
                           reason="No currently executable route or a coordinated vehicle trip already governs travel")
                meta["state"] = "STRANDED"
                meta["unmet_need"] = True

    def model_round(self):
        contexts = [self.context(person, meta) for person, meta in zip(self.life.people, self.meta, strict=True)]
        if self.progress_callback:
            self.progress_callback({"stage": "agent_decisions", "tick": self.tick,
                                    "decision_round": len(self.rounds)+1,
                                    "decision_rounds_completed": len(self.rounds), "residents": len(contexts)})
        decisions = self.policy.decide(contexts, self.warning.model_dump(mode="json"),
                                       {**self.config.model_dump(mode="json"), "elapsed_seconds": self.seconds}, self.tick)
        if not isinstance(decisions, dict) or set(decisions) != set(range(len(self.life.people))):
            raise ValueError("The model must return exactly one decision for every requested campus resident")
        for context in contexts:
            decision = decisions[context["id"]]
            if decision.action not in CAMPUS_ACTIONS or decision.action not in context["available_actions"]:
                raise ValueError("The model selected an unavailable campus action")
            if not isinstance(decision.reason, str) or not 1 <= len(decision.reason.strip()) <= 160:
                raise ValueError("The model returned an invalid campus reason")
        self.rounds.append(self.tick)
        self.decision_times.append(self.seconds)
        for person, meta in zip(self.life.people, self.meta, strict=True):
            i = person["id"]
            decision = decisions[i]
            value = {"id": i, "action": decision.action, "reason": decision.reason, "tick": self.tick, "time_seconds": self.seconds}
            meta["decisions"].append(value)
            if meta["received"] and not meta["noticed"]:
                meta.update(noticed=True, notice_tick=self.tick, notice_seconds=self.seconds)
                self.event("warning_noticed", i)
            self.event("agent_model_decision", i, mode="bedrock", model_id=self.policy.usage.get("model_id"),
                       action=decision.action, reason=decision.reason)
            destination = contexts[i]["route"]["destination"]
            self.apply(person, meta, decision.action, "bedrock", destination["id"] if destination else None)

    def rules(self):
        for person, meta in zip(self.life.people, self.meta, strict=True):
            i = person["id"]
            visible = self.observe(person, meta)
            attention_seconds = 5 + int(16*self.draw("campus-attention-delay", i))
            if (meta["received"] and not meta["noticed"] and self.seconds >= meta["receipt_seconds"] + attention_seconds and
                    self.draw("notice", i) < max(0, min(1, self.warning.notice_probability + self.notice_adjustment))):
                meta.update(noticed=True, notice_tick=self.tick, notice_seconds=self.seconds)
                self.event("warning_noticed", i)
            if meta["clear_received"]:
                if self.is_follower(person):
                    self.apply(person, meta, "STAY_WITH_GROUP", "rules")
                elif meta["action"] != "CONTINUE_ROUTINE":
                    self.apply(person, meta, "CONTINUE_ROUTINE", "rules")
                continue
            cue_ready = meta["siren_heard"] and self.seconds >= meta["siren_seconds"] + self.preparation_seconds
            ready = ((meta["noticed"] and self.seconds >= meta["notice_seconds"] + self.preparation_seconds)
                     or meta["latest_update"] or cue_ready)
            observation_ready = visible and self.seconds >= (meta["observed_seconds"] or 0) + 2 + int(6*self.draw("campus-observation-delay", i))
            if not meta["attempted"] and (ready or observation_ready):
                meta["attempted"] = True
                probability = max(.75 if visible else 0, self.warning.action_probability)
                if self.draw("campus-action", i) < probability:
                    options = self.available_actions(person, meta)
                    action = ("SHELTER_IN_PLACE" if "SHELTER_IN_PLACE" in options else
                              "SEEK_INDOOR_SHELTER" if "SEEK_INDOOR_SHELTER" in options else "POSTPONE_TRAVEL")
                    if action not in options:
                        action = "STAY_WITH_GROUP" if "STAY_WITH_GROUP" in options else "WAIT"
                    self.apply(person, meta, action, "rules")
                if meta["received"] and "social" in self.warning.channels and self.draw("share", i) < self.warning.social_share_probability:
                    old_action = meta["action"]
                    self.apply(person, meta, "SHARE", "rules")
                    meta["action"] = old_action

    @staticmethod
    def _position_at(person, motion, fraction):
        if not motion:
            return tuple(person["position"])
        k = min(len(motion["path"])-2, max(0, bisect_right(motion["fractions"], fraction)-1))
        span = motion["fractions"][k+1]-motion["fractions"][k]
        ratio = (fraction-motion["fractions"][k])/span if span else 0
        a, b = motion["path"][k:k+2]
        return tuple(a[axis]+(b[axis]-a[axis])*ratio for axis in (0, 1))

    def _end_contact(self, resident_id, at):
        meta = self.meta[resident_id]
        if not meta["contact"]:
            return
        meta["contact"] = False
        self.event("hazard_contact_ended", resident_id, time=round(at, 6), hazard=self.hazard.kind)
        impact = self.current_impacts.get(resident_id)
        if impact:
            impact["contact_ended_at"] = round(at, 6)
            impact["recover_until"] = round(at+(8 if self.hazard.kind == "tornado" else 2), 6)

    def _contact(self, person, start, end, point, occupancy):
        i, meta = person["id"], self.meta[person["id"]]
        if meta["contact"] and start > meta.get("last_contact_end", start)+1e-6:
            self._end_contact(i, meta["last_contact_end"])
        if not meta["contact"]:
            meta["contact"] = True
            meta["contact_count"] += 1
            self.event("hazard_contact_started", i, time=round(start, 6), hazard=self.hazard.kind,
                       position=[round(v, 6) for v in point], consequence="temporary authored protective reaction")
            if self.hazard.kind != "public_safety":
                self._contact_sequence += 1
                impact = {"id": i, "event_id": self._contact_sequence, "hazard": self.hazard.kind,
                          "kind": "knockdown" if self.hazard.kind == "tornado" and occupancy.get("mode") not in {"riding", "driving"} else "brace",
                          "started_at": round(start, 6), "contact_ended_at": None,
                          "recover_until": round(end+(8 if self.hazard.kind == "tornado" else 2), 6),
                          "position": [round(v, 6) for v in point], "intensity": 1.0,
                          "vehicle_id": occupancy.get("vehicle_id") if occupancy.get("mode") in {"riding", "driving"} else None}
                self.impact_history.append(impact)
                self.current_impacts[i] = impact
        meta["last_contact_end"] = end
        impact = self.current_impacts.get(i)
        if impact:
            impact["recover_until"] = round(end+(8 if self.hazard.kind == "tornado" else 2), 6)
        if self.hazard.kind == "tornado":
            # A short temporary physical interruption preserves the chosen route
            # and intent. This authored game reaction is not an injury estimate.
            self.life.interrupt(i, self.life_origin_seconds+end+8,
                                activity="recovering from wind impact" if impact and impact["kind"] == "knockdown" else "bracing against the wind")

    def integrate_exposure(self, frame, seconds, start_seconds=None, reactions=False):
        """Sweep recorded person motion against the moving ground footprint."""
        if not seconds:
            return
        start_seconds = ((self.tick-1)*self.config.tick_seconds if start_seconds is None else start_seconds)
        motions = {row["id"]: row for row in frame.get("agent_motion", [])}
        transitions = {p["id"]: [] for p in self.life.people}
        for row in frame.get("agent_activity_transitions", []):
            transitions[row["id"]].append(row)
        for person, meta in zip(self.life.people, self.meta, strict=True):
            motion = motions.get(person["id"])
            states = sorted(transitions[person["id"]], key=lambda row: row["fraction"])
            times = [row["fraction"] for row in states]
            cuts = {0., 1., *times}
            if motion:
                cuts.update(motion["fractions"])
            # A building's flood/fire suitability is time-dependent. Retain a
            # bounded sampling interval for that authored indoor predicate.
            if self.hazard.kind in {"flood", "wildfire"}:
                cuts.update(i/seconds for i in range(1, int(seconds)))
            amount = 0.
            for left, right in pairwise(sorted(cuts)):
                middle = (left+right)/2
                occupancy = states[max(0, bisect_right(times, middle)-1)] if states else person
                at = start_seconds+middle*seconds
                if self.hazard.outside_scene(occupancy, self.places) or self.hazard.protected(occupancy, self.places, at):
                    continue
                a, b = self._position_at(person, motion, left), self._position_at(person, motion, right)
                begin, finish = start_seconds+left*seconds, start_seconds+right*seconds
                for entry, exit_time in self.hazard.contact_intervals(a, b, begin, finish):
                    amount += exit_time-entry
                    if reactions:
                        ratio = (entry-begin)/(finish-begin) if finish > begin else 0
                        point = tuple(a[axis]+(b[axis]-a[axis])*ratio for axis in (0, 1))
                        self._contact(person, entry, exit_time, point, occupancy)
            meta["exposure"] = round(meta["exposure"]+amount, 6)
            if reactions and meta["contact"] and (not amount or meta["last_contact_end"] < start_seconds+seconds-1e-6):
                self._end_contact(person["id"], meta["last_contact_end"])

    def _before_substep(self, elapsed_seconds, seconds):
        self._before_people = [{key: person.get(key) for key in
                               ("id", "position", "inside", "place_id", "mode", "vehicle_id")}
                              for person in self.life.people]
        self._before_motion_counts = {i: len(self.life._motions.get(i, [])) for i in range(len(self.life.people))}
        self._before_transition_count = len(self.life._transitions)
        self._before_vehicles = {key: copy.deepcopy(value) for key, value in self.life.vehicles.items()} if self.hazard.kind == "tornado" else {}
        self._before_vehicle_motion_counts = {key: len(rows) for key, rows in self.life._vehicle_motions.items()} if self._before_vehicles else {}

    def _after_substep(self, elapsed_seconds, seconds):
        self._seconds = round(elapsed_seconds-self.life_origin_seconds, 8)
        begin = self.seconds-seconds
        self.hazard.step(self.seconds, rasterize=False)
        self.life.weather = self.hazard.mobility_conditions()
        motions, transitions = [], []
        for old, person in zip(self._before_people, self.life.people, strict=True):
            i = person["id"]
            samples = [(0., tuple(old["position"]))]
            for at, point in self.life._motions.get(i, [])[self._before_motion_counts[i]:]:
                fraction = (at+self.life._frame_start-self.life_origin_seconds-begin)/seconds
                fraction = min(1., max(0., fraction))
                if fraction <= samples[-1][0]+1e-9:
                    samples[-1] = (fraction, tuple(point))
                else:
                    samples.append((fraction, tuple(point)))
            if samples[-1][0] < 1:
                samples.append((1., tuple(person["position"])))
            if len(samples) > 1:
                motions.append({"id": i, "path": [list(point) for _, point in samples], "fractions": [at for at, _ in samples]})
            transitions.append({**old, "fraction": 0.})
        for row in self.life._transitions[self._before_transition_count:]:
            fraction = (row["at"]+self.life._frame_start-self.life_origin_seconds-begin)/seconds
            transitions.append({**row, "fraction": min(1., max(0., fraction))})
        self.integrate_exposure({"agent_motion": motions, "agent_activity_transitions": transitions},
                               seconds, start_seconds=begin, reactions=True)
        self._vehicle_reactions(begin, self.seconds)
        self.route_cache.clear()
        self.update_states()
        self._process_information()
        self.update_states()

    def _vehicle_reactions(self, begin, end):
        """Visible cars and service buses react even when no sampled rider exists."""
        if self.hazard.kind != "tornado":
            return
        for key, old in self._before_vehicles.items():
            vehicle = self.life.vehicles[key]
            active = bool(old.get("occupant_ids") or old.get("service_active"))
            rows = [(begin, tuple(old["position"]))]
            for at, point in self.life._vehicle_motions.get(key, [])[self._before_vehicle_motion_counts.get(key, 0):]:
                absolute = min(end, max(begin, at+self.life._frame_start-self.life_origin_seconds))
                if absolute <= rows[-1][0]+1e-9:
                    rows[-1] = absolute, tuple(point)
                else:
                    rows.append((absolute, tuple(point)))
            if rows[-1][0] < end:
                rows.append((end, tuple(vehicle["position"])))
            contacts = []
            if active:
                for (a, pa), (b, pb) in pairwise(rows):
                    for entry, finish in self.hazard.contact_intervals(pa, pb, a, b):
                        point = [pa[axis]+(pb[axis]-pa[axis])*(entry-a)/(b-a) for axis in (0, 1)]
                        contacts.append((entry, finish, point))
            state = self.vehicle_contacts.get(key)
            for entry, finish, point in contacts:
                if not state or not state["active"] or entry > state["last_end"]+1e-6:
                    if state and state["active"]:
                        state["impact"]["contact_ended_at"] = round(state["last_end"], 6)
                    self._contact_sequence += 1
                    impact = {"id": key, "event_id": self._contact_sequence, "hazard": "tornado", "kind": "buffet",
                              "started_at": round(entry, 6), "contact_ended_at": None, "recover_until": round(finish+8, 6),
                              "position": [round(v, 6) for v in point], "intensity": 1.}
                    self.vehicle_impact_history.append(impact)
                    state = self.vehicle_contacts[key] = {"active": True, "last_end": finish, "impact": impact}
                    self.event("vehicle_hazard_contact", time=round(entry, 6), vehicle_id=key, hazard="tornado")
                state["last_end"] = finish
                state["impact"]["recover_until"] = round(finish+8, 6)
                if vehicle["type"] == "bus":
                    bus = next(b for b in self.life.transit.buses if b["vehicle_id"] == key)
                    bus["impact_until"] = max(bus.get("impact_until", 0), self.life_origin_seconds+finish+8)
                    bus["current_speed"] = 0.
                elif vehicle.get("driver_id") is not None:
                    self.life.interrupt(vehicle["driver_id"], self.life_origin_seconds+finish+8)
                # A contact earlier in this slice remains a valid replay event,
                # but cannot put an already emptied/parked car back on the road.
                if vehicle["type"] == "bus" or vehicle.get("occupant_ids"):
                    vehicle.update(speed_mps=0., state="yielding", weather_response="wind_impact")
                self.life._record_vehicle(vehicle, self.life.elapsed_seconds-self.life._frame_start)
            if state and state["active"] and (not contacts or state["last_end"] < end-1e-6):
                state["active"] = False
                state["impact"]["contact_ended_at"] = round(state["last_end"], 6)
                state["impact"]["recover_until"] = round(state["last_end"]+8, 6)
            if state and not state["active"] and end < state["impact"]["recover_until"] and vehicle["state"] == "yielding":
                vehicle["weather_response"] = "recovering"
                self.life._record_vehicle(vehicle, self.life.elapsed_seconds-self.life._frame_start)
    def _process_information(self):
        was_clear = self.clear_sent
        self.broadcast()
        if self.config.decision_mode == "bedrock":
            # Locally observed danger can start the bounded response schedule
            # before a deliberately delayed warning. It cannot reveal the future.
            for person, meta in zip(self.life.people, self.meta, strict=True):
                self.observe(person, meta)
            due = {index for index, delay in enumerate(DECISION_SECONDS)
                   if index not in self.base_rounds_completed and self.seconds >= self.decision_anchor+delay}
            if due or self.update_delivered_this_tick or (self.clear_sent and not was_clear):
                self.base_rounds_completed.update(due)
                self.model_round()
        else:
            self.rules()

    def update_states(self):
        for person, meta in zip(self.life.people, self.meta, strict=True):
            old = meta["state"]
            protected = self.hazard.protected(person, self.places)
            exposed = self.hazard.danger_at(person["position"]) and not protected
            if self.hazard.outside_scene(person, self.places):
                meta["state"] = "ALERTED" if meta["received"] or meta["siren_heard"] else "UNAWARE"
            elif exposed:
                meta["state"] = "EXPOSED"
                if old != "EXPOSED":
                    self.event("agent_exposed", person["id"])
            elif protected:
                meta["state"] = "SHELTERED"
                if meta["start_tick"] is not None and meta["safe_tick"] is None:
                    meta["safe_tick"] = self.tick
                    meta["safe_seconds"] = self.seconds
                    self.event("agent_reached_safety", person["id"], destination_place_id=person.get("place_id"))
            elif meta["unmet_need"] or self.life.unit_for[person["id"]]["stage"] == "unreachable":
                meta["state"] = "STRANDED"
            elif meta["target"] or self.reservations.get(self.life.unit_for[person["id"]]["id"]):
                meta["state"] = "STRANDED" if person.get("activity") in {"route closed — waiting", "building at capacity"} else "EVACUATING"
            elif meta["action"] in {"WAIT", "PREPARE", "POSTPONE_TRAVEL", "SHARE"}:
                meta["state"] = "PREPARING" if meta["action"] in {"PREPARE", "SHARE"} else "DECIDING"
            else:
                meta["state"] = "ALERTED" if meta["received"] or meta["siren_heard"] else "UNAWARE"
            if meta["state"] != old:
                self.event("state_changed", person["id"], previous=old, state=meta["state"])

    def metrics(self):
        counts = Counter(m["state"] for m in self.meta)
        def mean(values):
            return round(sum(values)/len(values), 3) if values else None

        return {"population": len(self.meta), "warning_delivered": sum(m["received"] for m in self.meta),
                "warning_noticed": sum(m["noticed"] for m in self.meta),
                "siren_heard": sum(m["siren_heard"] for m in self.meta),
                "evacuation_started": sum(m["start_tick"] is not None for m in self.meta),
                "evacuated": counts["SHELTERED"], "sheltered": counts["SHELTERED"],
                "exposed": sum(m["exposure"] > 0 for m in self.meta),
                "stranded": counts["STRANDED"], "evacuating": counts["EVACUATING"],
                "warning_shared": sum(m["shared"] for m in self.meta),
                "average_alert_receipt_time": mean([m["receipt_seconds"] for m in self.meta if m["receipt_seconds"] is not None]),
                "average_decision_delay": mean([m["start_seconds"]-m["notice_seconds"] for m in self.meta if m["start_seconds"] is not None and m["notice_seconds"] is not None and m["start_seconds"] >= m["notice_seconds"]]),
                "average_evacuation_completion_time": mean([m["safe_seconds"]-m["start_seconds"] for m in self.meta if m["safe_seconds"] is not None]),
                "hazard_coverage": len(self.hazard.cells)/max(1, len(self.hazard.domain_cells)), "road_closures": len(self.hazard.blocked_cells),
                "route_replans": sum(m["reroutes"] for m in self.meta), "state_counts": {s: counts[s] for s in STATES},
                "trips_postponed": sum(m["action"] == "POSTPONE_TRAVEL" for m in self.meta),
                "all_clear": self.hazard.all_clear, "hazard_contacts": sum(m["contact_count"] for m in self.meta),
                "affected_people": sum(m["contact_count"] > 0 for m in self.meta),
                "exposure_method": "swept relative motion against authored ground footprint with exact occupancy transitions; not injury probability"}

    def record(self, frame=None):
        frame = frame or self.life.frame(self.tick, time=self.tick * self.config.tick_seconds)
        frame.update(agents=[[p["id"], *p["position"], STATES.index(m["state"]), m["exposure"]]
                              for p, m in zip(self.life.people, self.meta, strict=True)],
                     metrics=self.metrics(), hazard=self.hazard.state(),
                     hazard_cells=[list(p) for p in sorted(self.hazard.cells)],
                     active_hazard_cells=[list(p) for p in sorted(self.hazard.active_cells)],
                     blocked_roads=[list(p) for p in sorted(self.hazard.blocked_cells)],
                     agent_decisions=[dict(m["decisions"][-1]) for m in self.meta if m["decisions"]],
                     interval_seconds=0 if self.tick == 0 else self.config.tick_seconds,
                     hazard_motion=self.hazard.motion(max(0., self.seconds-self.config.tick_seconds), self.seconds),
                     agent_impacts=[copy.deepcopy(row) for row in self.impact_history
                                    if row["started_at"] <= self.seconds and row["recover_until"] >= max(0., self.seconds-self.config.tick_seconds)],
                     vehicle_impacts=[copy.deepcopy(row) for row in self.vehicle_impact_history
                                      if row["started_at"] <= self.seconds and row["recover_until"] >= max(0., self.seconds-self.config.tick_seconds)])
        self.frames.append(frame)

    def run(self):
        from .campus_life import DAY_VERSION

        self._seconds = 0.
        self.life.weather = self.hazard.mobility_conditions()
        # A scenario can begin in an already active field (blizzard). Record
        # contact at its true start without inventing elapsed exposure time.
        for person in self.life.people:
            if (not self.hazard.outside_scene(person, self.places)
                    and not self.hazard.protected(person, self.places, 0.)
                    and self.hazard.danger_at(person["position"], 0.)):
                self._contact(person, 0., 0., person["position"], person)
        self.update_states()
        self._process_information()
        self.record()
        for tick in range(1, self.config.duration_ticks+1):
            if self.cancel_check:
                self.cancel_check()
            self.tick = tick
            self.life.step(self.config.tick_seconds, blocked=self.blocked,
                           weather=self.hazard.mobility_conditions, admit=self.can_admit,
                           before_substep=self._before_substep, after_substep=self._after_substep,
                           max_step_seconds=1)
            self.hazard.step(tick*self.config.tick_seconds)
            frame = self.life.frame(self.tick, time=self.seconds)
            self.update_states()
            self.record(frame)
            if self.progress_callback:
                self.progress_callback({"stage": "simulation", "tick": tick,
                                        "total_ticks": self.config.duration_ticks,
                                        "decision_rounds_completed": len(self.rounds)})
        return {"simulation_version": VERSION, "configuration": self.config.model_dump(mode="json"),
                "recording_version": "last-warning-recording/3", "art_seed": self.config.seed,
                "art_manifest_version": "last-warning-campus/2", "town_day_version": DAY_VERSION,
                "warning": self.warning.model_dump(mode="json"), "seed": self.config.seed,
                "initial_conditions_hash": self.initial_hash, "initial_conditions": self.initial_conditions,
                "city": {**self.city.serialize(), "art_seed": self.config.seed}, "states": STATES,
                "profiles": self.life.profiles, "frames": self.frames, "events": self.events,
                "metrics": self.frames[-1]["metrics"], "notice_adjustment": self.notice_adjustment,
                "decision_mode": self.config.decision_mode,
                "agent_policy": {"mode": self.config.decision_mode, "decision_ticks": self.rounds,
                                 "decision_times_seconds": self.decision_times,
                                 "decision_count": sum(len(m["decisions"]) for m in self.meta),
                                 "usage": dict(self.policy.usage) if self.policy else None},
                "model_assumptions": {"people": "synthetic", "weather": "authored educational profile",
                                      "shelter_capacity": "authored; not official campus shelter designations",
                                      "siren_audibility": "authored outdoor-only tone cue; reach factor 0.65, not an acoustic coverage model",
                                      "exposure": "swept ground-footprint contact; not harm probability",
                                      "response_timing": "authored seeded seconds: mobile 5–15, attention 5–20, social/siren 5; not campus-calibrated",
                                      "preparation_seconds": self.preparation_seconds, "broadcast_seconds": self.broadcast_at,
                                      "legacy_warning_reference_seconds": LEGACY_WARNING_SECONDS,
                                      "model_checkpoints_seconds": list(DECISION_SECONDS),
                                      "physical_reactions": "authored non-graphic wind interruption and 8-second recovery for people and service vehicles, not injury or mortality",
                                      "weather_mobility": "authored mode-specific snow/rain pace, snow retained after all-clear; 3-second snow headway and reduced traction, not campus-calibrated",
                                      "shelter_pace": "only chosen shelter trips hurry; adult cap 2.4 m/s, child/older/mobility-aid group cap 1.55 m/s; snow never uses a running gait"}}


def simulate_campus(config, warning, notice_adjustment=0, decision_policy=None,
                    progress_callback=None, cancel_check=None):
    return CampusSimulation(config, warning, notice_adjustment, decision_policy, progress_callback, cancel_check).run()
