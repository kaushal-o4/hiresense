# Visual attention monitoring (added 2026-10-25)

An estimate of how much of the interview the candidate's head and eyes were directed toward the screen, shown live
and in the post-interview report. It extends the existing interview security module ([INTERVIEW_SECURITY.md](INTERVIEW_SECURITY.md)); nothing was
rebuilt. Labelled everywhere: **"Estimated visual attention toward the interview screen."**

## What it is built on (already in the project, reused)
| Part | Choice |
|---|---|
| Detector | **MediaPipe Face Landmarker** (`@mediapipe/tasks-vision` 1.0.1), running in the candidate's browser; model files served from `frontend/public/models` / `public/mediapipe`. No new dependency, no API, no paid service, no frames leave the browser. |
| Signals | face count and position, 478 face landmarks, facial transformation matrix (head yaw/pitch), eye-direction blendshapes (`eyeLook*`). It does **not** track the pupil or know what is on the screen. |
| Camera | the existing single stream (`monitoring/mediaSession.js`); one analysis loop (`monitoring/faceMonitor.js`, 2 analyses/s, admin-configurable). |
| Calibration | existing: the candidate's median head and eye position over 5 s is the baseline; deviations are measured from it. Can now be repeated with **Recalibrate** on the live card. |

## Method
1. Each analysed frame is classified (`monitoring/attentionMeter.js` → `classifyFrame`):
   `toward` / `away` (one face, good light, angles within limits of the calibrated position) or an unobserved state:
   `face_not_visible`, `low_confidence` (several faces, face cut by the frame edge, dark picture, no head angle,
   blocked camera), `unavailable` (the detector failed). Frames during calibration or pause are outside the numbers.
2. `AttentionMeter` turns samples into **elapsed time**: a state holds until the next sample but never longer than
   `attention_max_gap_ms` (2.5 s); a longer silence becomes unobserved "gap" time. Frame rate, duplicate and
   out-of-order samples therefore cannot change the result.
3. A change between toward and away must last `attention_confirm_ms` (1 s) before it counts, so a blink of the detector
   or a natural glance does not move the percentage. (Sustained deviations of 3 s+ become reviewable events through the
   existing `SignalTracker`; a reminder appears after 8 s with a 30 s cooldown, as before. Nothing is penalised.)

## Formula (live indicator and report use the same one)
```
attention %  = time toward the screen / (time toward + time away)          valid observations only
coverage %   = (time toward + time away) / (time toward + away + unobserved)
```
* Live value: the last `attention_window_s` (30 s, configurable 10-300). It is shown only with at least 5 s of valid
  time in the window **and** at least 1.2 s of valid observation in the last 2 s; otherwise the card says "Collecting
  observations…" or "Attention estimate temporarily unavailable." An old value is never shown as current.
* Whole interview: totals over all valid time, not an average of window percentages. Unobserved time is reported
  separately and is **never** counted as attention or as looking away. Paused and calibration time are outside both.
* Example: 24 s toward + 6 s away = 80%. With 10 more seconds without a face: attention still 80%, coverage 75%.

## Where the data goes
* The browser sends **cumulative time totals** (never frames, landmarks or coordinates) every 10 s and when monitoring
  stops: `PUT /api/student/interviews/{id}/attention`. Per monitor run ("epoch"; a page reload starts a new one) it
  holds five totals, four unobserved reasons and ≤720 ten-second buckets (≤ 12 KB).
* Stored in the existing `interview_sessions.monitoring` JSON under `attention` - **no migration**. Retention follows
  `monitoring_retention_days` (purged with the integrity events). Source is labelled `client`.
* The server accepts a snapshot only if: it belongs to the signed-in student's own interview, the candidate consented to
  the gaze feature and has not withdrawn, the interview is running (or ended < 3 min ago), totals never decrease within a
  run, the sum of all time cannot exceed the interview clock (+30 s), buckets cannot exceed their length, and ≤ 30
  updates/min. **A modified browser can still send false totals; the figure is a signal, not tamper-proof evidence.**
* Prolonged-deviation events, camera interruptions and tracking failures come from the existing `integrity_events` table.

## Who sees what
Same rules as the rest of monitoring: the candidate (own interview, in "Interview monitoring"), admins, mentors with
`review_integrity` for their students, and recruiters only for **completed** interviews of their own applicants when
recruiter access was disclosed at consent. Another student gets 404; a student on the reviewer endpoint gets 403.
It is kept apart from interview scores and is never used to reject, fail or end an interview.

## API
| Method | Path | Who |
|---|---|---|
| PUT | `/api/student/interviews/{id}/attention` | student, own interview |
| GET | `/api/student/interviews/{id}/integrity-events` → `attention` | student, own interview |
| GET | `/api/monitoring/sessions/{id}` → `attention` | admin, mentor*, recruiter* |

## Settings (admin → Security settings → thresholds)
`attention_window_s` (30), `attention_confirm_ms` (1000), `attention_max_gap_ms` (2500), plus the existing
`calibration_ms`, `gaze_yaw_deg`, `gaze_pitch_deg`, `gaze_eye`, `gaze_record_ms`, `gaze_warn_ms`, `frame_rate`,
`warning_cooldown_s`. All defaults are engineering choices, **not validated against real candidates**.

## Files
Created: `frontend/src/monitoring/attentionMeter.js`, `attentionMeter.test.js`, `AttentionPanels.jsx`;
`backend/app/services/attention.py`; `backend/tests/test_attention.py`; `backend/tests_e2e/attention_browser.py`.
Modified: `interviewMonitor.js` (meter, 1 s tick, recalibrate, pause, final upload), `eventReporter.js` (upload),
`MonitorBar.jsx` (live card, student report), `pages/shared/IntegrityReview.jsx` (reviewer report),
`pages/admin/SecuritySettings.jsx`, `backend/app/routers/monitoring.py`, `schemas.py`, `services/integrity.py`
(3 thresholds), `frontend/vite.config.js` (`HS_API` override for a second test backend; default unchanged),
`backend/tests/conftest.py` + `test_latency_and_monitoring.py` (see "Test fix" below).

## Tests and results (2026-10-25, this laptop)
| Test | Result |
|---|---|
| `attentionMeter.test.js` (23): 24+6 s = 80%, 15+15 = 50%, frame-rate independence, uneven spacing, duplicates, missing frames, no face / low confidence / unavailable kept separate, dead camera = unavailable not 0%, stale value hidden within ~1 s of losing the face, minimum data, rolling-window expiry, configurable window, glance debounce, pause and calibration excluded, snapshot monotonic/integer/consistent, bucket splitting, frame classification | 23/23 pass |
| `test_attention.py` (20): formula and unobserved handling, runs adding up, too-little-data, monotonic totals, clock limit, 8 malformed payloads, ownership and consent, reload keeps totals, events and tracking failures in the report, no data = unavailable, rate limit, recruiter/admin/stranger access, retention purge | 20/20 pass |
| Whole backend suite | 274 pass (two consecutive runs); frontend 124 unit tests pass; production build OK |
| `tests_e2e/attention_browser.py` (real Chromium, **real MediaPipe**, real backend, fake camera playing the app's synthetic 3D face: facing 25 s, head turned 15 s, facing 20 s, empty room 10 s, facing 20 s, then a page reload) | 13/13: stored 83% vs 82% from an independent count made by the test; looking away 15.3 s for a 15 s turn; empty room 9.4 s recorded as *face not visible*, not as attention or away; one deviation event; coverage 91%; live card "Face not detected / estimate unavailable" with no stale value; reload added a second run; student denied on the reviewer endpoint (403); no unexpected console errors |
| Existing `security_module_browser.py` (regression) | 22/22; the recruiter's report for that interview shows 76% attention, 85% coverage, 2 runs, 14 timeline blocks |
| Cost of the meter | 2 µs per frame (14,400 frames = 2 h of interview: 29 ms in total); snapshot 0.3 ms |
| Backend log of the browser runs (2 attention runs + the security run) | 43 attention uploads, all `200 OK`; no error lines |

**Test fix found on the way:** `test_latency_and_monitoring.py` crashed the interpreter in 3-4 of 10 runs while I was
testing this feature (a segfault or "bad parameter or other API misuse" inside the request that starts a live
interview; the traces show the `prefetch-N` thread and the request's worker thread). The cause is the test setup: the
first-question prefetch thread and the request that started it share ONE in-memory SQLite connection (this was before the move to MongoDB; production gives
each thread its own). I did not run the old code to check whether it flaked before my changes; none of the changed
code appears in the traces. The prefetch now runs inline in tests only (`conftest._prefetch_runs_inline`); 0 failures in
10 repeated runs afterwards and two clean full-suite runs. Production code is unchanged.

## Known limitations - read before relying on it
* **Never tested with a human face or a real webcam.** The fake camera is a rendered 3D character; it cannot show
  glasses, beards, masks, skin-tone or lighting differences, a webcam at the side, a laptop on the knees, or
  real eye movements. The thresholds (30° yaw, 25° pitch, 0.6 eye offset, 1 s confirm, 2.5 s gap) need tuning with
  real sessions before anyone relies on the numbers. Test with your own camera: the steps in [INTERVIEW_SECURITY.md](INTERVIEW_SECURITY.md) "How to try it yourself".
* Gaze is approximate (head pose + eye blendshapes); it cannot tell what the candidate is looking at. People look away
  while thinking. Looking at a second monitor beside the camera reads as "away" unless that was the calibrated position.
* Several faces, a face cut by the frame, a dark picture, or a blocked camera are treated as *not observable*, so the
  percentage is simply unavailable then (and coverage drops) - it is not a judgement about the candidate.
* When the face first disappears the live card keeps the old value for up to ~1 s (blink tolerance), then shows unavailable.
* The overall figure includes only time with monitoring on; if the candidate stops monitoring or the browser tab sleeps,
  that time is missing (coverage shows it). Hidden tabs are throttled by the browser and show up as unobserved "gap" time.
* Speed on weaker or older laptops, with the 3D avatar and the voice models running, has not been measured; the analysis
  rate lowers itself on slow devices (existing behaviour).
* Accommodation: a candidate who cannot use camera monitoring is told to contact the placement cell (existing policy
  text). There is no automated accommodation workflow.
* Not built, on purpose: any use of the figure to score, rank, reject or end an interview; emotion or honesty inference;
  face recognition; saving video or landmarks.

## How to run and verify
1. Start the backend and frontend as usual (`start.bat`), sign in as a student, start a **live** interview, tick
   *Approximate head direction and gaze*, test the camera, **Calibrate now** while looking at the screen, start.
2. The *Visual attention* card appears under the status chips. Look at the screen, then turn your head away for ~10 s,
   leave the frame for ~10 s, then return. The percentage should dip, then the card should say unavailable while no face
   is visible, then recover. **Recalibrate** repeats the calibration.
3. Finish the interview; open *My Interviews → report → Interview monitoring* for the whole-interview figure and timeline.
4. As the recruiter of a job you applied to: *Security Reports* → the interview → the *Estimated visual attention* panel.
5. Automated: `cd backend; .\venv\Scripts\pytest tests/test_attention.py`; `cd frontend; npx vitest run`; browser test
   (own servers): start `uvicorn app.main:app --port 8001`, `HS_API=http://127.0.0.1:8001 npx vite --port 5174`, then
   `HS_E2E_BASE=http://localhost:5174 .\venv\Scripts\python.exe tests_e2e\attention_browser.py`.
