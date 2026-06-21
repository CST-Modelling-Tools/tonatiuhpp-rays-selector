"""Compare hourly flux concentration summaries across technology cases."""

import argparse
import csv
import math
import re
from pathlib import Path

from analyze_hourly_flux_concentration import SUMMARY_COLUMNS, radius_label, time_label


REQUIRED_COLUMNS = (
    "Radius_m",
    "Top90SolidAngle_sr",
    "Top90HemispherePercent",
    "MaxFlux_W_m2",
)

POINT_RE = re.compile(r"Point_(?P<number>\d+)")


def require_matplotlib():
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise RuntimeError("matplotlib is required to write comparison plots.") from exc

    return plt


def parse_case_argument(value):
    if "=" not in value:
        raise ValueError(f"--case must have the form Technology label=path/to/file.csv: {value}")
    label, path_text = value.split("=", 1)
    label = label.strip()
    path_text = path_text.strip()
    if not label:
        raise ValueError(f"--case has an empty technology label: {value}")
    if not path_text:
        raise ValueError(f"--case has an empty CSV path: {value}")
    return label, Path(path_text)


def parse_float(value, path, row_number, column):
    try:
        parsed = float(value)
    except ValueError as exc:
        raise ValueError(f"Invalid numeric value in {path}, row {row_number}, column {column}") from exc
    if not math.isfinite(parsed):
        raise ValueError(f"CSV file contains non-finite value in column {column}: {path}")
    return parsed


def parse_hour_from_time_label(value):
    parts = value.strip().split(":")
    if not 1 <= len(parts) <= 2:
        raise ValueError
    hour = int(parts[0])
    minute = int(parts[1]) if len(parts) == 2 else 0
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError
    return hour + minute / 60.0


def point_hour(value):
    match = POINT_RE.search(value)
    if match is not None:
        return int(match.group("number")) - 3
    return int(value) - 3


def row_time(row, path, row_number):
    if row.get("hour", "").strip():
        hour = parse_float(row["hour"], path, row_number, "hour")
        label = row.get("time_label", "").strip() or time_label(int(hour))
        return hour, label

    if row.get("time_label", "").strip():
        label = row["time_label"].strip()
        try:
            return parse_hour_from_time_label(label), label
        except ValueError as exc:
            raise ValueError(f"Cannot infer hour from time_label in {path}, row {row_number}: {label}") from exc

    for column in ("Point_ID", "point_name", "Point"):
        if row.get(column, "").strip():
            hour = point_hour(row[column].strip())
            return float(hour), time_label(hour)

    raise ValueError(f"CSV file needs hour, time_label, Point_ID, point_name, or Point column: {path}")


def validate_columns(fieldnames, path):
    missing = [column for column in REQUIRED_COLUMNS if column not in fieldnames]
    if missing:
        raise ValueError(f"CSV file is missing required column(s) {missing}: {path}")
    if not any(column in fieldnames for column in ("hour", "time_label", "Point_ID", "point_name", "Point")):
        raise ValueError(f"CSV file is missing a usable time column: {path}")


def read_case(label, path):
    if not path.is_file():
        raise ValueError(f"Case CSV does not exist or is not a file: {path}")

    with path.open(newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames is None:
            raise ValueError(f"CSV file has no header: {path}")
        validate_columns(reader.fieldnames, path)

        rows = []
        seen = set()
        for row_number, row in enumerate(reader, start=2):
            hour, label_text = row_time(row, path, row_number)
            radius = parse_float(row["Radius_m"], path, row_number, "Radius_m")
            top90 = parse_float(row["Top90SolidAngle_sr"], path, row_number, "Top90SolidAngle_sr")
            percent = parse_float(row["Top90HemispherePercent"], path, row_number, "Top90HemispherePercent")
            max_flux = parse_float(row["MaxFlux_W_m2"], path, row_number, "MaxFlux_W_m2")

            if radius <= 0.0:
                raise ValueError(f"CSV file contains non-positive radius in {path}, row {row_number}")
            if top90 < 0.0 or percent < 0.0 or max_flux < 0.0:
                raise ValueError(f"CSV file contains negative concentration or flux values in {path}, row {row_number}")

            key = (radius, hour)
            if key in seen:
                raise ValueError(f"Duplicate row for radius {radius:g} m and hour {hour:g} in case {label}: {path}")
            seen.add(key)

            rows.append({
                "Technology": label,
                "time_label": label_text,
                "hour": hour,
                "Radius_m": radius,
                "TotalPower_W": row.get("TotalPower_W", ""),
                "Top90SolidAngle_sr": top90,
                "Top90HemispherePercent": percent,
                "Top90BinCount": row.get("Top90BinCount", ""),
                "TotalBinCount": row.get("TotalBinCount", ""),
                "MaxFlux_W_m2": max_flux,
                "Az_max_flux_deg": row.get("Az_max_flux_deg", ""),
                "El_max_flux_deg": row.get("El_max_flux_deg", ""),
            })

    if not rows:
        raise ValueError(f"CSV file contains no data rows: {path}")
    return {"label": label, "path": path, "rows": rows}


def select_radii(cases, requested_radii):
    available_by_case = {
        case["label"]: {row["Radius_m"] for row in case["rows"]}
        for case in cases
    }

    if requested_radii is None:
        common = set.intersection(*(set(radii) for radii in available_by_case.values()))
        if not common:
            raise ValueError("No common radii are available in all input cases.")
        return sorted(common)

    selected = [float(radius) for radius in requested_radii]
    for radius in selected:
        if radius <= 0.0:
            raise ValueError("--radii values must be positive")
        missing = [
            label
            for label, available in available_by_case.items()
            if radius not in available
        ]
        if missing:
            raise ValueError(
                f"Requested radius {radius:g} m is missing from case(s): {', '.join(missing)}"
            )
    return selected


def rows_for_radius(case, radius):
    return sorted(
        (row for row in case["rows"] if row["Radius_m"] == radius),
        key=lambda row: row["hour"],
    )


def output_columns():
    return ("Technology",) + SUMMARY_COLUMNS


def format_value(row, column):
    if column == "Technology":
        return row[column]
    if column == "time_label":
        return row[column]
    if column == "hour":
        return f"{row[column]:.10g}"
    if column == "Radius_m":
        return f"{row[column]:.10g}"
    if column in ("Top90SolidAngle_sr", "MaxFlux_W_m2"):
        return f"{row[column]:.17g}"
    if column == "Top90HemispherePercent":
        return f"{row[column]:.10g}"
    return row.get(column, "")


def write_comparison_csv(path, cases):
    rows = []
    for case in cases:
        rows.extend(case["rows"])
    rows.sort(key=lambda row: (row["Technology"], row["Radius_m"], row["hour"]))

    columns = output_columns()
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(columns)
        for row in rows:
            writer.writerow([format_value(row, column) for column in columns])


def global_max(cases, radii, column):
    values = [
        row[column]
        for case in cases
        for row in case["rows"]
        if row["Radius_m"] in radii
    ]
    return max(values) if values else 0.0


def time_ticks(cases, radii):
    by_hour = {}
    for case in cases:
        for row in case["rows"]:
            if row["Radius_m"] in radii:
                by_hour.setdefault(row["hour"], row["time_label"])
    return sorted(by_hour), [by_hour[hour] for hour in sorted(by_hour)]


def write_line_plot(path, cases, radius, column, ylabel, title, ymax, ticks, tick_labels, dpi):
    plt = require_matplotlib()
    fig, ax = plt.subplots(figsize=(10, 6), constrained_layout=True)

    for case in cases:
        rows = rows_for_radius(case, radius)
        x_values = [row["hour"] for row in rows]
        y_values = [row[column] for row in rows]
        ax.plot(x_values, y_values, marker="o", linewidth=1.8, markersize=4.5, label=case["label"])

    ax.set_xlabel("Time of day")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.set_ylim(0.0, ymax if ymax > 0.0 else 1.0)
    ax.set_xticks(ticks)
    ax.set_xticklabels(tick_labels)
    ax.grid(True, alpha=0.35)
    ax.legend(loc="best")

    fig.savefig(path, dpi=dpi)
    plt.close(fig)


def write_plots(output_dir, cases, radii, top90_ymax, flux_ymax, title_prefix, dpi):
    ticks, tick_labels = time_ticks(cases, radii)
    written = []
    for radius in radii:
        label = radius_label(radius)
        top90_path = output_dir / f"comparison_top90_solid_angle_R{label}m.png"
        flux_path = output_dir / f"comparison_max_flux_R{label}m.png"

        write_line_plot(
            top90_path,
            cases,
            radius,
            "Top90SolidAngle_sr",
            "Top90 solid angle [sr]",
            f"{title_prefix} hourly Top90 solid angle, R = {radius:g} m",
            top90_ymax,
            ticks,
            tick_labels,
            dpi,
        )
        write_line_plot(
            flux_path,
            cases,
            radius,
            "MaxFlux_W_m2",
            "Maximum flux [W/m$^2$]",
            f"{title_prefix} hourly maximum escaped flux, R = {radius:g} m",
            flux_ymax,
            ticks,
            tick_labels,
            dpi,
        )
        written.extend((top90_path, flux_path))
    return written


def parse_args():
    parser = argparse.ArgumentParser(
        description="Compare hourly flux concentration CSVs across technology cases."
    )
    parser.add_argument(
        "--case",
        action="append",
        required=True,
        help="Technology label=path/to/hourly_flux_concentration.csv. May be repeated.",
    )
    parser.add_argument("--radii", nargs="+", type=float, default=None, help="Radii in meters to compare.")
    parser.add_argument("--output-dir", default=".", help="Folder for comparison CSV and PNG outputs.")
    parser.add_argument("--top90-ymax", type=float, default=None, help="Override Top90 plot y-axis maximum.")
    parser.add_argument("--flux-ymax", type=float, default=None, help="Override maximum-flux plot y-axis maximum.")
    parser.add_argument("--title-prefix", default="Spring Equinox")
    parser.add_argument("--dpi", type=int, default=180)
    return parser.parse_args()


def main():
    args = parse_args()
    if len(args.case) < 2:
        raise ValueError("At least two --case arguments are required for comparison.")
    if args.dpi <= 0:
        raise ValueError("--dpi must be positive")
    if args.top90_ymax is not None and args.top90_ymax <= 0.0:
        raise ValueError("--top90-ymax must be positive")
    if args.flux_ymax is not None and args.flux_ymax <= 0.0:
        raise ValueError("--flux-ymax must be positive")

    parsed_cases = [parse_case_argument(value) for value in args.case]
    labels = [label for label, _ in parsed_cases]
    duplicates = sorted({label for label in labels if labels.count(label) > 1})
    if duplicates:
        raise ValueError(f"Duplicate technology label(s): {', '.join(duplicates)}")

    cases = [read_case(label, path) for label, path in parsed_cases]
    radii = select_radii(cases, args.radii)

    top90_ymax = args.top90_ymax if args.top90_ymax is not None else global_max(cases, radii, "Top90SolidAngle_sr")
    flux_ymax = args.flux_ymax if args.flux_ymax is not None else global_max(cases, radii, "MaxFlux_W_m2")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    comparison_csv = output_dir / "hourly_flux_concentration_comparison.csv"
    write_comparison_csv(comparison_csv, cases)
    written_plots = write_plots(output_dir, cases, radii, top90_ymax, flux_ymax, args.title_prefix, args.dpi)

    print(f"Compared {len(cases)} technology cases at radii: {', '.join(f'{radius:g}' for radius in radii)} m")
    print(f"Top90 y-axis maximum: {top90_ymax:.10g} sr")
    print(f"Maximum-flux y-axis maximum: {flux_ymax:.10g} W/m^2")
    print(f"Wrote {comparison_csv}")
    for path in written_plots:
        print(f"Wrote {path}")


if __name__ == "__main__":
    main()
