# Optimizing TCC behaviour for N52K (NA) + N20-spec converter

Scope: calibration ZB 8646496 (E70 8HP, Bosch ITCU2/SH-2A, cal block 0x180200–0x1FFFFF).
Built on the verified characterization in `tcc_deep_dive.md`. **We have XDF metadata only** —
structure, addresses, axes, and the value ranges quoted in RE notes. No live calibration values,
so every recommendation below is a *direction and a lever*, not a target number. Confidence
ratings (HIGH/MED/LOW) are carried over verbatim from the RE evidence.

---

## 1. Why the turbo-era TCC strategy is wrong for an NA engine

The donor calibration was matched to turbocharged engines (N55/N63-class), where the converter
is deliberately kept in controlled slip through the torque build-up: while the turbo spools, the
converter's torque multiplication (mu quoted up to 1.865 in `tcmodel_mu_curve`; a converter's mu
peaks at stall, though the RE notes do not say where on the axis the maximum sits) and a
non-zero slip target "fill in" the missing low-end torque and hide lag from the driver. This
calibration implements that not with lock-up speed lines (none exist in the XDF — see §5 of the
deep dive) but through a continuously slip-controlled clutch: the slip setpoint path
(`tcc_slip_target_map` + the unlabelled curve at tcc+0x12C + `tcc_slip_cond_map`, summed in
reader 0xDD238, with `tcc_slip_target_curve` feeding a separate rpm slip-target path) schedules how
much slip is tolerated at each slip/torque/pedal/temperature operating point. An N52K makes its
torque immediately and linearly with throttle — there is no lag to mask — so every rpm of
scheduled slip is pure loss: fuel burned into ATF heat, a rubbery pedal-to-driveline connection,
and higher converter/cooler duty. On top of that, the TCU's feedforward plant model
(`tcmodel_K_curve`/`tcmodel_mu_curve`) describes the *original* converter; with an N20-spec
converter installed, that model is wrong until corrected, which degrades slip control accuracy
and drives adaptation (`tccadp_block`) to paper over a hardware mismatch. The correct strategy
for this combination is: fix the plant model first, then schedule earlier/tighter lock through
the slip-setpoint path, bounded by NVH (an NA six lugged at low rpm/high load with a locked
clutch will shudder and boom) and converter thermal limits.

---

## 2. Ordered recommendations

Order matters: 2.1 is a prerequisite for everything after it. All addresses are flash addresses
as quoted in the RE notes; XDF z-data addresses in parentheses where they differ.

### 2.1 Correct the converter plant model for the N20 converter — FIRST

| Item | Addr | Category | Confidence |
|---|---|---|---|
| `tcmodel_K_curve` | 0x1999B0 (z@0x1999CC), 12x1 s16, x turbine rpm 0..15000 | Converter model (`tcmodel_block` @0x181E18, DAT_fff84a10+0x00) | HIGH |
| `tcmodel_mu_curve` | 0x1999E4 (z@0x1999F4), 6x1 s16, x speed-ratio index, z mu ×10000 | Converter model (+0x04) | HIGH |

- **Direction:** replace with the N20 converter's K-factor and torque-ratio curves. We cannot
  say which way the values move without the binary and the converter's data — the correct source
  is either (a) the equivalent curves from a factory calibration that shipped with the N20
  converter (an F-series 8HP45 N20 ZB, if obtainable and the curve format matches), or (b)
  on-car identification: log engine rpm, turbine rpm and estimated engine torque; fit
  K = rpm/√T at matched speed ratios across a stall-to-coupling sweep.
- **Expected effect:** the slip-torque → pressure feedforward becomes accurate, so the PID works
  near zero error. This alone often fixes hunting/soft lock symptoms after a converter swap.
- **Risk:** low mechanical risk (it is a model, not a pressure command), but a *badly* wrong
  curve makes slip control worse than stock — change it from data, never by guess.
- **Validate:** log commanded TCC pressure vs slip error in steady-state micro-slip. Good model
  = small, stable corrections; bad model = sustained offset or slow oscillation. Also check that
  adaptation drift (if observable via diagnostics) stops trending after the fix.
- Note: `tcmodel_block` +0x08/+0x0C "dyn params" exist (HIGH for the block) but their meaning is
  not extracted — leave them alone.
- `tc_torque_ratio_curve` @0x19A854 (LOW, a second mu-like curve outside the five blocks; a
  reader is bound — 0xB9D10 — but its role is unanalysed and the label is only an F object-match)
  plausibly needs the same treatment — log first,
  and only mirror the mu change into it after confirming on-car that leaving it stock causes a
  measurable inconsistency.

### 2.2 Lower the slip targets — the main "de-turbo" lever

| Item | Addr | Category | Confidence |
|---|---|---|---|
| `tcc_slip_target_map` | 0x1A14FC (z@0x1A151C), 6x6 s16, x slip -1000..1200, y torque 800..5000, z 13..21 | Slip setpoint (tcc+0x128, reader 0xDD238) | HIGH |
| `tcc_slip_target_curve` | 0x1A0F88 (z@0x1A0FA4), 6x1 f32, x slip -50..450, z gain 0.5..2.5 | Slip target in rpm (tcc+0xF4, readers 0xDBA7C/0xDBE6E) | HIGH |

- **Direction:** reduce z values, starting in the low-to-mid torque region (the cruise and light
  tip-in cells), in small steps (10–20% per iteration). Do **not** zero the high-torque /
  low-rpm region: an NA six held locked while lugging (roughly the sub-1500 rpm, high-load
  corner) is exactly where driveline shudder and boom appear — keep micro-slip there.
- **Expected effect:** tighter coupling earlier, direct throttle feel, lower ATF heat at cruise,
  a measurable mpg gain on the highway.
- **Risk:** shudder (low-frequency driveline judder) if slip goes too low at high load/low rpm;
  PID oscillation if targets drop faster than the pressure loop can follow (which is why 2.1
  comes first).
- **Validate:** log engine rpm minus turbine rpm (actual slip) at steady 1500–2500 rpm cruise
  and during moderate tip-ins; listen/feel for 5–15 Hz judder; monitor ATF temperature trend on
  the same loop before/after (it should fall).
- The unlabelled curve at tcc+0x12C (likely `auto_cal_curve_s16_1a1564` @0x1A1564, LOW) is the
  second term of the same setpoint sum — it is a lever in principle, and the JSON does bind it
  to reader 0xDD238, but that it occupies the +0x12C slot is not formally proven: log before and
  after any change to the two HIGH items above, and only consider touching 0x1A1564 if the summed
  setpoint clearly misbehaves and on-car evidence ties it to the +0x12C slot.
- Caveat on lookup inputs: the RE evidence strings for `tcc_slip_target_curve` (and
  `tcc_slip_gain_b` in 2.3) quote the lookup argument as `oil_temp_raw/10`, while the quoted
  x-axis labels say "slip" / "pedal/derivative". The ground truth carries both without resolving
  them. If these f32 curves are in fact oil-temperature-scheduled, the tuning picture for them
  changes (cold/warm shaping rather than slip shaping) — confirm with cold-vs-warm logs before
  reshaping either curve.

### 2.3 Speed up setpoint convergence (crisper lock)

| Item | Addr | Category | Confidence |
|---|---|---|---|
| `tcc_slip_gain_b` | 0x1A0ECC (z@0x1A0EE8), 6x1 f32, x pedal/derivative -100..400, z 2.0..4.0 | Slip-target ramp rate (tcc+0xE4, reader 0xDBA7C, ×0.01 per step) | HIGH |

- **Direction:** increase moderately. This is the per-step increment of the slip-target
  accumulator — a larger value ramps the target toward lock faster, which reads as a crisper,
  less "slurred" engagement.
- **Expected effect:** shorter controlled-slip phase after a shift or an unlock event.
- **Risk:** a ramp faster than the pressure loop can track produces a bump or a brief flare at
  engagement. Increase in small steps.
- **Validate:** log slip during the 2 s after an upshift completes; the decay to target should
  get shorter without overshoot (slip crossing through zero and bouncing).
- `tcc_setpoint_curve_a`/`_b` @0x1A1A68/0x1A1A98 (HIGH, reader 0xDAC8C, PT1-filtered setpoint
  targets, z 15759..23593 raw) are part of the same shaping but their scaling is opaque (raw
  u32 tab2 values, meaning of x 0..5 unknown). Log first; treat as a second-round lever only.

### 2.4 Reduce pedal-driven slip opening

| Item | Addr | Category | Confidence |
|---|---|---|---|
| `tcc_pedal_weight_curve` | 0x1A1970-adjacent @0x1A197C (z@0x1A1984), 4x1 u8, x pedal raw 0..255, z 0..100 % | Percent weight on a torque term (reader 0xDA984; that this torque feeds the slip setpoint is inferred from the name/context, not stated in the RE notes) | HIGH |

- **Direction:** flatten/reduce the weight at mid-to-high pedal. On the turbo calibration, big
  pedal input plausibly raises the torque term and with it the scheduled slip (anticipating the
  boost ramp). The N52K's torque arrives instantly, so the converter does not need to open up
  on tip-in nearly as much.
- **Expected effect:** the clutch stays tight through throttle transients; the car feels
  connected instead of "flaring then catching".
- **Risk:** too little compliance on aggressive tip-in at low rpm = harsh driveline shock
  (the compliance the slip provides is also an NVH device). Keep some weight at the
  full-pedal end.
- **Validate:** log slip during 30→70% pedal steps at 2000–3000 rpm in a tall gear; slip
  excursion should shrink; listen for clunk/shock on the same manoeuvre.

### 2.5 Condition-class map — understand before adjusting

| Item | Addr | Category | Confidence |
|---|---|---|---|
| `tcc_slip_cond_map` | 0x1A167C (z@0x1A169C), 6x6 s16, x 40..120, y 60..150, z 0..7 | Third term of the setpoint sum (tcc+0x140, reader 0xDD238) | HIGH |

- **Direction:** none yet. The reader binding is HIGH but the axes (40..120 × 60..150 — both
  plausibly temperatures) are unidentified, and z is a small-integer condition/class term, not a
  physical slip value. Log which cells are active in normal driving first. If it turns out to be
  a temperature-conditioned slip adder (e.g. extra slip when cold), reducing the warm-region
  values is a legitimate second-round refinement.
- **Risk of blind edits:** it may encode regime selection rather than magnitude; wrong edits
  could flip the controller into an unintended state.

### 2.6 Coast-side micro-slip

| Item | Addr | Category | Confidence |
|---|---|---|---|
| `tcc_neg_slip_curve` | 0x1A1970 (z@0x1A1978), 2x1 s16, x -500..-150, z -500..-300 (0.01 scale) | Coast negative slip target (tcc+0x1CC, reader 0xDD208) | HIGH |

- **Direction:** move the coast slip target modestly toward zero (less negative) for more
  consistent engine braking — useful on an NA car driven with the throttle. Only 2 points, so
  changes are coarse.
- **Expected effect:** firmer, more predictable coast/overrun behaviour and better
  rev-matching feel.
- **Risk:** coast shudder and transmitted injector-cut harshness on overrun; also interacts
  with the coast-open thresholds (`tcc_open_speed_slip_map`, LOW — do not touch, §3).
- **Validate:** lift-off at 2500 rpm in 5th/6th; log slip sign and magnitude; listen for drone
  on trailing throttle.

### 2.7 Apply feel: fill and hold pressure — only after 2.1 is confirmed

| Item | Addr | Category | Confidence |
|---|---|---|---|
| `tcc_press_fill_map` | 0x1A15AC (z@0x1A15CC), 6x6 s16, x rpm 1000..6000, y torque -250..300, z 100..150 raw (reader math u/100 → 1.00..1.50 bar; the RE units field says "mbar", an internal inconsistency in the notes — trust the raw counts) | Phase pressure (tcc+0x138, reader 0xDCF6A) | HIGH |
| `tcc_press_hold_map` | 0x1A1614 (z@0x1A1634), 6x6 s16, z 40..100 raw (0.40..1.00 bar) | Phase pressure (tcc+0x13C, reader 0xDCF6A) | HIGH |

- **Direction:** if, after the model fix and slip-target reduction, engagement is still lazy,
  raise fill (and if needed hold) pressure slightly in the cells where the lazy apply is logged.
  Single-digit raw counts (0.01–0.05 bar) per iteration.
- **Expected effect:** shorter fill phase, quicker transition to closed-loop slip control.
- **Risk:** overfill = apply clunk and a torque dip; this is also where crude changes most
  directly fight the adaptation block (tccadp plausibly trims the apply point — see §3).
- **Validate:** log pressure command and slip through an engagement event; the fill→ramp
  transition should shorten without a slip undershoot spike.

### 2.8 PID gains — leave alone unless the loop misbehaves

`tcc_slip_pid_gain_a` @0x1A0D5C (MED, oil-temp-scheduled, reader 0xDB5AA) and its four sibling
curves @0x1A0D80/0x1A0DA4/0x1A0DC8/0x1A0EA4 (LOW, auto-detected) plus the error-scheduled 6x6
maps `tcc_slip_pid_gain_e4`/`_ec` @0x1A07E4/0x1A0974 (LOW, **no bound reader**). With a correct
plant model (2.1) the stock gains should remain stable. Touch only if logged slip shows
sustained oscillation after 2.1–2.3, start with the one MED item, and verify on-car which curve
does what before trusting any LOW label.

---

## 3. Prerequisites and cautions

1. **Reset adaptation after any change in 2.1, 2.2 or 2.7.** `tccadp_block` @0x1824D4 (MED for
   its adaptation role; internal layout and its three curves @0x19E9A0/0x19E9B4/0x19E9D0 are
   LOW/"meaning not analysed"). The TCU has been adapting around the wrong converter model since
   the swap; stale trims will fight your changes and contaminate your logs. Reset via the
   diagnostic adaptation-reset routine (ISTA/scan tool) — do **not** edit the adaptation block's
   bytes in the calibration.
2. **Shudder is the binding constraint, not capacity.** TCC shudder shows up as 5–15 Hz
   longitudinal judder at low rpm / high load with near-zero slip. There is no identified
   shudder-detection calibration in this XDF, so *you* are the detector: every iteration, run a
   1200–1800 rpm high-load pull in a tall gear and log slip at high rate — oscillating slip
   around zero plus felt judder means back off the slip-target reduction in that region.
3. **Thermal:** `tcctemp_heat_coeff_map` @0x19E868 (LOW, no reader — thermal model by name
   only) and `tcc_eng_temp_factor` @0x1A10A0 (LOW, no reader). Do not edit either. Tighter lock
   *reduces* heat, so the thermal direction of this whole project is favourable, but monitor
   ATF temperature during testing anyway.
4. **Do NOT touch (LOW confidence, unbound, or unidentified):**
   - `converter_lockup_curve` @0x19A9D8 — LOW, name is an RE hypothesis, axes unproven.
   - `tcc_close_press_map`/`tcc_close_time_map` @0x19E340/0x19E460 — MED object-match but **no
     bound reader** and unidentified axes (0..4.3?); tempting name, unverified lever.
   - `tcc_open_speed_slip_map`/`_map2` @0x19F31C/0x19F3FC — LOW; label is an F object-match and
     a reader (0xDDDCA) is bound, but their role (coast-open thresholds) is an interpretation of
     the name, not proven.
   - `tcc_conv_capacity_map`, `tcc_coast_torque_map`, the slip-torque factors
     (0x1A12EC/0x1A13B4), `tcc_torque_capacity_drive_coast`, `tcc_press_offset_curve` (shared
     with neutral-idle!), `tcc_output_torque_map`, all `_set0/_set1/_set2` families (the set
     selector is not attributed), `tcc_aux_block` @0x1826A8 (the only per-gear gating evidence,
     layout unproven), `tcc_setpoint_tab2`, and every `auto_*` unlabelled structure.
   - The overspeed protection (`tctrq_*` @0x19AA08–0x19AB8C flash, z-data 0x19AA1C–0x19ABA8) —
     safety, irrelevant to this goal.
5. **No lock-up speed lines exist to edit.** The primary "when does it lock" scheduling is the
   state machine + setpoint path itself; anyone expecting GM/ZF-6HP-style apply/release lines
   will not find them, and should not repurpose the shift-line tables (483 gear-change items in
   the shift-lines group) for it.
6. **Shift lines (noted, out of scope):** the N52K's torque peak sits much higher than a turbo
   engine's plateau, so the gear-change lines themselves will eventually want raising for
   part-throttle response; do that as a separate project *after* the converter work, or you will
   not be able to attribute feel changes to either.
7. **Manual-mode interaction:** nothing in the TCC group is manual-mode-specific in the
   metadata. If the car shows sensor/plausibility faults during manual shifting (see the
   separate sensor-issue investigation), fix that first — slip logs taken while the TCU is in a
   substitute-value or fault-degraded mode are worthless for calibration.

---

## 4. Suggested test procedure (incremental rollout)

Each step: flash one change-set, reset TCC adaptation, drive the standard loop, log, decide.
Standard loop: (a) 10 min mixed urban (engagements/disengagements), (b) steady 100 km/h cruise
5 min, (c) 30→70% pedal steps at 2000 and 3000 rpm in 5th, (d) 1200–1800 rpm high-load pull in
6th (shudder probe), (e) trailing-throttle coast-down from 3000 rpm. Log throughout: engine
rpm, turbine rpm (→ slip), commanded TCC pressure if accessible, pedal, gear, ATF temp.

1. **Baseline:** stock calibration post-swap, adaptation reset, full loop logged twice. This
   log also *characterizes the current lock-up behaviour* (where slip sits per gear/load) and
   exposes the converter-model mismatch (steady-state slip error / pressure offset).
2. **Step 1 — converter model (2.1):** flash corrected K/mu from data. Expect slip-control
   accuracy to improve with no feel change in scheduling. Gate: stable micro-slip, no hunting.
3. **Step 2 — slip targets (2.2), cruise cells only,** 10–20% reduction. Gate: slip at cruise
   drops as commanded, no judder in probe (d), ATF temp equal or lower.
4. **Step 3 — slip targets, mid-torque/tip-in cells** + `tcc_slip_target_curve` shaping.
   Same gates; add the pedal-step manoeuvre (c) explicitly.
5. **Step 4 — ramp/crispness (2.3)** small `tcc_slip_gain_b` increase. Gate: shorter slip decay
   after upshifts without overshoot or bump.
6. **Step 5 — pedal weight (2.4):** reduce mid-pedal weighting. Gate: smaller slip excursion in
   (c) without tip-in clunk.
7. **Step 6 (optional) — coast slip (2.6), then apply pressures (2.7)** only if logs show a
   specific lazy-apply or coast complaint. One table per flash.
8. **Regression after each step:** cold-start drive the next morning (oil-temp-scheduled items
   dominate when cold), and re-run the shudder probe after ~200 km, because re-converged
   adaptation can shift the operating point from your freshly-reset test logs.
9. **Back-out rule:** any judder, hunting, or new fault code → revert the last single change,
   re-reset adaptation, re-baseline. Never stack an edit on top of an unexplained symptom.
