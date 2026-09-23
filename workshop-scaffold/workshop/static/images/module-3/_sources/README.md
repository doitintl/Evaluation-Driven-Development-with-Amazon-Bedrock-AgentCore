# Module 3 comparison-visual sources

`model-swap-comparison.png` and `prompt-change-comparison.png` are illustrative
mockups of the `npm run eval` before/after comparison, shown in Module 3
(`02-model-swap`, `03-prompt-change`). They are **hand-authored HTML rendered to
PNG**, not emitted by the eval runner (which produces markdown).

The `.html` files here are the source of truth. To regenerate the PNGs after an
edit (1361×788, matching the other Module-3 console captures):

```bash
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"   # or any Chromium
for name in model-swap-comparison prompt-change-comparison; do
  "$CHROME" --headless --disable-gpu --hide-scrollbars --force-device-scale-factor=1 \
    --window-size=1361,788 --screenshot="../$name.png" "file://$PWD/$name.html"
done
```

The data shown intentionally mirrors the 6 cases in `travel-agent/eval/cases.ts`
and the narrative in the two module pages. Keep glyphs as real UTF-8
(`→`, `✓`, `−`) — the originals shipped with mojibake (`â†'`, `âœ"`, `â€"`) from a
UTF-8-as-Latin-1 charset bug, which this regeneration fixed.
