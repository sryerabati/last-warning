"""Mesa agent lifecycle + NetworkX routing; deterministic independent tick recordings."""
import hashlib
import heapq
import json
from collections import Counter

import mesa
import networkx as nx

from ..schemas import ScenarioConfig, WarningConfig
from .agents import Resident
from .hazards import make_hazard
from .life import activity_row, interactions_for, routine_target, town_day
from .world import make_city, uniform

VERSION = "last-warning-ca/1.4.0"
STATES = ["UNAWARE", "ALERTED", "DECIDING", "PREPARING", "EVACUATING", "SHELTERED", "STRANDED", "EXPOSED"]
MODEL_DECISION_TICKS = (4, 16, 32, 56)
MODEL_ACTIONS = {"WAIT", "PREPARE", "SHARE", "EVACUATE"}
RECORDING_VERSION = "last-warning-recording/2"
ART_MANIFEST_VERSION = "last-warning-pixel/1"


class Simulation(mesa.Model):
    def __init__(self, config: ScenarioConfig, warning: WarningConfig, notice_adjustment: float = 0,
                 decision_policy=None, progress_callback=None, cancel_check=None):
        super().__init__(seed=config.seed)
        if config.decision_mode == "bedrock" and decision_policy is None:
            raise ValueError("Bedrock resident decisions require an available model policy; no rule fallback is used")
        if config.decision_mode == "bedrock" and notice_adjustment:
            raise ValueError("Neural notice-probability coupling is available only in rule-based decision mode")
        self.config, self.warning = config, warning
        self.notice_adjustment = notice_adjustment
        self.decision_policy = decision_policy
        self.progress_callback, self.cancel_check = progress_callback, cancel_check
        self.model_rounds: list[int] = []
        self.tick_motion: dict[int, list[tuple[int, int]]] = {}
        self.tick_route_changes: set[int] = set()
        self.city = make_city(config)
        self.hazard = make_hazard(self.city, config)
        self.safe_zones = self.city.safe_zones
        self.tick = -1
        self.events: list[dict] = []
        self.frames: list[dict] = []
        self.messages: list[tuple[int, int, int, str]] = []
        self.people: list[Resident] = []
        self.road_graph = self.city.graph
        self.paths = {}
        self.last_blocked = None
        self.traffic = Counter()
        self.town_profiles = []
        self.town_places = {p["id"]: p for p in self.city.places}
        self.tick_interactions = []
        starts = [p for p in self.city.roads if p not in self.safe_zones and not 18 <= p[0] <= 20
                  and 1 < p[0] < 39 and 1 < p[1] < 39]
        for i in range(config.population):
            pos = starts[int(self.draw("initial", i) * len(starts))]
            a = Resident(self, i, pos, 0.5 + 0.5 * self.draw("trust", i),
                         int(6 * self.draw("reaction", i)), 0.45 + 0.85 * self.draw("speed", i))
            self.people.append(a)
        social = nx.watts_strogatz_graph(config.population, 6, 0.12, seed=config.seed)
        for a in self.people:
            a.social_connections = sorted(social.neighbors(a.resident_id))
        if config.town_life:
            day = town_day(config.population, config.seed, config.disaster_type)
            snapshot = day["frames"][config.town_start_tick]
            self.town_profiles = day["profiles"]
            self.tick_interactions = snapshot["interactions"]
            for a, profile, row, activity in zip(self.people, self.town_profiles,
                                                  snapshot["agents"], snapshot["agent_activities"], strict=True):
                a.profile = profile
                a.position = a.initial_position = tuple(row[1:3])
                a.goal, a.social_connections = profile["goal"], profile["social_connections"]
                a.activity, a.place_id, a.inside = activity["activity"], activity["place_id"], activity["inside"]
                a.partner_ids = list(activity["partner_ids"])
                a.destination_place_id = activity["destination_place_id"]
                target = routine_target(profile, config.town_start_tick * 5)
                a.destination = tuple(target["destination"])
                a.planned_route = nx.shortest_path(self.city.graph, a.position, a.destination)
        initial_config = config.model_dump(mode="json")
        if initial_config.get("town_start_minutes") is None:
            initial_config.pop("town_start_minutes", None)
        if config.layout == "grid" and not config.town_life:
            # Default additive fields must not rewrite legacy initial hashes.
            for field in ("layout", "town_life", "town_start_tick"):
                initial_config.pop(field)
        self.initial_conditions = {
            "configuration": initial_config,
            "agents": [{"id": a.resident_id, "position": list(a.position), "trust": a.trust,
                        "goal": a.goal,
                        "reaction_delay": a.reaction_delay, "movement_speed": a.movement_speed,
                        "social_connections": a.social_connections,
                        **({**a.profile, "activity": a.activity, "place_id": a.place_id,
                            "inside": a.inside} if a.profile else {})} for a in self.people],
        }
        self.initial_hash = hashlib.sha256(json.dumps(self.initial_conditions, sort_keys=True).encode()).hexdigest()

    def draw(self, *keys):
        return uniform(self.config.seed, *keys)

    def event(self, kind, agent=None, **extra):
        self.events.append({"tick": self.tick, "time": self.tick * self.config.tick_seconds,
                            "type": kind, "agent_id": agent, **extra})

    def change_state(self, a, state):
        if a.state != state:
            self.event("state_changed", a.resident_id, previous=a.state, state=state)
            a.state = state

    def deliver(self, a, channel, source):
        if a.warning_received:
            return
        a.warning_received = True
        a.receipt_tick = self.tick
        self.event("warning_delivered", a.resident_id, channel=channel, source_agent_id=source)
        if a.state == "UNAWARE":
            self.change_state(a, "ALERTED")

    def broadcast(self):
        w = self.warning
        if self.tick == w.broadcast_tick:
            self.event("warning_sent", channels=w.channels)
            for a in self.people:
                if "mobile" in w.channels and self.draw("reach-mobile", a.resident_id) < w.delivery_reach_probability:
                    delay = 1 + int(4 * self.draw("mobile-delay", a.resident_id))
                    heapq.heappush(self.messages, (self.tick + delay, a.resident_id, -1, "mobile"))
                if "siren" in w.channels and self.draw("reach-siren", a.resident_id) < w.delivery_reach_probability * 0.65:
                    heapq.heappush(self.messages, (self.tick + 2, a.resident_id, -1, "siren"))
        while self.messages and self.messages[0][0] <= self.tick:
            _, target, source, channel = heapq.heappop(self.messages)
            self.deliver(self.people[target], channel, source)

    def available_model_actions(self, a):
        actions = ["WAIT", "PREPARE"]
        if self.config.town_life:
            actions.append("CONTINUE_ROUTINE")
        if a.position in self.paths:
            actions.append("EVACUATE")
        if a.warning_received and not a.shared and "social" in self.warning.channels:
            actions.append("SHARE")
        return actions

    def resident_context(self, a):
        x, y = a.position
        visible = sorted(p for p in self.hazard.active_cells if abs(p[0] - x) <= 3 and abs(p[1] - y) <= 3
                         and not (self.config.town_life and a.inside))
        if visible and not a.danger_seen:
            a.danger_seen = True
            self.event("hazard_observed", a.resident_id, source="local_observation")
        knows_hazard = a.warning_received or a.danger_seen
        route = self.paths.get(a.position)
        value = {
            "id": a.resident_id, "goal": a.goal, "position": list(a.position), "state": a.state,
            "trust": a.trust, "movement_speed_cells_per_tick": a.movement_speed,
            "warning_received": a.warning_received,
            "perceived_warning": self.warning.text if a.warning_received else None,
            "hazard": {"type": self.config.disaster_type if knows_hazard else None, "observed": a.danger_seen,
                       "visible_active_cells": [list(p) for p in visible[:12]],
                       "nearest_visible_distance_cells": min((abs(px - x) + abs(py - y) for px, py in visible), default=None)},
            "route": {"available": route is not None, "distance_cells": len(route) - 1 if route else None,
                      "destination": list(route[0]) if route else None},
            "neighbors": [{"id": i, "state": self.people[i].state,
                           "warning_received": self.people[i].warning_received} for i in a.social_connections],
            "memory": a.model_decisions[-3:], "available_actions": self.available_model_actions(a),
        }
        if a.profile:
            target = routine_target(a.profile, self.world_clock_minutes)
            home = self.town_places[a.profile["home_place_id"]]
            workplace = self.town_places.get(a.profile["work_place_id"])
            value["town_life"] = {"name": a.profile["name"], "role": a.profile["role"],
                                  "household_id": a.profile["household_id"],
                                  "household_members": [p["id"] for p in self.town_profiles
                                                        if p["household_id"] == a.profile["household_id"]],
                                  "home": {"id": home["id"], "name": home["name"], "entrance": home["entrance"]},
                                  "workplace": ({"id": workplace["id"], "name": workplace["name"],
                                                 "entrance": workplace["entrance"]} if workplace else None),
                                  "activity": a.activity, "inside": a.inside, "place_id": a.place_id,
                                  "daily_destination": {"place_id": target["place_id"],
                                                        "name": self.town_places[target["place_id"]]["name"],
                                                        "position": target["destination"]},
                                  "world_clock_minutes": self.world_clock_minutes}
        return value

    @property
    def world_clock_minutes(self):
        return (self.config.town_start_tick * 5 + max(0, self.tick) * self.config.tick_seconds / 60) % 1440

    def model_decision_round(self):
        people = [a for a in self.people if a.state not in {"SHELTERED", "EXPOSED"}
                  and a.position not in self.hazard.danger_cells]
        if not people:
            return
        if self.progress_callback:
            self.progress_callback({"stage": "agent_decisions", "tick": self.tick,
                                    "decision_round": MODEL_DECISION_TICKS.index(self.tick) + 1,
                                    "decision_rounds_completed": len(self.model_rounds),
                                    "residents": len(people), "batches_completed": 0})
        contexts = [self.resident_context(a) for a in people]
        decisions = self.decision_policy.decide(contexts, self.warning.model_dump(mode="json"),
                                                self.config.model_dump(mode="json"), self.tick)
        if not isinstance(decisions, dict) or set(decisions) != {a.resident_id for a in people}:
            raise ValueError("The model must return exactly one decision for every requested resident")
        # Validate a complete round before applying any returned behavior.
        for a in people:
            decision = decisions[a.resident_id]
            action, reason = getattr(decision, "action", None), getattr(decision, "reason", None)
            supported = MODEL_ACTIONS | ({"CONTINUE_ROUTINE"} if self.config.town_life else set())
            if action not in supported or action not in self.available_model_actions(a):
                raise ValueError(f"The model returned an unavailable action for resident {a.resident_id}")
            if not isinstance(reason, str) or not reason.strip() or len(reason) > 500:
                raise ValueError(f"The model returned an invalid reason for resident {a.resident_id}")
        self.model_rounds.append(self.tick)
        model_id = self.decision_policy.usage.get("model_id")
        for a in people:
            decision = decisions[a.resident_id]
            a.model_action = decision.action
            value = {"id": a.resident_id, "action": decision.action, "reason": decision.reason, "tick": self.tick}
            a.model_decisions.append(value)
            self.event("agent_model_decision", a.resident_id, action=decision.action, reason=decision.reason,
                       mode="bedrock", model_id=model_id)
            if a.warning_received and not a.warning_noticed:
                a.warning_noticed, a.notice_tick = True, self.tick
                self.event("warning_noticed", a.resident_id)
            if decision.action == "WAIT":
                if a.profile:
                    a.activity = "waiting"
                self.change_state(a, "DECIDING")
            elif decision.action in {"PREPARE", "SHARE"}:
                if a.profile:
                    a.activity = "sharing warning" if decision.action == "SHARE" else "preparing"
                self.change_state(a, "PREPARING")
                a.decision_tick = self.tick
                if decision.action == "SHARE":
                    a.shared = True
                    for target in a.social_connections:
                        delay = 2 + int(self.draw("social-delay", a.resident_id, target) * 4)
                        heapq.heappush(self.messages, (self.tick + delay, target, a.resident_id, "social"))
                    self.event("warning_shared", a.resident_id, recipients=len(a.social_connections), decided_by="bedrock")
            elif decision.action == "EVACUATE":
                if a.profile:
                    a.inside, a.place_id, a.activity, a.partner_ids = False, None, "evacuating", []
                if a.start_tick is None:
                    a.start_tick = self.tick
                    self.event("agent_started_evacuating", a.resident_id, decided_by="bedrock")
                self.change_state(a, "EVACUATING")
            elif decision.action == "CONTINUE_ROUTINE":
                self.change_state(a, "ALERTED" if a.warning_received else "UNAWARE")

    def advance_resident(self, a):
        w, i = self.warning, a.resident_id
        if a.state == "SHELTERED":
            return
        if a.position in self.hazard.danger_cells:
            if a.profile:
                a.activity, a.partner_ids = "exposed", []
            a.hazard_exposure += self.config.tick_seconds
            if a.state != "EXPOSED":
                self.event("agent_exposed", i)
                self.change_state(a, "EXPOSED")
            return
        if a.state == "EXPOSED":
            return
        if self.config.decision_mode == "bedrock":
            if self.config.town_life and a.model_action in {None, "CONTINUE_ROUTINE"}:
                self.advance_routine(a)
                return
            if a.model_action != "EVACUATE":
                return
            self.move_resident(a)
            return
        # A single attention draw prevents repeated trials from making every alert inevitable.
        if a.warning_received and not a.warning_noticed and self.tick == a.receipt_tick + 1:
            probability = max(0, min(1, w.notice_probability + self.notice_adjustment))
            if self.draw("notice", i) < probability:
                a.warning_noticed, a.notice_tick = True, self.tick
                self.event("warning_noticed", i)
                if a.state in {"UNAWARE", "ALERTED"}:
                    self.change_state(a, "DECIDING")
        if a.warning_noticed and not a.shared and "social" in w.channels and self.tick >= a.notice_tick + 2:
            a.shared = True
            if self.draw("share", i) < w.social_share_probability:
                for target in a.social_connections:
                    delay = 2 + int(self.draw("social-delay", i, target) * 4)
                    heapq.heappush(self.messages, (self.tick + delay, target, i, "social"))
                self.event("warning_shared", i, recipients=len(a.social_connections))
        x, y = a.position
        nearby = any((x + dx, y + dy) in self.hazard.active_cells
                     for dx, dy in [(0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)])
        if nearby and not a.danger_seen:
            a.danger_seen = True
            self.event("hazard_observed", i)
            if a.state in {"UNAWARE", "ALERTED", "DECIDING"}:
                self.change_state(a, "PREPARING")
                a.decision_tick = self.tick
        if (a.state == "DECIDING" and self.tick >= a.notice_tick + a.reaction_delay
                and self.draw("action", i) < w.action_probability * a.trust):
            self.change_state(a, "PREPARING")
            a.decision_tick = self.tick
        if a.state == "PREPARING":
            delay = 1 if a.danger_seen else w.response_delay
            if self.tick >= a.decision_tick + delay:
                a.start_tick = self.tick
                self.event("agent_started_evacuating", i)
                self.change_state(a, "EVACUATING")
        if a.state not in {"EVACUATING", "STRANDED"}:
            if self.config.town_life and a.state != "PREPARING":
                self.advance_routine(a)
            return
        self.move_resident(a)

    def advance_routine(self, a):
        target = routine_target(a.profile, self.world_clock_minutes)
        destination = tuple(target["destination"])
        if a.position == destination:
            a.activity, a.place_id, a.inside = target["activity"], target["place_id"], target["inside"]
            a.destination_place_id = target["place_id"]
            return
        a.inside, a.place_id, a.activity = False, None, "commuting"
        a.destination_place_id = target["place_id"]
        a.destination = destination
        try:
            planned = nx.shortest_path(self.road_graph, a.position, destination)
        except (nx.NodeNotFound, nx.NetworkXNoPath):
            a.activity = "route blocked"
            if a.planned_route:
                self.tick_route_changes.add(a.resident_id)
            a.planned_route = []
            return
        if planned != a.planned_route:
            self.tick_route_changes.add(a.resident_id)
        a.planned_route, a.destination = planned, destination
        a.progress = min(2.0, a.progress + a.movement_speed)
        while a.progress >= 1 and len(a.planned_route) > 1:
            next_pos = a.planned_route[1]
            if self.traffic[next_pos] >= 3:
                break
            self.traffic[next_pos] += 1
            self.tick_motion.setdefault(a.resident_id, [a.position]).append(next_pos)
            a.position = next_pos
            a.planned_route.pop(0)
            a.progress -= 1
        if a.position == destination:
            a.activity, a.place_id, a.inside = target["activity"], target["place_id"], target["inside"]

    def move_resident(self, a):
        i = a.resident_id
        if a.profile:
            a.inside, a.place_id, a.activity, a.partner_ids = False, None, "evacuating", []
        route = self.paths.get(a.position)
        if route is None:
            self.change_state(a, "STRANDED")
            if a.profile:
                a.activity, a.destination_place_id, a.destination = "stranded", None, None
            if a.planned_route:
                self.tick_route_changes.add(i)
            a.planned_route = []
            return
        if a.state == "STRANDED":
            self.change_state(a, "EVACUATING")
        if a.planned_route and any(p in self.hazard.blocked for p in a.planned_route):
            a.reroutes += 1
            self.event("route_replanned", i)
        # Paths are recalculated against current closures, so every movement is a live graph edge.
        planned = list(reversed(route))
        if planned != a.planned_route:
            self.tick_route_changes.add(i)
        a.planned_route = planned
        a.destination = a.planned_route[-1]
        if a.profile:
            shelter = next((p for p in self.city.places if p["kind"] == "shelter"
                            and tuple(p["entrance"]) == a.destination), None)
            a.destination_place_id = shelter["id"] if shelter else None
        a.progress = min(2.0, a.progress + a.movement_speed)
        while a.progress >= 1 and len(a.planned_route) > 1:
            next_pos = a.planned_route[1]
            if next_pos not in self.safe_zones and self.traffic[next_pos] >= 3:
                break
            if not self.road_graph.has_edge(a.position, next_pos):
                raise RuntimeError("Routing produced an inaccessible road")
            self.traffic[next_pos] += 1
            self.tick_motion.setdefault(i, [a.position]).append(next_pos)
            a.position = next_pos
            a.planned_route.pop(0)
            a.progress -= 1
        if a.position in self.safe_zones:
            if a.profile:
                shelter = next((p for p in self.city.places if p["kind"] == "shelter"
                                and tuple(p["entrance"]) == a.position), None)
                a.inside, a.place_id, a.activity = True, shelter["id"] if shelter else None, "sheltered"
            self.change_state(a, "SHELTERED")
            a.safe_tick = self.tick
            self.event("agent_reached_safety", i, destination=list(a.destination))

    def metrics(self):
        people, seconds = self.people, self.config.tick_seconds
        counts = Counter(a.state for a in people)

        def mean(values):
            return round(sum(values) / len(values) * seconds, 3) if values else None

        return {
            "population": len(people), "warning_delivered": sum(a.warning_received for a in people),
            "warning_noticed": sum(a.warning_noticed for a in people),
            "evacuation_started": sum(a.start_tick is not None for a in people),
            "evacuated": counts["SHELTERED"], "exposed": sum(a.hazard_exposure > 0 for a in people),
            "stranded": counts["STRANDED"], "evacuating": counts["EVACUATING"],
            "warning_shared": sum(e["type"] == "warning_shared" for e in self.events),
            "average_alert_receipt_time": mean([a.receipt_tick for a in people if a.receipt_tick is not None]),
            "average_decision_delay": mean([a.start_tick - a.notice_tick for a in people
                                             if a.start_tick is not None and a.notice_tick is not None]),
            "average_evacuation_completion_time": mean([a.safe_tick - a.start_tick for a in people if a.safe_tick is not None]),
            "hazard_coverage": round(len(self.hazard.cells) / 1600, 6),
            "road_closures": len(self.hazard.blocked),
            "route_replans": sum(a.reroutes for a in people),
            "state_counts": {state: counts[state] for state in STATES},
        }

    def step(self):
        if self.cancel_check:
            self.cancel_check()
        self.tick += 1
        self.tick_motion, self.tick_route_changes = {}, set()
        self.hazard.step(self.tick)
        blocked = frozenset(self.hazard.blocked)
        if blocked != self.last_blocked:
            self.road_graph = nx.subgraph_view(self.city.graph, filter_node=lambda n: n not in blocked)
            _, self.paths = nx.multi_source_dijkstra(self.road_graph, self.safe_zones, weight="weight")
            self.last_blocked = blocked
        self.broadcast()
        if self.config.decision_mode == "bedrock" and self.tick in MODEL_DECISION_TICKS:
            self.model_decision_round()
        self.traffic.clear()
        # Rotating deterministic priority avoids permanent low-id congestion preference.
        if self.config.town_life and self.tick == 0:
            self.tick_route_changes = {a.resident_id for a in self.people}
            self.tick_interactions = [{**item, "id": f"snapshot-{item['id']}", "tick": 0, "expires_tick": 1}
                                      for item in self.tick_interactions]
        else:
            for a in sorted(self.people, key=lambda a: self.draw("priority", self.tick, a.resident_id)):
                a.step()
            if self.config.town_life:
                states = [{"position": a.position, "activity": a.activity, "place_id": a.place_id,
                           "inside": a.inside, "partner_ids": []} for a in self.people]
                self.tick_interactions = interactions_for(states, self.tick)
                for a, state in zip(self.people, states, strict=True):
                    a.partner_ids = state["partner_ids"]
        self.frames.append({
            "tick": self.tick, "time": self.tick * self.config.tick_seconds,
            "agents": [[a.resident_id, *a.position, STATES.index(a.state), a.hazard_exposure] for a in self.people],
            "hazard_cells": [list(p) for p in sorted(self.hazard.cells)],
            "active_hazard_cells": [list(p) for p in sorted(self.hazard.active_cells)],
            "hazard": self.hazard.state(),
            "agent_decisions": [dict(a.model_decisions[-1]) for a in self.people if a.model_decisions],
            # The vertices are actual traversed graph edges. Fractions only
            # define equal-edge visual timing within the tick, not new physics.
            "agent_motion": [{"id": i, "path": [list(p) for p in path],
                              "fractions": [j / (len(path) - 1) for j in range(len(path))]}
                             for i, path in sorted(self.tick_motion.items())],
            "route_changes": [{"id": i, "path": [list(p) for p in self.people[i].planned_route],
                               "destination": list(self.people[i].destination) if self.people[i].destination else None}
                              for i in sorted(self.tick_route_changes)],
            "blocked_roads": [list(p) for p in sorted(blocked)], "metrics": self.metrics(),
            **({"world_clock_minutes": self.world_clock_minutes,
                "agent_activities": [activity_row(a.resident_id, {
                    "activity": a.activity, "place_id": a.place_id, "inside": a.inside,
                    "partner_ids": a.partner_ids, "destination_place_id": a.destination_place_id}) for a in self.people],
                "interactions": self.tick_interactions} if self.config.town_life else {}),
        })
        if self.progress_callback:
            self.progress_callback({"stage": "simulation", "tick": self.tick,
                                    "total_ticks": self.config.duration_ticks,
                                    "decision_rounds_completed": len(self.model_rounds)})

    def run(self):
        # Frame zero records the untouched population before any warning delivery or movement.
        for _ in range(self.config.duration_ticks + 1):
            self.step()
        return {
            "simulation_version": VERSION, "configuration": self.config.model_dump(mode="json"),
            "recording_version": RECORDING_VERSION, "art_seed": self.config.seed,
            "art_manifest_version": ART_MANIFEST_VERSION,
            "warning": self.warning.model_dump(mode="json"), "seed": self.config.seed,
            "initial_conditions_hash": self.initial_hash, "initial_conditions": self.initial_conditions,
            "city": {**self.city.serialize(), "art_seed": self.config.seed,
                     "art_manifest_version": ART_MANIFEST_VERSION}, "states": STATES, "frames": self.frames,
            "events": self.events, "metrics": self.frames[-1]["metrics"],
            "notice_adjustment": self.notice_adjustment,
            "decision_mode": self.config.decision_mode,
            "agent_policy": {"mode": self.config.decision_mode, "decision_ticks": list(self.model_rounds),
                             "decision_count": sum(len(a.model_decisions) for a in self.people),
                             "usage": dict(self.decision_policy.usage) if self.config.decision_mode == "bedrock" else None},
            **({"profiles": self.town_profiles, "town_day_version": "riverside-life/1"} if self.config.town_life else {}),
        }


def simulate(config: ScenarioConfig, warning: WarningConfig, notice_adjustment: float = 0, decision_policy=None,
             progress_callback=None, cancel_check=None):
    if config.layout == "campus":
        from .campus_engine import simulate_campus

        return simulate_campus(config, warning, notice_adjustment, decision_policy, progress_callback, cancel_check)
    return Simulation(config, warning, notice_adjustment, decision_policy, progress_callback, cancel_check).run()
