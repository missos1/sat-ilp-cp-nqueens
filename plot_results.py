"""Create report-ready comparison plots from benchmark CSV data."""

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


SAT_METRICS = {
    "solve_time": "Average solve time (seconds)",
    "conflicts": "Average conflicts",
    "decisions": "Average decisions",
    "propagations": "Average propagations"
}


def _style_axis(axis: plt.Axes, ylabel: str, title: str) -> None:
    axis.set(xlabel="Board size N", ylabel=ylabel, title=title)
    values = [value for line in axis.lines for value in line.get_ydata()]
    if values and min(values) <= 0:
        axis.set_yscale("symlog", linthresh=1)
    else:
        axis.set_yscale("log")
    axis.grid(True, which="both", alpha=0.25)


def _save_line_plot(data: pd.DataFrame, y: str, ylabel: str, title: str, path: Path) -> None:
    figure, axis = plt.subplots(figsize=(11, 6))
    for label, group in data.groupby("label"):
        group = group.sort_values("size")
        axis.plot(group["size"], group[y], marker="o", label=label)
    _style_axis(axis, ylabel, title)
    axis.legend(fontsize="small")
    figure.tight_layout()
    figure.savefig(path, dpi=180)
    plt.close(figure)


def _save_solver_panels(data: pd.DataFrame, y: str, ylabel: str, title: str, path: Path) -> None:
    solvers = list(data["solver"].drop_duplicates())
    figure, axes = plt.subplots(1, len(solvers), figsize=(6 * len(solvers), 5), squeeze=False)
    for axis, solver in zip(axes[0], solvers):
        subset = data[data["solver"] == solver]
        for encoding, group in subset.groupby("encoding"):
            group = group.sort_values("size")
            axis.plot(group["size"], group[y], marker="o", label=encoding)
        _style_axis(axis, ylabel, solver)
        axis.legend(fontsize="small")
    figure.suptitle(title)
    figure.tight_layout()
    figure.savefig(path, dpi=180)
    plt.close(figure)


def _save_encoding_panels(data: pd.DataFrame, y: str, ylabel: str, title: str, path: Path) -> None:
    encodings = list(data["encoding"].drop_duplicates())
    figure, axes = plt.subplots(2, 2, figsize=(12, 9), squeeze=False)
    for axis, encoding in zip(axes.flat, encodings):
        subset = data[data["encoding"] == encoding]
        for solver, group in subset.groupby("solver"):
            group = group.sort_values("size")
            axis.plot(group["size"], group[y], marker="o", label=solver)
        _style_axis(axis, ylabel, encoding)
        axis.legend(fontsize="small")
    figure.suptitle(title)
    figure.tight_layout()
    figure.savefig(path, dpi=180)
    plt.close(figure)


def _save_solver_comparison(data: pd.DataFrame, solver: str, path: Path) -> None:
    metrics = list(SAT_METRICS.items())
    encodings = list(data["encoding"].drop_duplicates())
    colors = dict(zip(encodings, plt.cm.tab10.colors))
    figure, axes = plt.subplots(1, len(metrics), figsize=(18, 5), squeeze=False)

    for axis, (metric, ylabel) in zip(axes[0], metrics):
        for encoding in encodings:
            for col_alo, line_style in ((False, "--"), (True, "-")):
                subset = data[(data["encoding"] == encoding) & (data["col_alo"] == col_alo)].sort_values("size")
                if subset.empty:
                    continue
                axis.plot(
                    subset["size"],
                    subset[metric],
                    color=colors[encoding],
                    linestyle=line_style,
                    marker="^" if col_alo else "o",
                    label=f"{encoding} / {'ALO' if col_alo else 'no ALO'}",
                )
        _style_axis(axis, ylabel, metric.replace("_", " "))
        axis.legend(fontsize="x-small", ncol=2)

    figure.suptitle(f"{solver}: ALO versus no ALO")
    figure.tight_layout()
    figure.savefig(path, dpi=180)
    plt.close(figure)


def _write_tables(data: pd.DataFrame, output_dir: Path) -> None:
    table_dir = output_dir / "tables"
    table_dir.mkdir(parents=True, exist_ok=True)
    markdown_sections = ["# N-Queens Benchmark Tables", ""]

    sat = data[data["approach"] == "SAT"].copy()

    def flatten_metric_column(column: object) -> str:
        if isinstance(column, tuple):
            if column[0] in ("size", "encoding"):
                return column[0]
            metric, alo = column
            return f"{metric}_{'with_alo' if alo else 'without_alo'}"
        return str(column)

    for solver in sat["solver"].drop_duplicates():
        solver_data = sat[sat["solver"] == solver]
        table = solver_data.pivot_table(
            index=["size", "encoding"],
            columns="col_alo",
            values=["clauses", "solve_time", "conflicts", "decisions", "propagations"],
            aggfunc="first",
        ).reset_index()
        table.columns = [flatten_metric_column(column) for column in table.columns]
        table = table.sort_values(["size", "encoding"])
        table.to_csv(table_dir / f"{solver}_alo_comparison.csv", index=False)
        markdown_sections.append(f"## {solver}: ALO versus no ALO")
        markdown_sections.append(table.to_markdown(index=False, floatfmt=".6g"))
        markdown_sections.append("")

    clauses = sat.drop_duplicates(["size", "encoding", "col_alo"])
    clause_table = clauses.pivot_table(index="size", columns=["encoding", "col_alo"], values="clauses", aggfunc="first").reset_index()
    clause_table.columns = [
        "size" if (column == "size" or (isinstance(column, tuple) and column[0] == "size"))
        else f"{encoding}_{'with_alo' if alo else 'without_alo'}"
        for column in clause_table.columns
        for encoding, alo in ([column] if isinstance(column, tuple) else [(str(column), False)])
    ]
    clause_table = clause_table.sort_values("size")
    clause_table.to_csv(table_dir / "clauses_by_encoding.csv", index=False)
    markdown_sections.extend(["## Clause growth by encoding", clause_table.to_markdown(index=False), ""])

    native = data[data["approach"].isin(["ILP", "CP"])][["size", "solver", "encoding_time", "solve_time", "total_time", "status"]]
    native = native.sort_values(["size", "solver"])
    native.to_csv(table_dir / "native_solver_comparison.csv", index=False)
    markdown_sections.extend(["## HiGHS and OR-Tools", native.to_markdown(index=False, floatfmt=".6g"), ""])
    markdown_sections.extend(["## Complete N-Queens Dataset", data.to_markdown(index=False, floatfmt=".6g"), ""])
    (table_dir / "comparison_tables.md").write_text("\n".join(markdown_sections), encoding="utf-8")


def plot_results(input_path: Path, output_dir: Path) -> None:
    data = pd.read_csv(input_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    sat = data[data["approach"] == "SAT"].copy()
    sat["label"] = sat["solver"] + " / " + sat["encoding"]

    clauses = sat.drop_duplicates(["size", "encoding", "col_alo"]).copy()
    for col_alo, suffix in ((False, "without_alo"), (True, "with_alo")):
        subset = clauses[clauses["col_alo"] == col_alo].copy()
        subset["label"] = subset["encoding"]
        _save_line_plot(subset, "clauses", "Clauses", f"Clause growth by encoding ({suffix.replace('_', ' ')})", output_dir / f"clauses_by_encoding_{suffix}.png")

    for solver in sat["solver"].drop_duplicates():
        _save_solver_comparison(sat[sat["solver"] == solver], solver, output_dir / f"sat_{solver}_alo_comparison.png")

    native = data[data["approach"].isin(["ILP", "CP"])].copy()
    native["label"] = native["solver"]
    _save_line_plot(native, "solve_time", "Average solve time (seconds)", "HiGHS versus OR-Tools CP-SAT", output_dir / "native_solver_comparison.png")
    _write_tables(data, output_dir)


if __name__ == "__main__":
    plot_results(Path("results/nqueens_average.csv"), Path("results/plots"))