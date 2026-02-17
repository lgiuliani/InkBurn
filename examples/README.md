# InkBurn Examples

This directory contains example files demonstrating the InkBurn V1 extension features.

## Files

### `example.svg`
Demo SVG showcasing multi-job layers:

- **Layer 1 - Cut Example**: Single cut job with rectangle and circle
- **Layer 2 - Cut and Fill**: Two jobs on one layer — cut contour + fill hatch (45°, 0.5mm spacing)
- **Layer 3 - With Inactive Job**: Active cut job (2 passes, 0.1mm offset) + inactive fill job (won't export)
- **Layer 4 - Hidden**: Hidden layer (skipped during export)

### `expected_output.nc`
Reference G-code output generated from `example.svg`, demonstrating:

- Spec-compliant header (document name, ISO timestamp)
- Layer/job/shape comments
- Multi-pass execution
- Hatch fill lines with alternating direction
- Hidden layer exclusion
- Power/speed per job
- M3/M4 laser mode selection

## Usage

1. Open `example.svg` in Inkscape
2. Go to `Extensions > Ink/Burn > Layer & Job Configuration`
3. View the configured jobs for each layer
4. Export via `Extensions > Ink/Burn > Export G-code`
5. Compare output with `expected_output.nc`

## Testing Migration

If you have SVG files from the old InkBurn version with `data-inkburn-*` attributes:

```bash
python migrate_legacy.py old_file.svg new_file.svg
```

This converts:
- `data-active` → job `active` field
- `data-inkburn-action` → job `type` (contour→cut, fill→fill, raster→raster)
- `data-inkburn-params` → job parameters + type-specific `params`
