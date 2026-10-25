export type Point = [number, number]
export type DisasterType = 'flood'|'wildfire'|'tornado'|'blizzard'|'hailstorm'|'thunderstorm'|'public_safety'
export type CampusDayType = 'teaching'|'weekend'|'class_break'|'closed'
export type DecisionMode = 'bedrock'|'rules'
export interface AgentDecision {id:number;action:'WAIT'|'PREPARE'|'SHARE'|'EVACUATE'|'CONTINUE_ROUTINE'|'SHELTER'|'SHELTER_IN_PLACE'|'AVOID_AREA'|'REUNITE'|'SEEK_INDOOR_SHELTER'|'POSTPONE_TRAVEL'|'EVACUATE_AREA'|'STAY_WITH_GROUP';reason:string;tick:number;time_seconds?:number}
export type MovementStyle = 'still'|'walk'|'run'|'careful'|'brace'|'recover'
export interface AgentActivity {id:number;activity:string;place_id:string|null;destination_place_id?:string|null;inside:boolean;partner_ids:number[];mode?:string;vehicle_id?:string|null;group_id?:string|null;walked_m?:number;route_accessible?:boolean;movement_style?:MovementStyle;speed_mps?:number;weather_response?:string}
export interface TownInteraction {id:string;kind:'greeting'|'conversation'|'warning_shared'|'boarding'|'family_reunion';agent_ids:number[];position:Point;tick:number;expires_tick:number}
export interface TownPlace {is_portal?:boolean;id:string;name:string;kind:'home'|'shop'|'work'|'school'|'civic'|'park'|'shelter';position:Point;footprint:Point[];entrance:Point;facing:'n'|'e'|'s'|'w';variant:number}
export interface ResidentProfile {id:number;name?:string;biography?:string;identity?:{version:string;source:string;given_name:string;family_name:string;naming_style:string;display_order:string};age_years?:number;family_relationship?:string|null;household_type?:string;appearance?:CharacterAppearance;age_group?:string;household_role?:string;transport_preference?:string;household_id:string;home_place_id:string;work_place_id:string|null;role:string;goal:string;trust:number;movement_speed:number;reaction_delay:number;social_connections:number[];routine:{start_minute:number;activity:string;place_id:string;inside:boolean}[]}
export interface AgentMotion {id:number;path:Point[];fractions:number[]}
export interface RouteChange {id:number;path:Point[];destination:Point|null}
export interface AgentUsage {
  provider:string;model_id:string;region:string;run_id:string;calls:number;input_tokens:number;output_tokens:number;
  estimated_cost_usd:number;accounted_cost_usd:number;decision_count:number;rounds:number;max_run_usd:number
}
export interface AgentPolicy {
  mode:DecisionMode;model_id?:string;region?:string;decision_ticks:number[];decision_times_seconds?:number[];decision_count:number;usage?:AgentUsage|null
}
export interface AgentStatus {
  available:boolean;model_id:string;region:string;spend_limit_usd:number;spent_usd:number;remaining_usd:number;
  max_run_usd?:number;error?:string
}
export interface Scenario {
  id: string; name: string; population: number; seed: number; duration_ticks: number;
  tick_seconds: number; hazard_origin: Point; hazard_spread: number; created_at?: string
  disaster_type: DisasterType
  decision_mode:DecisionMode
  layout?:'grid'|'organic'|'campus';town_life?:boolean;campus_day_type?:CampusDayType;transit_enabled?:boolean;town_start_tick?:number;town_start_minutes?:number
}
export interface Warning {
  id: string; name: string; text: string; delivery_reach_probability: number; notice_probability: number;
  action_probability: number; response_delay: number; social_share_probability: number;
  broadcast_tick: number; broadcast_seconds?:number|null; preparation_seconds?:number|null; channels: ('mobile' | 'siren' | 'social')[]; created_at?: string
}
export interface Metrics {
  population: number; hazard_contacts?:number; affected_people?:number; siren_heard?: number; warning_delivered: number; warning_noticed: number; evacuation_started: number;
  evacuated: number; exposed: number; stranded: number; evacuating: number; warning_shared: number;
  average_alert_receipt_time: number | null; average_decision_delay: number | null;
  average_evacuation_completion_time: number | null; hazard_coverage: number; road_closures: number;
  route_replans: number; state_counts: Record<string, number>
}
export interface AgentImpact {id:number;event_id?:number;vehicle_id?:string|null;hazard:DisasterType;kind:'knockdown'|'brace';started_at:number;contact_ended_at:number|null;recover_until:number;position:Point;intensity:number}
export interface VehicleImpact {id:string;event_id:number;hazard:'tornado';kind:'buffet';started_at:number;contact_ended_at:number|null;recover_until:number;position:Point;intensity:number}
export interface VehicleStateTransition {id:string;fraction:number;state:string;speed_mps:number;weather_response:string}
export interface BusStop {id:string;name:string;position:Point;waiting_count:number;waiting_ids?:number[]}
export interface Frame { tick: number; time: number; agents: number[][]; hazard_cells: Point[];
  active_hazard_cells?: Point[]; blocked_roads: Point[]; metrics: Metrics;
  agent_decisions?:AgentDecision[];vehicles?:VehicleState[];vehicle_motion?:VehicleMotion[];agent_activity_transitions?:ActivityTransition[];vehicle_state_transitions?:VehicleStateTransition[];vehicle_impacts?:VehicleImpact[];
  agent_motion?:AgentMotion[];route_changes?:RouteChange[];
  world_clock_minutes?:number;agent_activities?:AgentActivity[];interactions?:TownInteraction[];
  traffic?:Record<string,number|string>;agent_impacts?:AgentImpact[];interval_seconds?:number;bus_stops?:BusStop[];transit?:{service_active:boolean;service_label?:string;route_name?:string;[key:string]:unknown};hazard_motion?:{path:Point[];fractions:number[];active_from?:number|null;active_until?:number|null};
  hazard?: {type:DisasterType; center?:Point; wind?:Point; radius?:number; [key:string]:unknown} }
export interface City {
  size: number; roads: Point[]; buildings: Point[]; river: Point[]; safe_zones: Point[];
  neighborhoods: {name: string; position: Point}[]
  art_seed?:number;art_manifest_version?:string
  layout?:'grid'|'organic'|'campus';world_version?:string;places?:TownPlace[];
  road_styles?:{position:Point;kind:'road'|'path'|'bridge'}[]
  coordinate_space?:string;meters_per_unit?:number;map_bounds?:number[];campus_geometry?:CampusGeometry;walk_edges?:[Point,Point][];vehicle_edges?:[Point,Point][];geography_provenance?:{source:string;attribution:string;url:string;license:string;source_sha256:string;snapshot:string;limitations:string};
  default_origins?:Partial<Record<DisasterType,Point>>;camera_focus?:Point
}
export interface Recording {city: City; frames: Frame[]; states: string[]; total: number;
  art_seed?:number;art_manifest_version?:string;recording_version?:string|null;
  profiles?:ResidentProfile[];initial_conditions?:{agents:ResidentProfile[]}}
export interface TownDay extends Recording {profiles:ResidentProfile[];town_day_version:string;minutes_per_tick:number;clock_start_minutes:number}
export interface Run {
  id: string; scenario_id: string; warning_id: string; warning: Warning; seed: number;
  configuration: Scenario; metrics: Metrics; created_at: string; frame_count: number;
  initial_conditions_hash: string; baseline_run_id: string | null; coupling_strength: number;
  simulation_version: string; notice_adjustment: number
  neural_analysis_id: string|null
  decision_mode?:DecisionMode;agent_policy?:AgentPolicy
  art_seed?:number;art_manifest_version?:string;recording_version?:string
}
export interface RunJob {
  id:string;status:'queued'|'running'|'completed'|'failed'|'cancelled'|'interrupted';
  stage:string;run_id:string|null;analysis_id:string|null;cancel_requested:boolean;
  progress:{tick:number;total_ticks:number;decision_round?:number;decision_rounds_completed:number;
    batches_completed?:number;batches_total?:number;residents?:number};
  error:{status:number;detail:string}|null;created_at:string;updated_at:string;started_at?:string;finished_at?:string
}
export interface ResidentDetails {
  id:number;tick:number;time:number;position:Point;state:string;exposure_seconds:number;
  initial_position:Point|null;goal:string|null;trust:number|null;reaction_delay_ticks:number|null;response_timing_seconds?:{mobile:number;attention:number;observation:number;siren:number;social:number}|null;
  movement_speed_cells_per_tick:number|null;social_connections:number[]|null;decision:AgentDecision|null;
  route:Point[]|null;destination:Point|null;route_source:'recorded_plan'|null;route_accessible:boolean|null;art_seed:number
  household_id?:string|null;home_place_id?:string|null;work_place_id?:string|null;role?:string|null;
  name?:string|null;
  activity?:string|null;place_id?:string|null;inside?:boolean;partner_ids?:number[];mode?:string;vehicle_id?:string|null;group_id?:string|null;movement_speed_mps?:number|null;current_speed_mps?:number|null;movement_style?:MovementStyle|null;weather_response?:string|null
}
export interface Comparison {id: string; baseline_run_id: string; alternative_run_id: string;
  deltas: Record<string, number | null>; assumptions: Record<string, {baseline: unknown; alternative: unknown}>;
  initial_conditions_hash: string}
export interface Stimulus {id: string; warning_id: string; filename: string; sha256: string; size: number}
export interface NeuralSeries {time: number; mean: number; mean_absolute: number; std: number}
export interface Analysis {
  id: string; warning_id: string; stimulus_id: string; stimulus_hash: string; model_id: string;
  model_revision: string; code_revision: string; prediction_shape: number[]; inference_timestamp: string;
  sampling_information: Record<string, unknown>; provenance: 'REAL_TRIBE'|'TEST_FIXTURE'; provenance_note: string;
  notes: string;
  warning_text_hash: string;
  summary: {mean: number; std: number; min: number; max: number; mean_absolute_response: number; normalized_feature: number};
  series: NeuralSeries[]
}
export interface NeuralDifference {aligned_samples: number; mean_absolute_difference: number; provenance: string;
  series: {time: number; mean_difference: number; mean_absolute_difference: number}[]}
export interface LocalTribeStatus {available: boolean; running: boolean; model_id: string;
  model_revision: string; max_words: number; words_per_second: number; protocol: string}

export interface CharacterAppearance {body?:number;skin?:number;hair?:number;hair_style?:number;outfit?:number;top?:number;bottom?:number;accessory?:number;headwear?:number;mobility?:'walk'|'wheelchair';age?:'adult'|'child'|'older'}
export interface CampusFeature {id:string;name?:string;kind?:string;geometry:{type:string;coordinates:Point[]|Point[][]};[key:string]:unknown}
export interface CampusGeometry {buildings:CampusFeature[];paths:CampusFeature[];roads:CampusFeature[];water:CampusFeature[];greens:CampusFeature[]}
export interface VehicleState {id:string;x:number;y:number;position?:Point;type?:string;capacity?:number;heading?:number;mode?:string;state?:string;speed_mps?:number;weather_response?:string;occupant_ids?:number[];passenger_ids?:number[];driver_id?:number|null;seats?:number;color?:string|number;[key:string]:unknown}
export interface VehicleMotion {id:string;path:Point[];fractions:number[]}
export interface ActivityTransition {id:number;fraction:number;mode:string;vehicle_id:string|null;inside:boolean;activity:string;place_id:string|null;movement_style?:MovementStyle;speed_mps?:number;weather_response?:string}
