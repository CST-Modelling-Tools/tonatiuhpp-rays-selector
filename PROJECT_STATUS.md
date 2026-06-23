# PROJECT_STATUS.md

## Last updated

2026-06-23

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
* `tools/aggregate_daily_hemisphere_energy.py` aggregates hourly hemisphere flux CSV files into daily sky-dome energy PNG and CSV outputs.
* `tools/analyze_daily_energy_concentration.py` computes energy-ranked 90% daily concentration regions, solid-angle summaries, and per-radius irregular-region overlays.
* `tools/analyze_hourly_flux_concentration.py` analyzes hourly hemisphere flux CSV files under `Point_<n>` folders and writes time-evolution CSV and PNG summaries of power-ranked 90% concentration solid angle plus maximum-flux bubble markers.
* `tools/plot_hourly_flux_concentration_maps.py` writes per-hour, per-radius polar sky-dome PNG maps showing the power-ranked Top90 region, maximum-flux bin, and optional day-level Sun position/DNI overlays from hourly hemisphere flux CSV files.
* `tools/compare_hourly_flux_concentration.py` compares hourly flux-concentration CSV outputs across technology cases with separate Top90 hemisphere-percentage and maximum-flux line plots per radius.
* `tools/compare_hourly_max_flux_bubbles.py` compares hourly maximum-flux curves across technology cases with Top90 hemisphere-percentage encoded as fixed-scale bubble radius.
* `tools/plot_max_flux_vs_radius.py` plots maximum escaped flux versus hemisphere radius for each technology case, with separate curves for solar hours.

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
* Hemisphere flux mapper now writes outputs next to the input escaped-ray file by default while preserving `--output-dir` overrides.
* Daily hemisphere energy aggregation utility added and synthetically validated with matching hourly grids.
* Daily hemisphere energy aggregation now accepts prefixed hourly flux CSV filenames.
* Daily energy concentration analysis utility added and synthetically validated with a dominant-lobe dataset.
* Daily energy concentration analysis now reports energy-ranked 90% sky regions using physical solid angle instead of symmetric circular containment regions, with single-lobe and disconnected two-lobe synthetic validation completed.
* Hourly flux concentration analysis utility added and synthetically validated with Point_10/Point_21 time mapping and power-ranked 90% selection across two radii.
* Hourly flux concentration map plotting utility added and synthetically validated with Point_10/Point_21 time mapping, two radii, power-ranked Top90 region selection, flux-ranked maximum-bin annotation, optional Sun position/DNI overlays, and missing-Sun-row handling.
* Hourly flux concentration comparison utility added and synthetically validated with two technology cases, requested and intersected radius selection, Top90 hemisphere-percentage plots, global y-axis scaling, combined CSV output, and missing-radius error reporting.
* Hourly maximum-flux bubble comparison utility added with fixed 0-4% Top90 hemisphere-percentage bubble-radius scaling.
* Hourly maximum-flux radius-dependence plotting utility added for per-technology distance analysis across solar hours.

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
* Validate hourly flux concentration summaries and maps on representative real Spring Equinox escaped-ray datasets.
* Validate hourly flux concentration technology comparisons on representative real Spring Equinox case outputs.
* Validate hourly maximum-flux bubble comparisons on representative real Spring Equinox technology outputs.
* Validate maximum-flux radius-dependence plots on representative real Spring Equinox technology outputs.

## Recommended Next Milestones

1. Validate on representative Tonatiuh++ projects.
2. Add unit tests for ray reconstruction.
3. Add metadata versioning for the compact binary output format.
4. Validate performance on multi-million-ray datasets.
5. Add additional selection criteria.
