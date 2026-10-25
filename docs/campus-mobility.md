# Campus movement coordination

The campus life runtime now coordinates crossings and lane following on the pinned walking and driving graphs. These are deterministic authored traffic rules, not fitted Columbus traffic, verified crosswalk markings, or a recreation of actual traffic signals.

`campus_traffic.py` finds footpath/road segment intersections and road junctions, merges neighboring source vertices into conflict zones, and indexes them spatially. A unit requests a zone before entering. The earliest expected arrival retains priority; simultaneous requests favor pedestrians. An occupying unit keeps the reservation until its body or vehicle rear clears. A waiting request keeps its original timestamp so new arrivals cannot indefinitely jump the queue. A stopped vehicle remains a physical obstacle.

Cars and buses use a standstill spacing allowance plus reaction headway on the same directed lane, an authored 6 m/s campus cruise ceiling, 1.6 m/s² acceleration and a 3 m/s² braking target. The hard movement allowance remains authoritative when a following vehicle or crossing blocks the route. Opposing directed lanes share canonical road-centerline routing coordinates; `lane_offset_m` is supplied to the renderer to show separate lanes without changing route topology or resident seat coordinates.

The motion integrator uses at most one-second slices while motor traffic is active, and at most five seconds for otherwise quiet ordinary days. Emergency callers can request a fixed one-second grid and update hazard speeds through a per-slice callback. All time is physical simulation time. Idle agenda lookups are cached until the next scheduled appointment, keeping the finer motor-traffic stepping bounded.

A yield is recorded as stationary timed motion and a concrete `waiting to cross`, `yielding at crossing`, or `waiting in traffic` activity. Resume preserves the chosen destination and resumes actual movement. The recording retains corners, stops, starts, boarding and alighting fractions; interpolation does not slide through a wait.

Transit buses participate in the same reservations and headway rules. A dwelling bus owns its short curb-transfer corridor, so boarding passengers cannot deadlock against the vehicle they are boarding. A bus passenger cannot stop the entire vehicle through an individual WAIT intention; passengers remain conserved until physical alighting at a stop. The driver is outside the synthetic resident population. Boarding and step-off movements remain visible transfers, with seat occupancy beginning on completion of boarding and ending when step-off begins.

Transient hazard interruptions are separate from a resident's deliberate hold. `interrupt(resident_id, until_seconds, activity)` preserves the route, seats and prior intention while physical movement pauses; recovery restores activity without teleporting or inventing a new decision. An interruption of a bus passenger also prevents the bus from moving until the physical effect resolves.

## Checks

Eight focused traffic tests cover geometric interior intersections, parallel-path exclusion, pedestrian tie priority, occupied-zone release, non-starvation, same-lane headway, opposing lanes, empty-road pedestrian flow, bus transfer reservations, and acceleration/braking. Existing campus-life checks continue to cover exact motion endpoints, fraction ordering, household formation, capacity, route access, return-home completion and frozen warning initialization. Additional life checks cover callback timing/speed changes, temporary impact recovery, bus passenger identity, and car acceleration after a physical interruption. Bus dispatch and return visibility is recorded and replayed at its event fraction, so an end-of-frame depot state cannot hide its preceding journey.

The original car-only conservation assertion was extended narrowly for buses: the operator is not a resident, and an alighting passenger has physically left the seat while still completing the recorded curb transfer. Capacity, duplicate riders, vehicle/person positions while aboard, and vehicle IDs remain checked.
