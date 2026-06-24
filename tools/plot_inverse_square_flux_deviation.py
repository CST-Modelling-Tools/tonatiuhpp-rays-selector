"""Plot maximum-flux deviation from an ideal inverse-square radius decrease."""

import argparse
import csv
from pathlib import Path

from plot_max_flux_vs_radius import (
    read_cases,
    safe_filename_stem,
    select_hours,
    time_labels,
)
from compare_hourly_flux_concentration import select_radii


def require_matplotlib():
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise RuntimeError("matplotlib is required to write inverse-square deviation plots.") from exc

    return plt


def row_lookup(case):
    return {
        (row["hour"], row["Radius_m"]): row
        for row in case["rows"]
    }


def compute_deviation_rows(cases, radii, hours, reference_radius):
    rows = []
    skipped = []

    for case in cases:
        lookup = row_lookup(case)
        for hour in hours:
            reference = lookup.get((hour, reference_radius))
            if reference is None:
                skipped.append((case["label"], hour, "missing reference radius"))
                continue

            reference_flux = reference["MaxFlux_W_m2"]
            if reference_flux <= 0.0:
                skipped.append((case["label"], hour, "zero reference flux"))
                continue

            for radius in radii:
                row = lookup.get((hour, radius))
                if row is None:
                    continue

                expected_flux = reference_flux * (reference_radius / radius) ** 2
                actual_flux = row["MaxFlux_W_m2"]
                ratio = actual_flux / expected_flux if expected_flux > 0.0 else 0.0
                rows.append({
                    "Technology": case["label"],
                    "time_label": row["time_label"],
                    "hour": hour,
                    "ReferenceRadius_m": reference_radius,
                    "Radius_m": radius,
                    "ReferenceMaxFlux_W_m2": reference_flux,
                    "ActualMaxFlux_W_m2": actual_flux,
                    "InverseSquareExpectedFlux_W_m2": expected_flux,
                    "ActualToInverseSquareRatio": ratio,
                    "InverseSquareDeviationPercent": (ratio - 1.0) * 100.0,
                })

    return rows, skipped


def output_columns():
    return (
        "Technology",
        "time_label",
        "hour",
        "ReferenceRadius_m",
        "Radius_m",
        "ReferenceMaxFlux_W_m2",
        "ActualMaxFlux_W_m2",
        "InverseSquareExpectedFlux_W_m2",
        "ActualToInverseSquareRatio",
        "InverseSquareDeviationPercent",
    )


def format_value(row, column):
    value = row[column]
    if column in ("Technology", "time_label"):
        return value
    if column in ("hour", "ReferenceRadius_m", "Radius_m"):
        return f"{value:.10g}"
    return f"{value:.17g}"


def write_deviation_csv(path, rows):
    columns = output_columns()
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(columns)
        for row in rows:
            writer.writerow([format_value(row, column) for column in columns])


def rows_for_case_hour(rows, technology, hour):
    return sorted(
        (row for row in rows if row["Technology"] == technology and row["hour"] == hour),
        key=lambda row: row["Radius_m"],
    )


def deviation_range(rows):
    values = [row["InverseSquareDeviationPercent"] for row in rows if row["Radius_m"] != row["ReferenceRadius_m"]]
    if not values:
        return -1.0, 1.0

    minimum = min(min(values), 0.0)
    maximum = max(max(values), 0.0)
    padding = max((maximum - minimum) * 0.05, 1.0)
    return minimum - padding, maximum + padding


def write_case_plot(
    path,
    case,
    rows,
    radii,
    hours,
    labels_by_hour,
    y_limits,
    radius_scale,
    deviation_scale,
    deviation_symlog_linthresh,
    title_prefix,
    dpi,
):
    plt = require_matplotlib()
    fig, ax = plt.subplots(figsize=(11.5, 6))
    fig.subplots_adjust(right=0.78)
    colors = plt.get_cmap("tab20")

    for index, hour in enumerate(hours):
        hour_rows = rows_for_case_hour(rows, case["label"], hour)
        if not hour_rows:
            continue
        x_values = [row["Radius_m"] for row in hour_rows]
        y_values = [row["InverseSquareDeviationPercent"] for row in hour_rows]
        ax.plot(
            x_values,
            y_values,
            marker="o",
            linewidth=1.7,
            markersize=4.5,
            color=colors(index % 20),
            label=labels_by_hour.get(hour, f"{hour:g}:00"),
        )

    if radius_scale == "log":
        ax.set_xscale("log")
    if deviation_scale == "symlog":
        ax.set_yscale("symlog", linthresh=deviation_symlog_linthresh)

    ax.axhline(0.0, color="#333333", linewidth=1.0, linestyle="--", alpha=0.8)
    ax.set_xticks(radii)
    ax.set_xticklabels([f"{radius:g}" for radius in radii], rotation=35, ha="right")
    ax.set_xlabel("Hemisphere radius [m]")
    ax.set_ylabel("Deviation from 1/R$^2$ decrease [%]")
    ax.set_title(f"{title_prefix} inverse-square flux deviation - {case['label']}")
    ax.set_ylim(*y_limits)
    ax.grid(True, alpha=0.35)
    ax.legend(
        title="Solar time",
        loc="upper left",
        bbox_to_anchor=(1.01, 1.0),
        borderaxespad=0.0,
        fontsize=9,
        title_fontsize=10,
    )

    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)


def write_plots(
    output_dir,
    cases,
    rows,
    radii,
    hours,
    y_limits,
    radius_scale,
    deviation_scale,
    deviation_symlog_linthresh,
    title_prefix,
    dpi,
):
    labels_by_hour = time_labels(cases, radii, hours)
    written = []
    for case in cases:
        path = output_dir / f"inverse_square_flux_deviation_{safe_filename_stem(case['label'])}.png"
        write_case_plot(
            path,
            case,
            rows,
            radii,
            hours,
            labels_by_hour,
            y_limits,
            radius_scale,
            deviation_scale,
            deviation_symlog_linthresh,
            title_prefix,
            dpi,
        )
        written.append(path)
    return written


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "For each technology case, compare the maximum escaped flux decrease with "
            "the ideal 1/R^2 decrease from a reference radius."
        )
    )
    parser.add_argument(
        "--case",
        action="append",
        required=True,
        help=(
            "Technology label=SpringEquinox folder or path/to/hourly_flux_concentration.csv. "
            "May be repeated."
        ),
    )
    parser.add_argument("--radii", nargs="+", type=float, default=None, help="Radii in meters to plot.")
    parser.add_argument("--hours", nargs="+", type=float, default=None, help="Solar hours to plot, for example 9 10 15.")
    parser.add_argument(
        "--reference-radius",
        type=float,
        default=None,
        help="Radius used as the inverse-square reference. Defaults to the smallest selected radius.",
    )
    parser.add_argument("--output-dir", default=".", help="Folder for CSV and PNG outputs.")
    parser.add_argument(
        "--deviation-ymin",
        type=float,
        default=None,
        help="Override deviation plot y-axis minimum, in percent.",
    )
    parser.add_argument(
        "--deviation-ymax",
        type=float,
        default=None,
        help="Override deviation plot y-axis maximum, in percent.",
    )
    parser.add_argument("--title-prefix", default="Spring Equinox")
    parser.add_argument(
        "--deviation-scale",
        choices=("symlog", "linear"),
        default="symlog",
        help="Deviation-axis scale. Symlog is log-like away from zero but can show negative deviations and 0%%.",
    )
    parser.add_argument(
        "--deviation-symlog-linthresh",
        type=float,
        default=10.0,
        help="Half-width of the linear region around 0%% when --deviation-scale symlog is used.",
    )
    parser.add_argument(
        "--radius-scale",
        choices=("log", "linear"),
        default="log",
        help="Radius-axis scale. The default log scale is useful for radii spanning orders of magnitude.",
    )
    parser.add_argument("--dpi", type=int, default=180)
    return parser.parse_args()


def main():
    args = parse_args()
    if args.dpi <= 0:
        raise ValueError("--dpi must be positive")
    if (args.deviation_ymin is None) != (args.deviation_ymax is None):
        raise ValueError("--deviation-ymin and --deviation-ymax must be provided together")
    if args.deviation_ymin is not None and args.deviation_ymin >= args.deviation_ymax:
        raise ValueError("--deviation-ymin must be smaller than --deviation-ymax")
    if args.deviation_symlog_linthresh <= 0.0:
        raise ValueError("--deviation-symlog-linthresh must be positive")

    cases = read_cases(args.case)
    radii = select_radii(cases, args.radii)
    hours = select_hours(cases, radii, args.hours)
    reference_radius = min(radii) if args.reference_radius is None else float(args.reference_radius)
    if reference_radius not in radii:
        raise ValueError("--reference-radius must be one of the selected radii")

    rows, skipped = compute_deviation_rows(cases, radii, hours, reference_radius)
    if not rows:
        raise ValueError("No deviation rows were produced. Check that reference-radius flux is positive.")

    y_limits = (
        (args.deviation_ymin, args.deviation_ymax)
        if args.deviation_ymin is not None
        else deviation_range(rows)
    )

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    csv_path = output_dir / "inverse_square_flux_deviation.csv"
    write_deviation_csv(csv_path, rows)
    written_plots = write_plots(
        output_dir,
        cases,
        rows,
        radii,
        hours,
        y_limits,
        args.radius_scale,
        args.deviation_scale,
        args.deviation_symlog_linthresh,
        args.title_prefix,
        args.dpi,
    )

    print(f"Analyzed {len(cases)} technology case(s).")
    print(f"Reference radius: {reference_radius:g} m")
    print(f"Radii: {', '.join(f'{radius:g}' for radius in radii)} m")
    print(f"Solar hours: {', '.join(f'{hour:g}' for hour in hours)}")
    print(f"Deviation y-axis range: {y_limits[0]:.10g} to {y_limits[1]:.10g} %")
    print(f"Deviation y-axis scale: {args.deviation_scale}")
    if skipped:
        labels = [f"{label} at {hour:g}:00 ({reason})" for label, hour, reason in skipped]
        print(f"Skipped hour(s): {', '.join(labels)}")
    print(f"Wrote {csv_path}")
    for path in written_plots:
        print(f"Wrote {path}")


if __name__ == "__main__":
    main()
