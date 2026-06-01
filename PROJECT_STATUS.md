# PROJECT_STATUS.md

## Last updated

2026-06-01

## Purpose

`tonatiuhpp-rays-selector` is a standalone C++ post-processing utility for Tonatiuh++ photon output files.

The project is intended to support large-scale analysis of ray-tracing results without requiring modifications to Tonatiuh++ itself.

The tool operates on exported photon files and reconstructs complete rays using Tonatiuh++ photon-link information.

The long-term objective is to support multiple ray-selection criteria and specialized output formats for optical analysis.

## Current Priorities

Current work is validation-oriented:

* validate escaped-ray detection on representative Tonatiuh++ projects;
* validate power accounting;
* validate performance on large datasets;
* evaluate additional future selection criteria.

A ray is currently considered selected when:

* the ray has at least two photon records;
* the final photon has `surface_id == 0`;
* the previous photon has `surface_id > 0`.

For each selected ray, the output should contain:

```text
x
y
z
dx
dy
dz
```

where:

* `(x,y,z)` is the last non-air intersection point;
* `(dx,dy,dz)` is the normalized outgoing direction of the escaping ray.

## Current Architecture

### Input

* Tonatiuh++ photon `.dat` files.
* Tonatiuh++ `<output>_parameters.txt` metadata files.
* Support for split photon files.

### Core Components

* `TonatiuhPhotonReader`
* `ParametersFileReader`
* `RaySelector`

### Processing Strategy

* Streaming processing.
* No full photon-file loading.
* No full ray-database construction.
* Suitable for millions of rays.

### Escaped-Ray Output

The primary output mode writes `<output_prefix>.dat` with one compact record per selected escaping reflected ray.

Each record contains six binary `double` values:

```text
x
y
z
dx
dy
dz
```

where `(x,y,z)` is the last non-air intersection point and `(dx,dy,dz)` is the normalized outgoing direction.

The companion `<output_prefix>_parameters.txt` file records the field list plus `SelectedRays`, `PowerPerRay`, and `SelectedPower`.

### Analysis Tools

* `tools/visualize_escaped_rays.py` visualizes compact escaped-ray records for inspection and debugging.
* `tools/map_escaped_flux_hemisphere.py` maps compact escaped-ray records onto sky-dome hemispheres and writes report-oriented polar flux PNG and CSV outputs for one or more radii.

## Current Output Format

Binary output:

```text
<output_prefix>.dat
```

Each record contains:

```text
double x
double y
double z
double dx
double dy
double dz
```

Records are written as compact binary `double` values using the repository's existing big-endian double writer.

Metadata output:

```text
<output_prefix>_parameters.txt
```

Contains:

* parameter definitions
* selected ray count
* power per ray
* selected power

## Completed Milestones

* Repository created.
* Initial photon reader migrated from legacy project.
* Tonatiuh++ parameter-file reader migrated.
* Support for split photon files preserved.
* Initial ray reconstruction logic available.
* Escaped-reflected-ray selector implemented.
* Compact escaped-ray binary output format implemented.
* Minimal synthetic functional validation completed for compact escaped-ray output.
* Escaped-ray visualization utility added.
* Escaped-ray hemisphere flux mapping utility added.
* Synthetic hemisphere flux validation completed with PNG and CSV output.
* Hemisphere flux PNG maps refined with elevation labels, 30-degree azimuth grid labels, cardinal labels, contour overlays, yellow disk sun marker, DNI annotation, fixed-scale support, hotspot annotation, and report-style two-line titles.

## Known Technical Debt

* Current code originates from a specialized heliostat-analysis tool and may still contain project-specific assumptions.
* Reader assumptions regarding exported photon fields should be validated against multiple Tonatiuh++ export configurations.
* Compact escaped-ray output is implemented, but the binary format has no explicit version marker in metadata.

## Pending Validation

* Validate escaped-ray detection on real Tonatiuh++ exports.
* Verify ray counts against manually inspected datasets.
* Verify power accounting.
* Validate performance on multi-million-ray datasets.
* Validate hemisphere flux maps on representative real escaped-ray datasets.

## Recommended Next Milestones

1. Validate on representative Tonatiuh++ projects.
2. Add unit tests for ray reconstruction.
3. Add metadata versioning for the compact binary output format.
4. Validate performance on multi-million-ray datasets.
5. Add additional selection criteria.
