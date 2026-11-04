# Interview monitoring and security

Disclosed, opt-in, on-device camera, microphone and browser signals during interviews. Events never change scores and must never be the sole basis for a hiring decision. Visual attention percentage: [ATTENTION_MONITORING.md](ATTENTION_MONITORING.md).

## Camera monitoring (2026-10-11)

* Setup screen before every live interview: what is monitored and why, processed **in the browser** (MediaPipe Face
  Landmarker, model served from `public/models`), nothing stored except event records, retention (default 90 days,
  setting `monitoring_retention_days`), who can see it, how to stop. Separate opt-ins; permissions are requested only
  when the student presses **Test my camera and microphone**; camera preview with face/lighting/framing guidance.
* **Camera required by default** (`monitoring_camera_required` = true, admin → Settings): camera, face visibility
  and multiple-face checks are mandatory; approximate gaze/head direction and tab-focus changes stay optional.
  Without camera access the interview does not start and the student is told why.
* Signals: face not visible, more than one face, sustained looking away (approximate), camera blocked/dark, low light,
  camera disconnected, permission revoked, tab/window focus changes, monitoring stopped/unavailable. Grace periods,
  hysteresis and frame-agreement confidence (`src/monitoring/signalTracker.js`); neutral warnings only.
* Severity is assigned by the server (`services/integrity.py`); gaze is never above "low", and low-confidence signals
  stay "info". Events **never change scores** and never trigger a penalty.
* Review: admin → AI & Monitoring → **Interview integrity**; mentors only with the extra permission
  `review_integrity` and only for students they can access; recruiters: only completed interviews of their own applicants (see [INTERVIEW_SECURITY.md](INTERVIEW_SECURITY.md)). Views and reviews are audit-logged.
  Students see their events after the interview and can add an explanation.
* Media handling: one camera stream, self-view always marked "Camera on", **Stop monitoring** turns it off at once,
  everything is stopped when the interview ends or the page is left. Frames and audio are never sent to other services.


## Interview security module (2026-10-23)

Extends the camera monitoring of the camera monitoring section of [INTERVIEW_SECURITY.md](INTERVIEW_SECURITY.md) into one security module: more detectors, one event engine, a security summary,
recruiter reports and admin settings. Everything in the camera monitoring section of [INTERVIEW_SECURITY.md](INTERVIEW_SECURITY.md) still applies (disclosed, opt-in per feature, on-device,
never changes scores). Code: `frontend/src/monitoring/*`, `backend/app/services/integrity.py`,
`backend/app/routers/monitoring.py`.

### What is detected, and how
| Category (`event_type`) | How | Where it runs |
|---|---|---|
| PROLONGED_LOOKING_AWAY (`attention_away`) | head yaw/pitch from MediaPipe's face transformation matrix + eye-direction blendshapes, measured **from the candidate's own calibrated position**; recorded after 3 s, reminder after 8 s; brief glances are not recorded; not judged in low light | browser |
| EYE_GAZE_DEVIATION (`attention_repeated`) | 5 recorded deviations within 120 s = one event (then counting restarts) | browser |
| FACE_NOT_DETECTED / FACE_PARTIALLY_VISIBLE | no face for 4 s+ / face cut by the frame edge for 10 s+ (grace periods, hysteresis, frame agreement) | browser |
| MULTIPLE_FACES_DETECTED | 2+ faces for 3 s+, with the largest count seen; nobody is identified | browser |
| BROWSER_TAB_SWITCH, FULLSCREEN_EXIT, SECOND_DISPLAY, PASTE | Page Visibility / blur, Fullscreen API, `screen.isExtended`, paste events (the camera monitoring section of [INTERVIEW_SECURITY.md](INTERVIEW_SECURITY.md)) | browser |
| POSSIBLE_BACKGROUND_SPEECH (`background_speech`) | while the microphone is open **for the answer**: voiced audio (RMS level only) for 4 s+ while the one visible face's mouth (jawOpen) does not move → "uncertain"; nothing is reported when it cannot be attributed (no face / several faces) | browser |
| MICROPHONE_DISCONNECTED, CAMERA_DISCONNECTED, PERMISSION_REVOKED | track `ended`/`mute`, getUserMedia errors, Permissions API | browser |
| NETWORK_INTERRUPTION | `offline`/`online` events + failed event uploads; one event per outage (2 s+) | browser |
| SESSION_RECONNECTED | the candidate accepted the notice again for the same interview (page reload) - **recorded by the server** | server |
| INTERVIEW_PAUSED | pause/resume in the room, with the reason (manual / admin pause rule) | browser |
| POSSIBLE_IDENTITY_MISMATCH | **not implemented** - see limitations | - |

The interviewer is excluded from audio checks by design: the microphone is closed while the interviewer speaks, echo
cancellation is on, and nothing is analysed between answers. No audio is recorded or uploaded for these checks (the
answer itself is transcribed as before, [VOICE_INTERVIEW.md](VOICE_INTERVIEW.md)).

**Calibration**: the setup screen asks the candidate to sit comfortably, centre their face, look at the screen and
check the light, then offers *Calibrate now* (5 s). The median head/eye position becomes the baseline, so a camera
beside the screen or a different posture is not "looking away". If it is skipped, calibration runs during the first
5 s of the interview. A clearly turned baseline produces a hint to recalibrate (not an error - side cameras are fine).

### Event engine (one path for every detector)
`InterviewMonitor` → `EventReporter` → `POST /api/student/interviews/{id}/integrity-events` → `integrity_events`.
* Each event: type, controlled category, interview-relative start (`t_ms`), duration, confidence (frame agreement),
  whitelisted `details` (`max_faces`, `cause` head/eyes, `edge`, `count`, `reason`), server-assigned severity,
  detection source, review status/notes. API responses add wall-clock `start_timestamp`/`end_timestamp` (the interview
  clock starts at the first consent and **continues across reloads**).
* Consecutive frames are merged into one episode; nothing is sent per frame. Batches every 8 s (or 10 events).
* Duplicates: every event has a `client_event_id`; retries and page-close flushes are stored once (unique index).
* Unsent events survive a reload/crash (sessionStorage) and are flushed on `pagehide` with a keepalive request.
* Server checks: own interview only, consented feature only, interview in progress (3 min grace after finishing), not
  later than the interview clock allows, 50 events per request, 500 per interview, 30 requests/min per interview.
* Reviews never change detected fields; each review is appended to `integrity_reviews` (history visible to admins).

### Security summary (risk score)
`integrity.risk_summary`: rules count related **events** (not frames), multiply by a configurable weight, and are
capped per rule. Defaults: repeated/very long gaze 1, face absent 15 s+ 2, every 3 tab switches (or one 30 s+) 2,
second face 5 s+ 3, every 2 possible additional voices 1, phone 10 s+ 2, long paste 1, fullscreen exit 10 s+ 1,
device interruptions 1. Bands: low ≥ 1, moderate ≥ 4, high ≥ 8. Low-confidence events and events a reviewer marked
no concern / false positive are not counted. Labels are neutral ("Low/Moderate/High number of potential
irregularities"); the response always lists the contributing events and how it was calculated. **These weights are
illustrative engineering values, not validated against real data.** The summary is separate from interview scores
and must never be the sole basis for rejection or any hiring decision.

### Who sees what
* Candidate: their own events, summary, review status (not reviewer notes); can add an explanation.
* Admin: everything, plus review history. Admin → AI & Monitoring → *Interview integrity* and *Security settings*.
* Mentor: with `review_integrity` and only for students they may access (the camera monitoring section of [INTERVIEW_SECURITY.md](INTERVIEW_SECURITY.md)).
* Recruiter (**new**): *Security Reports* page and a section on the candidate page - only **completed** interviews of
  candidates who applied to one of their jobs, only if recruiter access was on **and disclosed when the candidate
  consented** (not retroactive), and only while the admin setting is still on. Recruiters can mark events reviewed /
  false positive / concern noted / further review requested, with notes. They never see consent configuration.

### Admin security settings (`GET/PUT /api/admin/security-settings`, audit-logged with a diff)
Detector switches (face, multiple faces, gaze, focus, full screen, paste, objects, audio), thresholds (frame rate,
calibration time, gaze record/reminder time, yaw/pitch/eye limits, repeat count/window, face and multiple-face
times, tab-switch minimum, audio minimum speech, minimum confidence), reminder cooldown (30 s), pause rule (pause when
no face for N s, default off - the candidate resumes; never ends or fails an interview), severity caps per event type,
risk weights and bands, recruiter access. Global switches stay in platform settings: `monitoring_enabled`,
`monitoring_camera_required`, `monitoring_retention_days` (also editable on the same screen). Each interview stores a
copy of the settings that applied at consent, so later changes affect new interviews only.

### API (all existing paths kept)
| Method | Path | Who |
|---|---|---|
| GET | `/api/monitoring/policy` | signed in (now includes thresholds, cooldown, pause rule) |
| POST | `/api/student/interviews/{id}/monitoring/consent` | student (returns `elapsed_ms`; re-consent = reconnect) |
| POST/GET | `/api/student/interviews/{id}/integrity-events` | student, own interview |
| GET | `/api/monitoring/sessions?q=&date_from=&date_to=&category=&severity=&review_status=&status=&risk=` | admin, mentor*, recruiter* |
| GET | `/api/monitoring/sessions/{id}` | admin, mentor*, recruiter* (report + summary + events) |
| PATCH | `/api/monitoring/events/{id}` | admin, mentor*, recruiter* (status + notes only) |
| GET/PUT | `/api/admin/security-settings` | admin |

### Tests
* `backend/tests/test_security_module.py` (20): own/other interview, duplicates, malformed events, too many events,
  expired interview, future timestamps, rate limit, reconnect + clock, session events, admin-only settings with
  validation/audit/caps/snapshot, monitoring switched off, recruiter access rules, review history, filters, risk.
* `frontend/src/monitoring/security.test.js` (22): calibration, screen-facing / brief glance / prolonged / repeated /
  flickering / low light / no face, partial face, multiple faces, brief dropout, audio attribution, tab switch,
  network outage, reporter ids/retry/reload/429, reminder cooldown and pause rule. Detector inputs are simulated.
* `backend/tests_e2e/security_module_browser.py`: real browser + real MediaPipe + real AI interviewer, fake camera
  built from the app's synthetic 3D interviewer (frontal, head turned 45°, empty room, two faces) and fake microphone.
  Checks reminders, stored events, reconnect, network outage, recruiter report/timeline/review. Result
  2026-10-23: 22/22 (`output/security_module.json`, screenshots `output/sec_*.png`). Headless Chromium did not hide the
  background tab, so the tab switch there is triggered with the real `visibilitychange` event.

### How to try it yourself (real camera and microphone)
1. Start the app, sign in as a student, start a live interview. Tick *Approximate head direction and gaze* and
   *Possible additional voice*, press *Test my camera and microphone*, then *Calibrate now* while looking at the screen.
2. Tick the notice and start. Turn your head away for ~10 s → reminder after ~8 s; leave the frame ~10 s; let a second
   person appear briefly; switch tabs for a few seconds; switch Wi-Fi off for ~10 s; reload the page.
3. While answering, play a voice from your phone without speaking yourself (mouth still) → possible additional voice.
4. Finish, then check *Interview monitoring* on the report; as a recruiter of a job you applied to, open *Security
   Reports*; as admin, *AI & Monitoring → Interview integrity* and *Security settings*.

### Visual attention percentage (2026-10-25)
A live "Visual attention" card (rolling 30 s, coverage, tracking status, Recalibrate) and an "Estimated visual attention" section in
the candidate's, admin's, mentor's and recruiter's monitoring report (overall %, coverage, away time, timeline). Time-based, unobserved
time kept separate, never changes scores. Details, formula, API, tests and limits: `docs/ATTENTION_MONITORING.md`.

### Known limitations (read before relying on it)
* **Not tested with a real human camera or microphone** in this session - only with synthetic faces and recorded audio.
  Thresholds need tuning on real sessions (glasses, beards, masks, poor webcams, different skin tones and lighting).
* Gaze is approximate (head pose + eye blendshapes). It cannot tell what someone looks at; looking away is normal while
  thinking. It is never above "low" severity.
* Additional-voice detection is a heuristic (one microphone cannot separate speakers). A beard, mask, face partly out
  of view or a quiet candidate can cause false signals; speech between answers is not checked.
* **Identity continuity is not implemented**: it would need face recognition / biometric templates, which this
  platform deliberately does not create. The category exists in the taxonomy; there is no detector.
* A web page cannot see other applications, other devices, other tabs' content, or AI tools; it cannot enforce
  lock-down. A modified browser can suppress or forge events - events are signals, the server validates what it can.
* No evidence images are captured (the least intrusive option): reports contain event metadata only.
* Typed interviews (`/student/interviews/:id`) now show the same notice/device check (`InterviewSetup typed`) and run the same detectors via `monitoring/useTypedMonitoring.js` (no microphone / additional-voice check). Browser E2E `tests_e2e\typed_monitoring_browser.py` passes 14/14 (2026-10-25; Chromium's fake camera shows a test pattern, so it checks the wiring - notice, consent, status bar, self-view, stored `focus_change` event, reconnect - not face detection).
* Not built, on purpose: evidence images (metadata only) and face-recognition identity matching (see above).

---
