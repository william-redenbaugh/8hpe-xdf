# Patches — E84 (GKE233, cal 8609556)

E84 counterpart of [the E70 chapter 10](../../e70/parameters/10-patches-stage3.md). The E70 chapter had four pillars: two one-click patches, the Radumfang constant, a 108-item **stage 3** folder mirroring a commercial (xHP-style) E70 tune, and 20 **Additional maps**. On the E84 only a fraction of that is applicable, and this chapter is mostly about what is *not* there and why:

- One patch survives, rebuilt on the native E84 shift-line structure and explicitly **[PARTIAL]**.
- **True manual was not ported** — and at a 7000 rpm target you do not need it.
- The **stage 3 / Additional maps content is an E70 artifact**: it visualizes where an xHP OTS calibration for the E70 (cal 8646496) differs from E70 stock. No E84 tune was diffed, so those folders survive only as remnants (1 + 4 items).
- Radumfang lives in the XDF's "Patches (click to apply)" folder as on the E70, but is documented with the other vehicle constants in [the signals chapter](09-signals-diagnosis.md): u16 at **0x191404**, stock **2003 mm** (225/50R17).

**Checksums changed.** The E70 rule ("recompute the CRC after all patches; declared CRC32 at 0x180244") does **not** carry over: the E70 checksum algorithm does not reproduce on this calibration-only E84 read — `xdf_checksum.py`'s algorithm search fails — and `cal_declared_crc32` is not in the E84 XDF. Sign via the flash tool instead (xHP corrects checksums itself on write). Until a full flash read lets the algorithm be recovered, treat any hand-patched E84 image as unsigned bytes that only the flasher can make valid.

Patches are still pure overwrites with no base-data restore, so **work on a copy of your stock read**. Apply in TunerPro, or from the CLI: `tools/xdf_patch.py 8hpe84_cali_v1.xdf my.bin --show "Start in 2nd"` to preview, `--apply` to write.

### [PATCH] Start in 2nd (E84) [PARTIAL]

44 entries, rebuilt on the **native** E84 shift-line structure (21 characteristics, not the E70's 23 — see the shift-lines chapter). What it writes:

| Edit | Bytes | E84 addresses |
|---|---|---|
| Zero the 1↔2 shift lines of all 21 characteristics | 42 slots x 15 u16 = 1260 bytes | char00 up 1>2 @0x1DBA68, dn 2>1 @0x1DBA86 (= up + 0x1E); +0x12C (300 B) per characteristic: char01 @0x1DBB94/0x1DBBB2 … char20 @0x1DD1D8/0x1DD1F6 |
| Min-gear floor byte | 1 byte, value 02 | 0x1E036F |
| One car-2nd min-speed word zeroed | u16 = 0000 | 0x1D791E (`min_speed_col1_t0_r4`) |

Two of the 21 characteristics (blocks 15 and 16) already have all-zero 1>2 stripes at stock — verified in the E84 read at 0x1DCBFC and 0x1DCD28 — which is one reason they are suspected to be the manual-mode characteristics. The patch zeroes all 21 anyway, since the characteristic-to-drive-mode mapping lives in the missing program ROM.

**What is missing, and the behaviour risk.** The E70 version of this patch carried 97 entries, and its R1–R5 on-car trail proved the point the hard way: zeroing the shift lines alone (R1) changed nothing — the car still pulled away in D1, because the gear-availability layer clamps the request. Only the later entries (the inhibit vector, the floor byte with its companion word at E70 0x1CD938, and all 45 car-2nd min-speed words) finally made 2nd available at 0 speed. Of those 51 auxiliary entries, **only 2 could be located in the calibration-only E84 read; the other 49 inhibit/min-speed entries could not be ported and are omitted** (the XDF patch description says the same). In particular 44 of the 45 min-speed words and the E70 0x1CD938 companion are unresolved. Realistic expectation: this partial patch may reproduce the E70 R1 result — lines zeroed, car still launching in 1st — rather than a working 2nd-gear start. Nothing in it is dangerous (it only disables 1↔2 scheduling and relaxes one availability word), but treat it as an experiment: apply, drive, log the launch gear, and expect to need a full flash read to finish the job.

### True manual: not ported, and why you likely don't need it

The E70 `[PATCH] True manual` (remove the TCU-side forced upshift at redline in manual mode) is **not in the E84 XDF**. Six of its seven entries could not be resolved on this read — **including both overspeed limits** (E70 0x1CECA4/0x1CECA6), the df32 margin seeds, the rev-match latch arm and the df31 gate; they are small code-anchored constants that none of the porting methods could pin down without the program ROM. The one piece that did port is the `strat_state_attr_3` table (the E70 "K0 lever", now at 0x1D5444, HIGH confidence) — but on the E70 evidence that lever only works together with the df32 margin seeds, so shipping it alone would be a patch that silently does nothing. Hence: dropped rather than shipped broken.

The practical mitigation: **the stock TCU guard sits at ~7100 rpm** (E70 code evidence: guard test 1's threshold word, stock 7100 — inherited, since the E84 word itself could not be located). Holding 1st and 2nd to **7000 rpm never trips it**, so for an N52K/N20-style NA setup revving to 7000 you do not need True manual at all. That is exactly what the native tooling does:

```
tools/xdf_tune.py sport-redline my.bin -o out.bin --rpm 7000
```

raises the 1>2 and 2>3 upshift lines to rpm/ratio from 400 permille pedal up (`--pedal-from`, `--chars` to limit characteristics). It edits the native E84 slots, stays under the ~7100 guard, and leaves the forced-upshift protection intact as a safety net. Caveat worth repeating: the 7100 figure is an E70 program-ROM fact from the same software generation; it is plausible but unverifiable on this read, so leave yourself the 100 rpm margin rather than tuning to 7099.

### stage 3: E70-only content

The E70 stage-3 folder existed to show, in one place, every map a commercial E70 stage-3 calibration touches. None of that transfers: the diff is against the **E70** cal 8646496 and the OTS values target an X5 — on the E84 they would be wrong even where the objects exist. Of the E70's 108 entries, 66 were duplicate views of objects documented in their own sections (shift lines, blip maps, …) and are handled there; of the stage-3-only objects, **41 are not in the E84 XDF (needs full flash read)** — that includes the shift torque-limit classes (`shift_torque_limit_class0..3` + fallback), all `shift_type_cond_records`, `shift_type_thresholds`, `per_gear_torque_rows`, `shift_element_pair_b`, `tc_torque_ratio_curve` and the gearsel small objects. These were the packed, code-anchored structures the port could not safely locate.

What survives in the E84 "stage 3" folder is exactly **1 item**: `strat_state_mask_vec` @0x1D7194 (u16, LOW, ported by interval match) — kept because it ported cleanly, not because a stage-3 value for it exists on this platform. If you want an E84 stage-3 equivalent, the honest route is to diff an actual E84 xHP read against this stock read, not to copy E70 numbers.

### Additional maps: remnants

4 of the E70's 20 items ported; all four are "the tune changes something here" markers, not understood maps:

| Parameter | E84 address | What it is | Confidence |
|---|---|---|---|
| `cal_trailer_ptr_triple` | 0x180266 | five s16 in the header area; meaning not proven | LOW |
| `xhp_gap_a_obj` | 0x19A024 | 10 u16 behind a data pointer, no reader found | LOW |
| `xhp_gap_b_obj` | 0x1B3EF8 | the u32 count word of the E70 0x1AE9EC flag block | LOW |
| `strat_state_mask_vec` | 0x1D7194 | same object as the stage-3 entry above (duplicate view) | LOW |

Header-area rule of thumb carries over: do not creatively edit `cal_trailer_ptr_triple` — and note that `xhp_gap_b_obj` ported while the 50-u16 `shiftexec_state_flag_tbl` block it counts did **not**, so there is nothing useful to do with it.

The 16 dropped items are **not in the E84 XDF (needs full flash read)**: `cal_declared_crc32`, `cal_id_string`, `gear_display_digit_rule`, the `gearsel_*` quartet, the three `shift_torque_headroom_*` curves, `intervention_element_thr_by_index`, `shiftexec_state_flag_tbl`, `strat_state_mask_tbl`, `escalation_test1_threshold`, `shiftprog_phase_2to3_flag` and `shiftprog_param_block_mask`. One consolation: the function behind `gear_display_digit_rule` (make the cluster show the actual gear number) exists on the E84 as the `disp_gear_src_v0/v1/v2` selectors @0x193F7C/0x193F84/0x193F8C — see [the signals chapter](09-signals-diagnosis.md).

Coverage: 7 XDF items — 2 in Patches (click to apply) (the Start-in-2nd patch with its 44 entries, plus the Radumfang constant documented in chapter 09), 1 in stage 3, 4 in Additional maps. True manual, the stage-3 map list and 16 of 20 Additional maps did not survive the port and are flagged above. Every address was verified against `8hpe84_cali_v1.xdf`.
