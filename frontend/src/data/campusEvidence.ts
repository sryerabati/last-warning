/** Dated public references. Entries marked reference are not runtime calibration. */
export interface CampusEvidence {
  id:string
  category:'Population'|'Routines'|'Transport'|'Climate'|'Hazards'|'Warnings'
  title:string
  summary:string
  period:string
  scope:string
  status:'Context only'|'Informs hazard definitions'|'Informs warning behavior'|'Informs schedules'|'Informs transit'
  application:string
  limitation:string
  sources:{title:string;url:string}[]
}

export const campusEvidenceReviewedOn='2026-10-25'
export const campusEvidence:CampusEvidence[]=[
  {
    id:'enrollment-2026',category:'Population',title:'A student-centered campus',
    summary:'Autumn 2026 enrollment: 62,010 students on the Columbus campus, including 47,308 undergraduates.',
    period:'Autumn 2026 census · announcement September 21, 2026',
    scope:'Columbus-campus enrolled students; not a count of people outdoors or present in this map.',
    status:'Context only',
    application:'Supports separate undergraduate and graduate roles. The playable population and its mix remain authored.',
    limitation:'Enrollment does not measure attendance, household structure, appearance or response to a warning.',
    sources:[{title:'Ohio State enrollment announcement',url:'https://news.osu.edu/ohio-state-increases-total-enrollment-to-68183-students/'}],
  },
  {
    id:'calendar-autumn-2026',category:'Routines',title:'Teaching days differ from breaks',
    summary:'Autumn classes run August 25–December 9, 2026. October 15–16 is a class break while offices remain open.',
    period:'Autumn 2026 · calendar updated March 3, 2026',
    scope:'University calendar dates, America/New_York; dates may change.',
    status:'Informs schedules',
    application:'Explicit teaching-day, weekend, class-break and university-closure presets change generated routines.',
    limitation:'The chosen day type repeats. It is not a reconstruction of today’s calendar or individual timetables.',
    sources:[{title:'Ohio State five-year academic calendar',url:'https://registrar.osu.edu/academic-calendar/academic-calendar-5-year-view-2023-2028/'}],
  },
  {
    id:'cabs-2026-27',category:'Transport',title:'Campus travel includes transit',
    summary:'Campus Connector service varies between teaching weekdays, evenings, weekends and class breaks; university holidays have no scheduled service.',
    period:'2026–27 published service schedule',
    scope:'Published service windows and mapped stop locations; not live arrivals or observed travel times.',
    status:'Informs transit',
    application:'A bounded campus shuttle uses real College Connector stop locations, scheduled departures, queues, boarding, capacity and alighting.',
    limitation:'The simulated circuit is educational and shorter than the official route. Capacity, dwell and travel behavior are authored; no live arrivals or football-day override.',
    sources:[{title:'Ohio State CABS routes and schedules',url:'https://ttm.osu.edu/cabs'}],
  },
  {
    id:'cmh-climate-1991-2020',category:'Climate',title:'Columbus has distinct seasons',
    summary:'Mean daily high/low: January 37.19°F / 21.97°F; July 85.48°F / 65.52°F. January normal monthly snowfall is 9.5 inches.',
    period:'1991–2020 climate normals',
    scope:'Columbus airport climate reference; monthly averages over the 30-year normal period.',
    status:'Context only',
    application:'A baseline for future seasonal clothing, daylight and ambient-weather presets.',
    limitation:'Airport normals are not campus observations, a forecast, or probabilities of a blizzard or hailstorm.',
    sources:[
      {title:'NWS Columbus normals overview',url:'https://www.weather.gov/iln/climate_normals_cmh'},
      {title:'January normal values',url:'https://www.weather.gov/media/iln/climo_webpage/CMH_Jan.pdf'},
      {title:'July normal values',url:'https://www.weather.gov/media/iln/climo_webpage/CMH_Jul.pdf'},
    ],
  },
  {
    id:'nws-storm-categories',category:'Hazards',title:'Severe and destructive are different',
    summary:'NWS base severe-thunderstorm criteria: 58 mph wind or 1-inch hail. Destructive criteria: 80 mph wind or 2.75-inch hail.',
    period:'NWS damage-threat categories · verified October 25, 2026',
    scope:'Warning thresholds for wind speed and hail diameter; either qualifying hazard can meet the criterion.',
    status:'Informs hazard definitions',
    application:'Supports the simulator’s destructive-thunderstorm scenario and explicit wind/hail readout.',
    limitation:'Thresholds do not establish uniform intensity, building damage, injury risk or a calibrated human response.',
    sources:[{title:'NWS severe-thunderstorm damage-threat categories',url:'https://www.weather.gov/lot/SevereThunderstormWarningsUpdate'}],
  },
  {
    id:'outdoor-warning-information',category:'Warnings',title:'A tone is not the full message',
    summary:'Outdoor sirens alert people outside. An alarm cue, access to a message and a protective decision are distinct steps.',
    period:'Franklin County guidance reviewed October 25, 2026; NIST review February 2011',
    scope:'Local alert-system guidance and a campus/building warning research review.',
    status:'Informs warning behavior',
    application:'New runs record outdoor siren cues separately. A tone can prompt shelter seeking, but cannot reveal or share warning text that was never received.',
    limitation:'Real county sirens may carry tones or speech. This option models tones only; reach and response rates remain authored, not measured acoustics.',
    sources:[
      {title:'Franklin County alerting and warning',url:'https://www.franklincountyohio.gov/Agency-Directory/Emergency-Management-and-Homeland-Security/Alerting-Warning'},
      {title:'NIST campus and building warning review',url:'https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=907983'},
    ],
  },
  {
    id:'lightning-shelter-hold',category:'Hazards',title:'Wait after the last thunder',
    summary:'NWS advises remaining sheltered for at least 30 minutes after the last thunder.',
    period:'NWS guidance reviewed October 25, 2026',
    scope:'Lightning safety guidance, not a severe-weather harm model.',
    status:'Informs hazard definitions',
    application:'The storm scenario resets its 30-minute shelter hold when another authored thunder event occurs.',
    limitation:'Enclosed metal-topped vehicles can protect against lightning, but not every storm hazard. Separate component-specific vehicle protection is not modeled yet.',
    sources:[{title:'NWS lightning safety',url:'https://www.weather.gov/safety/lightning-tips'}],
  },
]
