# PROJECT_STATUS.md

## Last updated

2026-06-01

## Purpose

`tonatiuhpp-rays-selector` is a standalone C++ post-processing utility for Tonatiuh++ photon output files.

The project is intended to support large-scale analysis of ray-tracing results without requiring modifications to Tonatiuh++ itself.

The tool operates on exported photon files and reconstructs complete rays using Tonatiuh++ photon-link information.

The long-term objective is to support multiple ray-selection criteria and specialized output formats for optical analysis.

## Current Priority

Validate the escaped-reflected-ray selector on representative Tonatiuh++ exports and harden the compact output workflow as needed.

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
* Escaped-reflected-ray selector implemented as the primary output mode.
* Compact escaped-ray binary output implemented as six doubles per selected ray.
* Minimal synthetic functional validation completed for compact escaped-ray output.

## Known Technical Debt

* Current code originates from a specialized heliostat-analysis tool and may still contain project-specific assumptions.
* Reader assumptions regarding exported photon fields should be validated against multiple Tonatiuh++ export configurations.
* Compact escaped-ray output is implemented, but the binary format has no explicit version marker in metadata.

## Pending Validation

* Validate escaped-ray detection on real Tonatiuh++ exports.
* Verify ray counts against manually inspected datasets.
* Verify power accounting.
* Validate performance on multi-million-ray datasets.

## Recommended Next Milestones

1. Validate on representative Tonatiuh++ projects.
2. Add unit tests for ray reconstruction.
3. Add metadata versioning for the compact binary output format.
4. Validate performance on multi-million-ray datasets.
5. Add additional selection criteria.
