# AGENTS.md

## Working principles

* Optimize for minimal token consumption.
* Keep responses concise and focused.
* Work in milestone mode, not micro-step mode.
* Batch related changes together instead of splitting work into many trivial steps.
* Avoid cosmetic refactors unless they improve correctness, maintainability, robustness, or clarity.
* Only propose follow-up work when they materially improve:

  * correctness
  * robustness
  * maintainability
  * validation quality
  * performance
  * cross-platform behavior
* Do not print full file contents unless explicitly requested.

## Project context

This repository contains `tonatiuhpp-rays-selector`, a standalone C++ command-line post-processing utility for Tonatiuh++ photon/ray-tracing output files.

The tool is intended to support analysis of very large Tonatiuh++ ray-tracing results without requiring modifications to Tonatiuh++ itself.

The repository currently focuses on identifying rays that leave the scene after reflection, but the long-term objective is to support multiple ray-selection criteria and specialized optical-analysis workflows.

The software must remain suitable for processing millions of rays with low memory consumption.

## Project status context

Before starting any non-trivial task, read `PROJECT_STATUS.md`.

Use `PROJECT_STATUS.md` to understand:

* current priorities
* implemented selection criteria
* current output formats
* completed milestones
* known technical debt
* pending validation
* next recommended milestones

Keep durable working rules in this file.

Keep time-sensitive project context in `PROJECT_STATUS.md`.

When a task materially changes the project state, update `PROJECT_STATUS.md`.

Examples include:

* implementation of a new ray-selection criterion
* changes to binary output formats
* changes to metadata formats
* completion of major milestones
* discovery or resolution of significant technical debt
* changes to project priorities
* major validation results

Do not update `PROJECT_STATUS.md` for trivial edits.

## Architecture guidelines

* Keep photon-file reading separate from ray-selection logic.
* Keep output generation separate from selection logic.
* Preserve support for split Tonatiuh++ `.dat` photon files.
* Preserve streaming processing; do not load all photons or all rays into memory.
* Prefer extending existing abstractions over creating parallel implementations.
* Avoid introducing a complex selection language until the core selection workflows are stable.
* Prefer simple C++ standard-library solutions unless additional dependencies are clearly justified.
* Do not duplicate Tonatiuh++ photon parsing logic across modules.
* Maintain compatibility with large photon datasets whenever practical.

## Current Priority

The current development priority is the escaped-reflected-ray selector.

A complete ray is selected when:

* the ray has at least two photon records;
* the final photon has `surface_id == 0`;
* the previous photon has `surface_id > 0`.

For each selected ray:

* use the previous photon position as the origin;
* compute the vector from the previous photon to the final photon;
* normalize the vector;
* skip the ray if the vector norm is zero or invalid;
* write exactly six binary `double` values:

```text
x
y
z
dx
dy
dz
```

where:

* `(x, y, z)` is the last non-air intersection point;
* `(dx, dy, dz)` is the normalized outgoing direction of the escaping ray.

## Output Format

Current escaped-ray output:

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

Metadata file:

```text
<output_prefix>_parameters.txt
```

At minimum:

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
<power_per_ray>

SelectedPower
<SelectedRays * PowerPerRay>
```

Do not write surface IDs to the compact escaped-ray output.

Do not copy the original Tonatiuh++ surface table into escaped-ray metadata files unless a future output mode requires surface identifiers.

## Codex efficiency guidelines

* Read only the files necessary for the requested task.
* Avoid repository-wide searches unless architectural impact is unclear.
* Reuse existing abstractions whenever possible.
* Prefer extending existing workflows over introducing parallel implementations.
* Avoid duplicated logic.
* Avoid creating multiple ways to perform the same task.
* Stop once the requested milestone is complete.
* Do not perform speculative refactors.

## Validation

When relevant, run:

```powershell
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build
```

For logic changes:

* perform at least one minimal functional validation using a representative Tonatiuh++ photon dataset when available;
* verify that streaming behavior is preserved;
* verify that memory usage remains proportional to a single reconstructed ray rather than the entire dataset.

## Output requirements

For each completed task:

* Provide a concise summary.
* List files created or modified.
* List validation performed.
* Provide one production-ready Conventional Commit message.

Do not print full file contents unless explicitly requested.

When the requested milestone has been completed, stop and wait for further instructions.

## Commit message requirements

Use Conventional Commits 1.0.0:

```text
<type>[optional scope]: <description>

<body>
```

Suitable types include:

* feat
* fix
* refactor
* perf
* test
* docs
* build
* ci
* chore

Use scopes when they improve clarity.

The commit message should explain:

* what changed;
* why it changed;
* important implementation decisions;
* compatibility considerations;
* validation performed.

Do not artificially wrap commit-message paragraphs.