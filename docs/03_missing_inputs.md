# Missing inputs and open decisions

Ordered by how much each one blocks final export.

## 1. The hero garment

The brief's hero is a **burnt-orange pile-textured track jacket** (dark piping, script, silver hardware). The eighth image supplied is a **navy hoodie with a cream and orange chest band**. No track jacket image was received.

What is in the cut now: the hoodie plays the hero. Scene 07's "follow the existing dark piping" became "follow the chest band", and the stitch rides the band's top edge under both drawcords.

Decide one:

- **Supply the track jacket image.** It replaces `assets/garments/source/hoodie_stripe.jpg`; the hero anchors in `sayless/assets.py` (`ANCHORS["track"]`) get re-picked on its piping. About an hour of work plus a re-render.
- **Confirm the hoodie as hero.** Set `"matches_brief": true` under `"hero"` in `assets/garments/manifest.json`.

## 2. An approved O mark and wordmark

No separate logo file was supplied. The end card currently shows:

- an O **extracted from the charcoal long-sleeve print** (worn specks closed, outline smoothed, nothing redrawn) — `assets/brand/o_mark_extraction.png`;
- `OMERTÀ ACADEMY` set in Anton as plain text.

Supply a vector or high-resolution transparent PNG of the O (and the wordmark, if one exists) and they go in unchanged: drop the O at `assets/brand/o_mark.png`.

## 3. Voice

The six lines are not recorded; review cuts show them as captions at the brief's start times. No text-to-speech service is reachable from this environment, and none was used.

Decide one:

- **Record it.** Put one aligned take at `assets/voice/voice.wav`, or six files `line_1.wav` … `line_6.wav` (each is placed at its start time). The mix then ducks the music at least 12 dB under the voice automatically.
- **Authorise a TTS account** and supply its output the same way.
- **Run without voice.** The brief marks voiceover as optional.

Also needed: confirmation that *Omertà* is pronounced "oh-mehr-TAH".

## 4. Higher-resolution garment images

Every source is about 1206 px wide, with the garment itself 900–1100 px across. That is enough for full-garment framing at 1080p (shown at roughly 1:1) but not for true close-ups. Consequences in the current cut:

| Shot | Enlargement of the photo | Effect |
|---|---|---|
| Opening on dark knit (0.0–0.5 s) | 3.2× | fabric is soft; it is dark, moving and behind a sharp stitch |
| Bomber zip pull | 1.3× landscape / 1.4× portrait | a modest push-in, not a macro |
| Plaid line, denim entry | 1.5× | acceptable |
| Everything else | ≤ 1.1× | clean |

Originals at 3000 px or more would allow the tight detail crops the beat sheet implies.

## 5. An uncropped bomber image

The supplied bomber photo cuts off the top of the hood at the frame edge. It shows as a flat hood top.

## 6. Brand typography

Anton (display) and Inter (small text) are openly licensed stand-ins. If the brand has licensed faces, supply the font files.

## 7. Copy check

The brief writes the call to action both with and without a full stop. The cut uses `EXPLORE THE COLLECTION.` (with), matching the brief's TYPE + COPY section.

## 8. Platform safe areas

Portrait copy is held inside 120 px (sides), 180 px (top), 300 px (bottom). The brief asks for this to be verified against the intended platform's overlay; the platform has not been named.

## Not done, by design

- No final masters. The brief gates them on preview approval; `python -m sayless final` refuses until the hero and O mark are settled and `--approved` is passed.
- No Resolve timeline. The brief makes it on-request only.
- No paid services or purchases were used.
