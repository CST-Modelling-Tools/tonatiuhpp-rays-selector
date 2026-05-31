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
