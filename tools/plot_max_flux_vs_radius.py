"""Plot maximum or average flux versus hemisphere radius for each technology case."""

import argparse
import csv
import re
from pathlib import Path

from compare_hourly_flux_concentration import (
    format_value,
    output_columns,
    parse_case_argument,
    read_case,
    select_radii,
)


SUMMARY_CSV_NAME = "hourly_flux_concentration.csv"
FLUX_METRICS = {
    "maximum": {
        "column": "MaxFlux_W_m2",
        "label": "Maximum flux",
        "description": "maximum escaped flux",
        "stem": "max_flux",
    },
    "average": {
        "column": "AverageFlux_W_m2",
        "label": "Top90 average flux",
        "description": "Top90 average escaped flux",
        "stem": "top90_average_flux",
    },
}


def require_matplotlib():
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise RuntimeError("matplotlib is required to write maximum-flux radius plots.") from exc

    return plt


def resolve_summary_csv(path):
    if path.is_dir():
        return path / SUMMARY_CSV_NAME
    return path


def read_cases(case_arguments):
    parsed_cases = [parse_case_argument(value) for value in case_arguments]
    labels = [label for label, _ in parsed_cases]
    duplicates = sorted({label for label in labels if labels.count(label) > 1})
    if duplicates:
        raise ValueError(f"Duplicate technology label(s): {', '.join(duplicates)}")

    return [
        read_case(label, resolve_summary_csv(path))
        for label, path in parsed_cases
    ]


def safe_filename_stem(value):
    stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return stem.strip("._") or "technology"


def row_matches(row, radii, hours):
    return row["Radius_m"] in radii and row["hour"] in hours


def available_hours(cases, radii):
    return sorted({
        row["hour"]
        for case in cases
        for row in case["rows"]
        if row["Radius_m"] in radii
    })


def select_hours(cases, radii, requested_hours):
    if requested_hours is None:
        hours = available_hours(cases, radii)
    else:
        hours = [float(hour) for hour in requested_hours]
        for hour in hours:
            if hour < 0.0 or hour > 23.0:
                raise ValueError("--hours values must be between 0 and 23")
        available = set(available_hours(cases, radii))
        missing = [hour for hour in hours if hour not in available]
        if missing:
            raise ValueError(f"Requested hour(s) not found in selected data: {', '.join(f'{hour:g}' for hour in missing)}")

    if not hours:
        raise ValueError("No hourly rows are available for the selected radii.")
    return hours


def time_labels(cases, radii, hours):
    labels = {}
    for case in cases:
        for row in case["rows"]:
            if row_matches(row, radii, hours):
                labels.setdefault(row["hour"], row["time_label"])
    return labels


def rows_for_hour(case, hour, radii):
    return sorted(
        (row for row in case["rows"] if row["hour"] == hour and row["Radius_m"] in radii),
        key=lambda row: row["Radius_m"],
    )


def selected_rows(cases, radii, hours):
    rows = [
        row
        for case in cases
        for row in case["rows"]
        if row_matches(row, radii, hours)
    ]
    rows.sort(key=lambda row: (row["Technology"], row["hour"], row["Radius_m"]))
    return rows


def write_selected_csv(path, cases, radii, hours):
    rows = selected_rows(cases, radii, hours)
    columns = output_columns()

    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(columns)
        for row in rows:
            writer.writerow([format_value(row, column) for column in columns])


def metric_value(row, metric):
    column = FLUX_METRICS[metric]["column"]
    value = row.get(column)
    if value is None:
        raise ValueError(f"Input CSV does not provide enough data to compute {column}")
    return value


def write_case_plot(path, case, radii, hours, labels_by_hour, flux_metric, flux_ymax, title_prefix, radius_scale, dpi):
    plt = require_matplotlib()
    fig, ax = plt.subplots(figsize=(11.5, 6))
    fig.subplots_adjust(right=0.78)
    colors = plt.get_cmap("tab20")

    for index, hour in enumerate(hours):
        rows = rows_for_hour(case, hour, radii)
        if not rows:
            continue
        x_values = [row["Radius_m"] for row in rows]
        y_values = [metric_value(row, flux_metric) for row in rows]
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

    ax.set_xticks(radii)
    ax.set_xticklabels([f"{radius:g}" for radius in radii], rotation=35, ha="right")
    ax.set_xlabel("Hemisphere radius [m]")
    ax.set_ylabel(f"{FLUX_METRICS[flux_metric]['label']} [W/m$^2$]")
    ax.set_title(f"{title_prefix} {FLUX_METRICS[flux_metric]['description']} versus radius - {case['label']}")
    ax.set_ylim(0.0, flux_ymax if flux_ymax > 0.0 else 1.0)
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


def filtered_global_max(cases, radii, hours, flux_metric):
    values = [
        metric_value(row, flux_metric)
        for case in cases
        for row in case["rows"]
        if row_matches(row, radii, hours)
    ]
    return max(values) if values else 0.0


def write_plots(output_dir, cases, radii, hours, flux_metric, flux_ymax, title_prefix, radius_scale, dpi):
    labels_by_hour = time_labels(cases, radii, hours)
    written = []
    for case in cases:
        path = output_dir / f"{FLUX_METRICS[flux_metric]['stem']}_vs_radius_{safe_filename_stem(case['label'])}.png"
        write_case_plot(path, case, radii, hours, labels_by_hour, flux_metric, flux_ymax, title_prefix, radius_scale, dpi)
        written.append(path)
    return written


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "For each technology case, plot hourly maximum or average escaped flux as a function "
            "of hemisphere radius."
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
    parser.add_argument("--output-dir", default=".", help="Folder for CSV and PNG outputs.")
    parser.add_argument(
        "--flux-metric",
        choices=tuple(FLUX_METRICS),
        default="maximum",
        help="Flux metric to plot. Average flux is 90%% of TotalPower_W divided by the Top90 region area Top90SolidAngle_sr*R^2.",
    )
    parser.add_argument("--flux-ymax", type=float, default=None, help="Override flux plot y-axis maximum.")
    parser.add_argument("--title-prefix", default="Spring Equinox")
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
    if args.flux_ymax is not None and args.flux_ymax <= 0.0:
        raise ValueError("--flux-ymax must be positive")

    cases = read_cases(args.case)
    radii = select_radii(cases, args.radii)
    hours = select_hours(cases, radii, args.hours)
    flux_ymax = args.flux_ymax if args.flux_ymax is not None else filtered_global_max(cases, radii, hours, args.flux_metric) * 1.05

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    csv_path = output_dir / f"{FLUX_METRICS[args.flux_metric]['stem']}_vs_radius.csv"
    write_selected_csv(csv_path, cases, radii, hours)
    written_plots = write_plots(output_dir, cases, radii, hours, args.flux_metric, flux_ymax, args.title_prefix, args.radius_scale, args.dpi)

    print(f"Analyzed {len(cases)} technology case(s).")
    print(f"Flux metric: {args.flux_metric}")
    print(f"Radii: {', '.join(f'{radius:g}' for radius in radii)} m")
    print(f"Solar hours: {', '.join(f'{hour:g}' for hour in hours)}")
    print(f"Flux y-axis maximum: {flux_ymax:.10g} W/m^2")
    print(f"Wrote {csv_path}")
    for path in written_plots:
        print(f"Wrote {path}")


if __name__ == "__main__":
    main()
