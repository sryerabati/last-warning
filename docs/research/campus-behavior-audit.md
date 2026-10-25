# Campus behavior audit and corrections

Audited locally on 2026-10-24/25. Default population: 300, seed: 42. No paid inference or AWS calls were made for this audit. These are synthetic demonstration occupants, not a census or a predictive model of Ohio State behavior.

## Measured defects in the previous day

| Finding | Default-day evidence | Correction |
| --- | --- | --- |
| Families dominated a university scene | 34 families, 119 family members, including 51 children; only 114 students | Cap local families at two at every population size. Most occupants are undergraduates or graduate students. |
| Families were not employees | Every adult family member had role `parent` and toured campus with the children all day | Employment and family relationship are separate. An employed parent travels independently; a caregiver accompanies one preschool child. |
| Tiny homes held apartment-block populations | Seven or eight unrelated families and 38–40 people shared individual houses | A house accommodates one household. Families receive distinct complete, connected residential houses. Student housing, apartments and commuter origins serve the other residents. |
| Faculty lived in student dorms | Four professors were assigned Baker, Bradley or Paterson Hall | Dorm assignment is limited to student residents. Faculty/staff live locally in apartments or enter from explicitly off-map commuter homes. |
| Graduate students never appeared | Household-index and role-index cycles excluded the graduate role | Independent campus composition includes graduate students explicitly. |
| Walkers were actually frozen | `family walk` and `morning walk` ended in `waiting`; 13:00 had zero walkers and 258 people parked at three parks | Outdoor leisure has distinct, traversed waypoints with short stops. A stationary stop is labeled as a break, not walking. |
| Campus-wide synchronized gatherings | At 13:00 there were 266 waiting residents; at 19:00 there were 278 | Stagger class, work, lunch, study and home times. Only a minority take short outdoor breaks; selected roommates have brief appointments. |
| Same-park destinations never changed | Routine transitions compared only place IDs | Target identity and destination changes now start a new route even within the same park. |
| Mobility could trap a person indoors all day | Two wheelchair students walked zero metres; six other family members received unreachable park destinations | Home and routine allocation respects the connected step-free graph. Shared dependent units use the most restrictive routing requirement. This does not certify actual real-world accessibility. |
| Cars chose implausible journeys | 189/255 trips were slower than walking; 118 required more walking just to reach/from the car; worst trip was 4.9× slower | Compare complete journey time, including walk to car, directed road journey, transfers and final walk. Require a meaningful time saving before driving. |
| Parked cars stacked | 70 cars occupied four exact garage coordinates | Garage inventory remains authoritative but the visual layer hides parked garage cars; moving/boarding vehicles remain visible. Physical parking bays are not modeled. |
| Social network and names were artificial | All 49 roommate households shared surnames; all 600 generated extra ties were nonreciprocal ID offsets | Roommates receive independent surnames. Relationships are reciprocal and come from households, classmates and coworkers. |
| Repeated conversations never rested | The same nearby pair restarted immediately after each four-minute interaction | Pairs have a 15-minute cooldown before another interaction. |
| Unrealistically frequent headwear | Four of five uniform choices were hats/headgear | Most recipes have no headwear; student recipes more often carry a backpack or shoulder bag. Appearance remains independently generated. |
| Meal activity could target any commercial building | The browser showed lunch/coffee at a veterinary clinic, concert venue or apartment-labelled commercial footprint | Meal and snack routines require mapped food service; coffee requires mapped café service. Generic retail remains eligible only for ordinary errands. |
| Routing memory scaled with every stop | Expanded map produced 508 full destination trees | Rare destinations use bidirectional point-to-point routing; reusable full trees are capped at 32. |

## Current authored day

For the default seed and 300 residents: 202 students, 47 graduate students, 16 professors, 16 staff, 15 local neighbors, two caregivers and two preschool children. There are two three-person local families. The percentages are chosen to make a campus-focused demonstration legible; they are not claimed to match OSU demographics.

Preschool children have explicit ages 3–5. A caregiver stays locally with the child and makes a brief afternoon outing. The other adult has their own work/teaching itinerary. This avoids implying that school-age children skip school or follow a professor through a full workday. Caregiver and child share route/vehicle decisions; their profile itineraries agree with actual shared motion.

Students change buildings between classes, study at civic/library destinations, have staggered lunch and sometimes a short break, coffee or evening study. Faculty and staff keep work blocks. Neighbors make limited errands and short walks, rather than serving as a second tourist population. Course locations, opening times, jobs, speeds, durations and population proportions remain authored assumptions. Real timetables and private personal data are not used.

Initial post-fix measurement: 12:00 had 46 walkers and 254 people indoors; 13:00 had 68 walkers and 232 indoors, with no prolonged park crowd. At all sampled times there were no unreachable units, and every resident travelled during the day and returned home. Short meetings were recorded in 22 two-minute frames. A cold 300-person, 720-frame day on this Mac took 28.23 seconds including geographic construction; compact JSON was 78.18 MB, gzip 10.39 MB, and process peak memory approximately 389 MB. Later geometry or art changes can alter these benchmark numbers.

The final version 2.1 exterior-only route and food-service audit is saved in `output/campus-car-behavior-audit.json`: 300 residents occupy 105 homes, with only two families. There are 31 cars and 26 actual car trips; none was slower than walking, and the median complete car trip took 79.2% of the direct walking time. At ten-minute samples the largest outdoor waiting count was 13, the peak walking count was 68, and six distinct interaction pairs were observed. Nobody was unreachable or stationary for the whole day, and all 300 residents returned home. All 351 meal, snack and coffee itinerary stops used the corresponding mapped service. Activity text identifies the actual venue where a source name exists, even inside a differently named campus or mixed-use building. This is a deterministic scenario check, not evidence of real-world behavioral accuracy.

## Verification and practical limits

Regression checks cover population sizes 30, 300 and 1,000; the two-family maximum; one household per house; preschool ages; professional housing; reciprocal contacts; coherent dependent itineraries; reachable wheelchair routes; short outdoor stops; distinct walk waypoints; a whole default-size day without unreachable units or mass park camping; and vehicle occupant/driver conservation. Warning handoff continues to use exactly the recorded daytime state.

The road model follows mapped directed routes but does not simulate traffic signals, lane-changing, headway, collision avoidance or pedestrian crossing priority. Driving speed is an authored simplification. The walking model follows pedestrian geometry and avoids stairs when needed, but it is not a crowd-pressure or accessibility certification model. Residents can pass each other without a full pedestrian collision solver. Indoor activity is represented at a building, without room-scale motion. Social interactions are brief local relationships, not LLM-generated daily conversations; Bedrock remains the warning-decision service. None of these limitations supports a claim of calibrated human response prediction.
