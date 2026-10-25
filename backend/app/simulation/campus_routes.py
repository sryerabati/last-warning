"""Shared directed closure checks for live campus motion and historical routes."""
import math

from .campus_world import distance


def segment_is_clear(start, end, blocked, meters_per_unit):
    if blocked is None:
        return True
    steps = max(1, math.ceil(distance(start, end)*meters_per_unit/3))
    initially_blocked = blocked(start)
    escaped = not initially_blocked
    score = getattr(blocked, "egress_score", None)
    previous_score = score(start) if initially_blocked and score else None
    for i in range(1, steps+1):
        point = tuple(start[k]+(end[k]-start[k])*i/steps for k in (0, 1))
        closed = blocked(point)
        if closed and escaped:
            return False
        if closed and previous_score is not None:
            current_score = score(point)
            if current_score > previous_score+1e-6:
                return False
            previous_score = current_score
        if not closed:
            escaped = True
    return escaped or (initially_blocked and score is not None)

