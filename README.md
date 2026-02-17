# Ink/Burn

**Ink/Burn** is a powerful Inkscape extension for laser cutting and engraving. It converts SVG designs into GRBL 1.1 compatible G-code files (.nc) for use with laser controllers and software like LaserGRBL.

## ✨ Features

### Multi-Job Per Layer
- **Unlimited jobs per layer** — Each SVG layer can have multiple laser operations
- **Three job types**: Cut (contour), Fill (vector hatching), and Raster (image engraving)
- **Job ordering** — Add, remove, and reorder jobs via the UI
- **Active/Inactive toggle** — Enable or disable jobs without deletion

### Job Types

**Cut (Contour)**
- Traces path outlines with configurable offset
- Multi-pass support
- M3 (constant power) or M4 (dynamic power) laser modes

**Fill (Hatching)**
- Vector scanline hatching for filled areas
- Configurable angle (0-360°), spacing, and alternating direction
- Processes closed paths only

**Raster (Image Engraving)**
- Converts embedded SVG images to G-code
- Grayscale → laser power interpolation (white=min, black=max)
- Configurable DPI and scan direction
- Requires Pillow (PIL): `pip install Pillow`

### G-code Output
- **GRBL 1.1 compliant** with spec-compliant headers and footers
- **Layer/job/shape comments** for easy debugging
- **Power/speed clamping** to prevent exceeding machine limits
- **Duplicate coordinate suppression** for smaller files
- **Path optimization** with nearest-neighbor algorithm (~40% travel reduction)

### Machine Settings
- Global power/speed limits with automatic clamping
- Configurable travel speed, resolution, and kerf width
- INI-based persistence (portable across installations)
- Debug logging levels (off / minimal / verbose)

## ⚠️ Development Disclaimer

**This software is currently in active development and should be used with caution.** 

- **Safety First**: Always verify and test generated G-code files before using them on your laser
- **Test Runs**: Perform test runs on scrap material at low power settings first
- **Supervision**: Never leave your laser engraver unattended
- **No Warranty**: This software is provided "as is" without any warranty of safety or accuracy

**Use at your own risk and always prioritize safety when working with laser equipment.**

## 📦 Installation

1. **Clone or download** this repository
2. **Copy** the InkBurn folder to your Inkscape extensions directory:
   - **Windows**: `%APPDATA%\Roaming\inkscape\extensions\`
   - **Linux**: `~/.config/inkscape/extensions/`
   - **macOS**: `~/Library/Application Support/org.inkscape.Inkscape/config/inkscape/extensions/`
3. **Install Pillow** (optional, for raster jobs):
   ```bash
   pip install Pillow
   ```
4. **Restart** Inkscape

## 🚀 Usage

### 1. Configure Machine Settings
`Extensions > Ink/Burn > Machine Settings`

Set your laser's maximum power, speed, and other global parameters. These settings apply to all documents and provide safety limits.

### 2. Configure Layer Jobs
`Extensions > Ink/Burn > Layer & Job Configuration`

- **Select a layer** from the left panel
- **Add jobs** using the "+" button — choose cut, fill, or raster
- **Configure each job**: speed, power, passes, laser mode, type-specific params
- **Reorder jobs** using ↑↓ buttons (jobs execute in order)
- **Toggle active/inactive** — inactive jobs won't export
- **Save** when done

### 3. Export G-code
`Extensions > Ink/Burn > Export G-code`

Processes all visible layers and their active jobs, generating a `.nc` file alongside your SVG.

### 4. Optional: SVG Optimization
`Extensions > Ink/Burn > Optimize SVG Elements`

Reorders shapes within each layer using nearest-neighbor to minimize travel distance (non-destructive).

## 📖 Example Workflow

1. Create an SVG with multiple layers:
   - **Layer 1**: Rectangle (for fill hatching and cut outline)
   - **Layer 2**: Image (for raster engraving)

2. Open **Layer & Job Configuration**:
   - Layer 1: Add **Fill** job (1200mm/min, 500 power, 45° angle, 0.5mm spacing)
              Add **Cut** job (800mm/min, 600 power, 1 pass)
   - Layer 2: Add **Raster** job (800mm/min, 0-600 power, 300 DPI)

3. **Export G-code** → `your_file.nc`

4. Load in LaserGRBL or your controller software

See `examples/example.svg` for a complete demo with expected output.


## 🧪 Testing

Run the test suite:
```bash
cd InkBurn
pytest tests/ -v
```

## 📋 Data Format

Jobs are stored as JSON in `data-job-X` attributes on SVG layer `<g>` elements:

```xml
<g inkscape:groupmode="layer" 
   inkscape:label="My Layer"
   data-job-0='{"id": "uuid", "type": "cut", "active": true, "speed": 800, ...}'
   data-job-1='{"id": "uuid", "type": "fill", "active": true, ...}'>
  <!-- shapes -->
</g>
```

This format is human-readable and version-control friendly.

## 🛠️ Requirements

- **Inkscape**: 1.4 or later
- **Python**: 3.8 or later
- **Pillow** (optional): For raster jobs only

## 🤝 Contributing

Contributions are welcome! Please open issues or pull requests on the [GitHub repository](https://github.com/lgiuliani/inkburn).

## 📄 License

Ink/Burn is licensed under the **GPL V3 License**. See [LICENSE](LICENSE) for details.

## 🙏 Acknowledgments

Ink/Burn is inspired by **Ink/Stitch**, the popular Inkscape embroidery extension.

## 📧 Contact

For questions or support: [l_giuliani@hotmail.com](mailto:l_giuliani@hotmail.com)

---

**Version**: 1.5  
**Last Updated**: 2026-02-17
