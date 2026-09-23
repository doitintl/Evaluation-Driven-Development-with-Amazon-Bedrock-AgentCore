#!/usr/bin/env python3
"""Draw focus highlights on workshop screenshots.

Participants scan a screenshot for a second or two. A rectangular highlight on
the ONE region that matters turns "here is a console" into "look here". This
script draws that box (plus an optional numbered badge) from a declarative spec,
so the annotation is reproducible when a screenshot is recaptured.

Coordinates are given as FRACTIONS of width/height (0.0-1.0), not pixels, so a
spec keeps working if the screenshot is recaptured at a different resolution.

Usage:
  python3 annotate_screenshots.py                 # annotate everything in SPECS
  python3 annotate_screenshots.py --list          # show the spec, change nothing
  python3 annotate_screenshots.py <image-key>     # just one

Source images live in images/_sources/<name>.png when a source copy exists,
otherwise the shipped image is used as its own source and a source copy is made
first, so re-running never double-draws.
"""
import sys
import shutil
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

STATIC = Path(__file__).resolve().parents[1] / "static"
IMAGES = STATIC / "images"
SOURCES = IMAGES / "_annotate_sources"

ACCENT = (255, 90, 0)      # AWS-ish orange, reads on both light and dark console chrome
ACCENT_SOFT = (255, 90, 0, 40)
STROKE = 4
RADIUS = 8

# name -> list of boxes. Each box: (x0, y0, x1, y1) as fractions, plus a label.
# Keep to 1-2 boxes per image: more than that and nothing stands out.
SPECS = {
    "module-1/1a-trace-waterfall.png": [
        # the span tree: the actual trajectory, which is the point of the image
        {"box": (0.315, 0.40, 0.585, 0.61), "label": "1"},
        # service.name in the OpenInference resource attributes
        {"box": (0.615, 0.555, 0.99, 0.615), "label": "2"},
    ],
    "module-2/eval-scores-expected.png": [
        # the three score rows: the evidence that sessions were scored
        {"box": (0.155, 0.275, 0.655, 0.385), "label": "1"},
    ],
    "module-1/00-genai-obs-before.png": [
        # 1: the span-ingestion callout. This is the meaningful "before" signal:
        # it names the reason the dashboard is empty. (The old spec pointed at a
        # row of zeroed OTEL metrics that the console no longer renders in this
        # state, so the box pointed at nothing.)
        {"box": (0.125, 0.368, 0.995, 0.478), "label": "1"},
        # 2: the visible consequence, "No data / Enable Transaction Search"
        {"box": (0.505, 0.666, 0.620, 0.733), "label": "2"},
    ],
}


def _font(size):
    for candidate in (
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ):
        if Path(candidate).exists():
            try:
                return ImageFont.truetype(candidate, size)
            except OSError:
                pass
    return ImageFont.load_default()


def annotate(rel_key, boxes):
    shipped = IMAGES / rel_key
    if not shipped.exists():
        print(f"  SKIP  {rel_key}: not found")
        return False

    source = SOURCES / rel_key
    if not source.exists():
        source.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(shipped, source)
        print(f"  saved source copy -> {source.relative_to(STATIC)}")

    im = Image.open(source).convert("RGB")
    W, H = im.size
    overlay = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    badge_font = _font(max(18, H // 34))

    for spec in boxes:
        x0, y0, x1, y1 = spec["box"]
        px = (x0 * W, y0 * H, x1 * W, y1 * H)
        d.rounded_rectangle(px, radius=RADIUS, outline=ACCENT + (255,), width=STROKE)
        label = spec.get("label")
        if label:
            r = max(15, H // 40)
            cx, cy = px[0] + r + 2, px[1] + r + 2
            d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=ACCENT + (255,))
            tb = d.textbbox((0, 0), label, font=badge_font)
            d.text(
                (cx - (tb[2] - tb[0]) / 2, cy - (tb[3] - tb[1]) / 2 - tb[1]),
                label, fill=(255, 255, 255, 255), font=badge_font,
            )

    out = Image.alpha_composite(im.convert("RGBA"), overlay).convert("RGB")
    out.save(shipped)
    print(f"  annotated {rel_key} ({len(boxes)} box(es))")
    return True


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--list" in sys.argv:
        for k, v in SPECS.items():
            print(f"{k}: {len(v)} box(es)")
            for b in v:
                print(f"    {b}")
        return
    keys = args or list(SPECS)
    n = 0
    for k in keys:
        if k not in SPECS:
            print(f"  SKIP  {k}: no spec")
            continue
        if annotate(k, SPECS[k]):
            n += 1
    print(f"\n{n} image(s) annotated. Verify each visually before committing.")


if __name__ == "__main__":
    main()
