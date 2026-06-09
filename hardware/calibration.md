# Calibration

One-time per-unit setup after assembly. Skeleton — paste actual numbers from your build into the TODOs.

## Servo zero positions

Each STS3215 needs a zero-offset captured for the kinematics in `lelamp/follower/` and `lelamp/leader/`. Procedure:

1. Power up the lamp. Do not start the lelamp service yet (it grabs the bus).
2. Manually move each joint to its mechanical zero (defined per joint — TODO: photo per joint).
3. Run the calibration tool: TODO command.
4. Calibration files land in `~/.cache/huggingface/lerobot/calibration/` and are read by `lelamp/calibration/`.

| Servo | Joint | Mechanical zero | Recorded offset |
|---|---|---|---|
| 1 | base yaw | TODO | TODO |
| 2 | shoulder | TODO | TODO |
| 3 | elbow | TODO | TODO |
| 4 | wrist | TODO | TODO |
| 5 | head tilt | TODO | TODO |

## Microphone gain

### Voice mic (USB)
- Initial: `amixer -c <usb_card> sset Mic 50%`
- Tune until utterances peak at ~−12 dBFS in your room.
- Recorded value: TODO

### Sensing mic (onboard)
- On Raspberry Pi: a watchdog clamps wm8960 capture gain to 160 — see `project_lumi_pcm_watchdog.md`. Don't fight it.
- On OrangePi: TODO — measure ambient noise floor and pick gain.

## Speaker volume

- Set DAC level once, then leave it. lelamp's `set_volume` adjusts a software gain on top.
- OrangePi safe defaults (from `project_orangepi_lelamp_dac_cap.md`):
  - `amixer -c 1 sset 'ADC2DAC Mixer' 0`
  - `amixer -c 1 sset 'ADCL/R PGA' 10` (≈ 30 dB)
  - `amixer -c 1 sset DACL/R 70%` (≈ −6.5 dB)
- Pi defaults: TODO

## LED brightness cap

- Maximum allowed: TODO % of max (limited by 5 V rail headroom — see [`power.md`](power.md)).
- Capped in `lelamp/service/rgb/rgb_service.py` — confirm the constant matches what the rail can deliver.

## Camera focus

- IMX307 USB module is fixed-focus; nothing to do.
- If image is soft, check the lens isn't loose in its mount.

## Verification

After calibration:
- [ ] Each joint reaches its commanded position within ±2°
- [ ] No clipping during normal-volume TTS
- [ ] LED ring at full white doesn't brown out the SBC
- [ ] No audible hum at idle volume

## TODO

- [ ] Capture command names for the servo calibration tool
- [ ] Joint-zero photos
- [ ] Final amixer values per board
