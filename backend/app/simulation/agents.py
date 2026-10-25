import mesa

EVERYDAY_PRIORITIES = (
    "Finish your work shift, then return home to your household. Keep family informed if credible local conditions change.",
    "Complete nearby errands and return home. Avoid unnecessary trips and reassess plans when reliable information arrives.",
    "Stay near home and check on neighbors when practical. Balance helping others with your own safety and available information.",
    "Get home to your family after work. Maintain ordinary plans while staying attentive to messages and conditions you can actually observe.",
    "Keep a planned appointment, then return home. Weigh disruption against credible information about your immediate surroundings.",
    "Continue your household routine. Confirm what is happening locally before deciding whether to change your plans or contact others.",
)


class Resident(mesa.Agent):
    def __init__(self, model, resident_id: int, position, trust, reaction_delay, movement_speed):
        super().__init__(model)
        self.resident_id = resident_id
        self.position = self.initial_position = position
        self.state = "UNAWARE"
        self.warning_received = False
        self.warning_noticed = False
        self.trust = trust
        self.reaction_delay = reaction_delay
        self.movement_speed = movement_speed
        self.social_connections: list[int] = []
        self.destination = None
        self.planned_route: list[tuple[int, int]] = []
        self.hazard_exposure = 0
        self.receipt_tick = None
        self.notice_tick = None
        self.decision_tick = None
        self.start_tick = None
        self.safe_tick = None
        self.shared = False
        self.danger_seen = False
        self.progress = 0.0
        self.reroutes = 0
        priority = int(model.draw("everyday-priority", resident_id) * len(EVERYDAY_PRIORITIES))
        self.goal = EVERYDAY_PRIORITIES[priority]
        if movement_speed < 0.7:
            self.goal += " Your walking pace is slow; account for the time and effort of any trip."
        self.model_action = None
        self.model_decisions: list[dict] = []
        self.profile = None
        self.activity = None
        self.place_id = None
        self.destination_place_id = None
        self.inside = False
        self.partner_ids: list[int] = []

    def step(self):
        self.model.advance_resident(self)
