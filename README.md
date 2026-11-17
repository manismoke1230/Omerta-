# SAY LESS. — Omertà Academy collection film

A 24-second, 60 fps collection ad built entirely in code from eight garment photographs. Deterministic 2.5D renderer in Python; original music and sound design synthesised in NumPy. No AI-generated video.

Source brief: *Omertà Academy / Say Less / Motion Ad Production Prompt* (PDF).

## Status

Review stage. Storyboard, animatic and full-resolution preview exist for both aspect ratios. Final masters are intentionally not exported: the brief gates them on approval, and three inputs are open (hero garment, approved O mark, voice). See [`docs/03_missing_inputs.md`](docs/03_missing_inputs.md).

| | |
|---|---|
| One-page brief | [`docs/01_brief.md`](docs/01_brief.md) |
| Asset map | [`docs/02_asset_map.md`](docs/02_asset_map.md) |
| Missing inputs | [`docs/03_missing_inputs.md`](docs/03_missing_inputs.md) |
| Sound cue sheet | [`docs/cue_sheet.md`](docs/cue_sheet.md) |
| Storyboard | `review/storyboard_landscape.jpg`, `review/storyboard_portrait.jpg` |
| Animatic | `review/animatic_landscape.mp4`, `review/animatic_portrait.mp4` |
| Contact sheets | `review/contact_landscape.jpg`, `review/contact_portrait.jpg` |
| Handoffs, frame by frame | `review/transitions/` |
| Frame checks | `review/qc_landscape.json`, `review/qc_portrait.json` |

## Run it

```bash
pip install -r requirements.txt        # NumPy, Pillow, OpenCV; FFmpeg must be on PATH

python -m sayless inventory            # the eight garments and their mattes
python -m sayless mattes               # review/mattes.jpg
python -m sayless storyboard           # nine frames + captioned sheet, both formats
python -m sayless audio                # out/audio/: master, stems, report
python -m sayless animatic             # review/animatic_*.mp4  (half resolution, burn-ins)
python -m sayless preview              # out/preview_*.mp4      (full resolution, review slate)
python -m sayless contact              # review/contact_*.jpg
python -m sayless transitions          # review/transitions/*.jpg
python -m sayless qc                   # review/qc_*.json; non-zero exit if a check fails
python -m sayless final --approved     # clean masters; refused while stand-ins remain
```

Add `--format landscape` or `--format portrait` to do one. Everything is deterministic: the same inputs give the same pixels and the same samples.

Tested with Python 3.13.18, NumPy 2.5.3, Pillow 12.3.0, opencv-python-headless 5.0.0.93, FFmpeg 6.1.1, on 4 cores. A full-resolution pass of one format takes a few minutes.

## How it works

```
sayless/
  config.py      timing grid (100 BPM, 2.4 s bars), palette, formats, copy, VO timings
  matte.py       background removal for the supplied photos (border flood + edge unmixing)
  assets.py      garment textures, anchor points on the artwork, shadows, O-mark extraction
  layout.py      the tableau: where each garment lies, per aspect ratio
  film.py        the score: stitch route, camera moves, light cues, fabric wipes, copy timing
  camera.py      one shared camera; long eased moves with a single brief acceleration
  thread.py      the stitch: draw_thread(time, layout), one continuous progress value
  render.py      compositor: stage, shadows, garments, stitch, copy, motion blur, grain
  typeset.py     supersampled type with tracking
  review.py      burn-ins, storyboard and contact sheets
  export.py      multi-process rendering, H.264 Rec.709 encode, audio mux
  qc.py          checks over all 1,440 frames
  audio/score.py music and sound design synthesis
  audio/mix.py   stems, voice ducking, -14 LUFS / -1 dBTP mastering
```

**The stitch.** `ThreadPath` is one world-space curve through the whole collection. `draw_thread(time, layout)` draws it from its start to `progress(time)`, which is monotone, so the stitch never restarts or runs backwards. Depth is real: loose thread is drawn under the garments (it slips beneath hems and sleeves), running stitches are drawn over the fabric as dashes, and between two garments the thread can lift toward the lens, larger and out of focus, then settle back onto the stage.

**The camera.** One list of moves in `film.py`, written against garment anchors, so the same score plays on both layouts. No cut exists anywhere; handoffs are fabric crossing the lens, matched details and changes of scale.

**Honesty rules built into the code.**

- A lit garment is drawn at exactly its photographed colour. Only unlit neighbours are dimmed.
- Only front views exist. Nothing rotates out of plane and no cloth deformation is simulated.
- `layout.max_zoom()` caps detail shots by source resolution.
- Review builds carry a slate naming every stand-in. `final` refuses to run while one remains.

## Changing things

| To change | Edit |
|---|---|
| A garment photo | replace the file in `assets/garments/source/`, keep the name |
| Matte settings, or paint a mask by hand | `assets/garments/manifest.json`, or `assets/garments/masks/<key>.png` (white = garment) |
| Where the stitch runs on a garment | `ANCHORS` in `sayless/assets.py` (coordinates are fractions of the cutout) |
| Garment positions and sizes | `SPECS` and `HEIGHTS` in `sayless/layout.py` |
| Timing of any move, light cue or wipe | `sayless/film.py` |
| Approved O mark | add `assets/brand/o_mark.png` (RGBA) |
| Voice | add `assets/voice/voice.wav`, or `line_1.wav` … `line_6.wav`, then `python -m sayless audio` |
| Fonts | files in `assets/fonts/`, paths in `sayless/config.py` |

## Licences

Fonts: Anton and Inter, SIL Open Font License 1.1 (texts in `assets/fonts/`). Music and sound design are original and generated by this repository. Garment images and brand artwork belong to Omertà Academy.
