# tonatiuhpp-rays-selector

Small command-line tool for post-processing Tonatiuh++ photon/ray output files.

Current primary mode: select complete rays that are reflected by a scene surface and then leave the scene. In the current Tonatiuh++ photon format this means:

- the ray has at least two photon records,
- the final photon has `surface ID == 0`, which Tonatiuh++ uses for air,
- the photon immediately before the final air photon has `surface ID > 0`.

Each selected ray is written as one compact binary record containing the last scene-surface intersection and normalized outgoing direction:

```text
x
y
z
dx
dy
dz
```

## Supported input format

The tool currently expects photon records with exactly these fields, in this order:

```text
id
x
y
z
side
previous ID
next ID
surface ID
```

This corresponds to Tonatiuh++ photon export with coordinates, side, photon IDs, and surface ID enabled.

## Build

```bash
cmake -S . -B build
cmake --build build --config Release
```

## Run

```bash
./build/tonatiuhpp-rays-selector <input_folder> <output_prefix> [parameters_file]
```

Examples:

```bash
./build/tonatiuhpp-rays-selector ./photon_output escaped_rays
./build/tonatiuhpp-rays-selector ./photon_output escaped_rays PhotonMap_parameters.txt
```

The program writes:

```text
<output_prefix>.dat
<output_prefix>_parameters.txt
```

## Escaped-Ray Output Format

`<output_prefix>.dat` contains one record per selected escaping reflected ray. Each record contains six binary `double` values:

```text
x
y
z
dx
dy
dz
```

where:

- `(x,y,z)` is the last non-air intersection point,
- `(dx,dy,dz)` is the normalized outgoing direction.

`<output_prefix>_parameters.txt` describes the compact record layout and selected-power summary:

```text
START PARAMETERS
x
y
z
dx
dy
dz
END PARAMETERS

SelectedRays
<number>

PowerPerRay
<value>

SelectedPower
<SelectedRays * PowerPerRay>
```

## Visualization Utility

The repository includes `tools/visualize_escaped_rays.py` for inspection and debugging of escaped-ray datasets.

Example usage:

```powershell
python tools/visualize_escaped_rays.py escaped_rays.dat --length 5 --max-rays 2000
```

`--length` controls the displayed ray length. `--max-rays` limits the number of displayed rays.

## Hemisphere Flux Mapping

The repository includes `tools/map_escaped_flux_hemisphere.py` to map compact escaped-ray records onto one or more sky-dome hemispheres and write polar flux maps.

This tool requires NumPy and Matplotlib.

Example usage:

```powershell
.\.venv\Scripts\python.exe tools\map_escaped_flux_hemisphere.py `
"path\to\stray_rays.dat" `
--radius 25 50 100 200 300 400 500 1000 `
--az-bins 180 `
--zenith-bins 90 `
--sun-azimuth-deg 178.59 `
--sun-elevation-deg 27.48 `
--dni 934.09 `
--output-dir hemisphere_flux
```

The tool reads `x y z dx dy dz` records from a big-endian binary `.dat` file and reads `PowerPerRay` from the matching `<input_prefix>_parameters.txt` file. Use `--power-per-ray <value>` to override the metadata value.

By default, outputs are written next to the input escaped-ray file. Use `--output-dir <path>` to redirect all generated maps and CSV files elsewhere.

For each radius, the tool writes:

```text
<output_dir>/hemisphere_flux_R<radius>m.png
<output_dir>/hemisphere_flux_R<radius>m.csv
```

The CSV reports azimuth, elevation, zenith, ray count, power, and flux for each bin. The PNG uses architectural sky-dome convention: zenith at the center, horizon at the outer circle, 0 degrees azimuth at North, 90 degrees at East, and azimuth increasing clockwise.

The polar PNG includes elevation-labelled radial rings, 30-degree azimuth grid lines with N/E/S/W labels, contour lines over the flux color map, a two-line report-style title, and an automatic maximum-flux annotation. If `--sun-azimuth-deg` and `--sun-elevation-deg` are provided, the map shows a labelled yellow Sun disk. If `--dni` is provided, the DNI value is included in the title. Use `--vmax <value>` to apply a fixed color-scale maximum across all requested radii for visual comparison.

## Daily Hemisphere Energy Aggregation

Use `tools/aggregate_daily_hemisphere_energy.py` to aggregate hourly hemisphere flux CSV files into daily sky-dome energy maps.

Example usage:

```powershell
.\.venv\Scripts\python.exe tools\aggregate_daily_hemisphere_energy.py `
"D:\Solatom\Report\RayTracing\SpringEquinox" `
--radius 25 50 100 200 300 400 500 1000 `
--duration-hours 1
```

For each requested radius, the tool recursively finds matching `*hemisphere_flux_R<radius>m.csv` files under the input folder. Hourly CSV files may have prefixes such as `point_10_hemisphere_flux_R25m.csv`, as long as they end with `hemisphere_flux_R<radius>m.csv`. The hourly CSVs for a radius must use the same ordered azimuth, elevation, and zenith bin grid.

Energy is computed as `flux_W_m2 * duration_hours`. Output CSV values are written in `Wh/m²` and `kWh/m²`. By default, daily outputs are written to the input day folder; use `--output-dir <path>` to redirect them.

## Daily Energy Concentration Analysis

Use `tools/analyze_daily_energy_concentration.py` to quantify how tightly daily escaped energy is concentrated on the sky dome.

Example usage:

```powershell
.\.venv\Scripts\python.exe tools\analyze_daily_energy_concentration.py `
"D:\Solatom\Report\RayTracing\SpringEquinox"
```

The tool discovers `daily_hemisphere_energy_R<radius>m.csv` files, sorts radii numerically, and writes `daily_energy_concentration.csv`, `daily_energy_concentration.png`, and per-radius `daily_hemisphere_energy_R<radius>m_concentration.png` overlays in the input folder.

`Theta90_max_deg` is the angular radius around the maximum-energy bin required to contain 90% of the summed daily sky-bin energy. `Theta90_centroid_deg` uses the same containment calculation around the energy-weighted spherical centroid direction. Smaller Theta90 values indicate tighter angular concentration; comparing the two metrics helps distinguish a compact dominant lobe from a broader or multi-lobe distribution.
