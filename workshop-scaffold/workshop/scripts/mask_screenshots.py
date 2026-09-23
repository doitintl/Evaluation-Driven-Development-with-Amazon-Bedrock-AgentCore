#!/usr/bin/env python3
"""Mask sensitive data in workshop screenshots before they ship.

The mission requires that every committed screenshot has account IDs, full role
names, full ARNs, account aliases, and emails masked or partially masked.

Two masking strategies are combined because OCR cannot read the AWS console's
dark top navigation strip (light-on-dark text), which is exactly where the most
sensitive identity data lives (account alias + 12-digit account ID + signed-in
email):

  1. IDENTITY BAND  — the AWS console always renders the account chip + email in
     the top-right of a dark nav strip. We detect the dark strip's bottom edge by
     scanning down the right portion of the image until the pixels stop being the
     console's near-black nav colour, then paint an opaque box over the top-right
     identity band. Resolution-agnostic (works for 1361/1625/2722-wide captures).

  2. BODY SWEEP     — OCR the whole image (dark-on-light body text reads fine) and
     paint over any token that looks like a 12-digit AWS account id, an ARN
     fragment, or an email address (e.g. account ids / ARNs shown in trace or
     evaluation detail panels).

Every masked image MUST still be verified visually afterwards — OCR is best-effort
and this script is deliberately conservative (over-masks rather than under-masks).

Usage:
  python3 mask_screenshots.py <image> [<image> ...]      # mask in place
  python3 mask_screenshots.py --dry-run <image> ...       # report only
"""
import sys, subprocess, csv, io, re, statistics
from PIL import Image, ImageDraw

MASK = (18, 20, 24)  # near-black; blends with the console nav so masks look intentional

ACCOUNT_RE = re.compile(r"\b\d{12}\b")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", re.I)
ARN_RE = re.compile(r"arn:aws", re.I)
# The capture account's real 12-digit AWS account id. We mask THIS specifically —
# not any 12-digit run — because the console also shows OTEL/X-Ray *trace ids*
# (random hex like 6a63028d7922…, which OCR truncates to 12 digits). Trace/session
# ids are not PII per the mission (account id / role name / ARN); masking one of a
# column of sibling trace ids also looks broken. Add ids here if new accounts appear.
KNOWN_ACCOUNT_IDS = ("654654616949",)
# known sensitive substrings specific to the capture account
SENSITIVE_SUBSTR = ("richardkang", "sandbox-ml", "doit.com", "@doit")


def nav_bottom(im):
    """Return y just past the AWS console's dark identity strip (0 if none)."""
    W, H = im.size
    px = im.load()
    xs = list(range(int(W * 0.60), int(W * 0.98), max(1, W // 200)))
    dark_rows = 0
    for y in range(0, min(H, 160)):
        med = statistics.median(sum(px[x, y][:3]) / 3 for x in xs)
        if med < 90:
            dark_rows += 1
        elif med > 140:
            # left the dark strip; only treat as a nav if we actually saw dark rows
            return y if dark_rows >= 3 else 0
    return 0


def ocr_rows(path):
    """OCR the ORIGINAL image file at native resolution. tesseract TSV has 12
    tab-separated columns; the final `text` column can itself contain stray
    tabs/newlines, so we parse positionally (split with maxsplit=11) instead of
    using csv.DictReader, which mis-aligns on those rows and yields garbage boxes.
    NB: we run tesseract on the on-disk file directly — re-encoding the PNG via
    PIL and re-saving confuses tesseract's DPI heuristic and returns 0 tokens."""
    p = subprocess.run(["tesseract", path, "stdout", "tsv"],
                       stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    out = p.stdout.decode("utf-8", "replace")
    rows = []
    for line in out.splitlines():
        parts = line.split("\t", 11)
        if len(parts) != 12 or parts[0] == "level":
            continue
        t = parts[11].strip()
        if not t:
            continue
        try:
            x, y, w, h = int(parts[6]), int(parts[7]), int(parts[8]), int(parts[9])
        except Exception:
            continue
        rows.append((t, x, y, w, h))
    return rows


def is_sensitive(tok):
    if EMAIL_RE.search(tok) or ARN_RE.search(tok):
        return True
    low = tok.lower()
    if any(s in low for s in SENSITIVE_SUBSTR):
        return True
    # the specific capture account id, however OCR mangles separators/parens
    digits = re.sub(r"\D", "", tok)
    if any(acct in digits for acct in KNOWN_ACCOUNT_IDS):
        return True
    return False


def mask_image(path, dry_run=False):
    im = Image.open(path).convert("RGB")
    W, H = im.size
    draw = ImageDraw.Draw(im)
    actions = []

    nb = nav_bottom(im)
    if nb:
        # identity band: top-right chip + email row (email can sit a little below the chip)
        x0 = int(W * 0.62)
        y1 = nb + int(H * 0.02)  # a touch below the strip to catch the email line
        actions.append(("identity-band", x0, 0, W, y1))
        if not dry_run:
            draw.rectangle([x0, 0, W, y1], fill=MASK)

    for tok, x, y, w, h in ocr_rows(path):
        # skip the identity band region we already covered
        if nb and y < nb + int(H * 0.02) and x > int(W * 0.62):
            continue
        if not is_sensitive(tok):
            continue
        pad = 3
        x0, y0, x1, y1 = x - pad, y - pad, x + w + pad, y + h + pad
        # Account IDs and ARNs frequently OCR with an undersized/mis-split box (e.g.
        # a 12px-wide box for a 12-digit id, or an ARN split across tokens). Extend
        # the mask to the right to guarantee the full id/ARN tail is covered, using
        # this token's own character pitch as the yardstick. Clamp to image width.
        low = tok.lower()
        digits = re.sub(r"\D", "", tok)
        pitch = max(6, w / max(1, len(tok)))  # px per character in this token
        if len(digits) >= 12:
            # numeric id (account id, session/trace id). OCR often undersizes or
            # truncates the box (e.g. '626302847922...' or a 12px box for
            # '1:654654616949'); cover a generous run so no digit peeks out.
            need = x + int(pitch * (len(tok) + 4)) + pad
            x1 = min(W, max(x1, need))
        if "arn:" in low or "agentcore:" in low:
            x1 = W  # an ARN runs to the right edge of its panel line; cover it all
        actions.append((f"body:{tok!r}", x0, y0, x1, y1))
        if not dry_run:
            draw.rectangle([x0, y0, x1, y1], fill=MASK)

    if not dry_run and actions:
        im.save(path)
    return actions


def main():
    args = sys.argv[1:]
    dry = "--dry-run" in args
    imgs = [a for a in args if a != "--dry-run"]
    for p in imgs:
        acts = mask_image(p, dry_run=dry)
        tag = "DRY" if dry else "MASKED"
        print(f"[{tag}] {p}  ({len(acts)} region(s))")
        for a in acts:
            print(f"     {a[0]:40} box={a[1:]}")


if __name__ == "__main__":
    main()
