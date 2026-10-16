"""Benchmark N-Queens with SAT, HiGHS, and OR-Tools CP-SAT."""

from __future__ import annotations

import argparse
import csv
import multiprocessing as mp
from queue import Empty
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean
from typing import Any

from highspy import Highs, HighsVarType
from ortools.sat.python import cp_model
import pycryptosat
from pysat.card import EncType
from pysat.solvers import Solver

try:
    from .nqueens_cnf import n_queens_cnf
except ImportError:
    from nqueens_cnf import n_queens_cnf


ENCODINGS = {
    EncType.pairwise: "pairwise",
    EncType.seqcounter: "seqcounter",
    EncType.totalizer: "totalizer",
    EncType.bitwise: "bitwise",
}
SAT_SOLVERS = ("cadical153", "minisat22")
SOLVER_CHOICES = SAT_SOLVERS
ENCODING_CHOICES = tuple(ENCODINGS.values())


@dataclass
class BenchmarkRow:
    size: int
    approach: str
    solver: str
    encoding: str
    col_alo: bool
    variables: int
    clauses: int
    encoding_time: float
    solve_time: float
    total_time: float
    status: str
    conflicts: int = 0
    decisions: int = 0
    propagations: int = 0


def build_sat_instance(size: int, enc_type: EncType, col_alo: bool) -> tuple[Any, float]:
    encoding_start = time.perf_counter()
    cnf = n_queens_cnf(size, enc_type=enc_type, col_alo=col_alo)
    return cnf, time.perf_counter() - encoding_start


def _heartbeat(start: float, finished: threading.Event, label: str) -> None:
    while not finished.wait(1):
        elapsed = time.perf_counter() - start
        print(f"\r  {label}: elapsed {elapsed:8.1f}s", end="", flush=True)


def _finish_heartbeat(start: float, finished: threading.Event, label: str) -> float:
    finished.set()
    elapsed = time.perf_counter() - start
    print(f"\r  {label}: finished in {elapsed:.3f}s" + " " * 12, flush=True)
    return elapsed


def _pysat_worker(solver_name: str, clauses: list[list[int]], result_queue: Any) -> None:
    try:
        with Solver(name=solver_name, use_timer=True) as solver:
            solver.append_formula(clauses)
            solve_start = time.perf_counter()
            solved = solver.solve()
            solve_time = time.perf_counter() - solve_start
            stats = solver.accum_stats()
        result_queue.put(("SAT" if solved else "UNSAT", solve_time, stats))
    except MemoryError:
        result_queue.put(("MEMORY_ERROR", 0.0, {}))


def benchmark_sat(size: int, cnf: Any, encoding_time: float, solver_name: str, enc_type: EncType, col_alo: bool, timeout: float) -> BenchmarkRow:
    result_queue = mp.Queue()
    process = mp.Process(target=_pysat_worker, args=(solver_name, cnf.clauses, result_queue))
    solve_start = time.perf_counter()
    process.start()
    while process.is_alive() and time.perf_counter() - solve_start < timeout:
        process.join(1)
        elapsed = time.perf_counter() - solve_start
        if process.is_alive():
            print(f"\r  solving {solver_name}: elapsed {elapsed:8.1f}s", end="", flush=True)
    timed_out = process.is_alive()
    if timed_out:
        process.terminate()
        process.join()
        status, solve_time, stats = "TIMEOUT", timeout, {}
        print(f"\r  solving {solver_name}: TIMEOUT after {timeout:.1f}s" + " " * 12, flush=True)
    else:
        try:
            status, solve_time, stats = result_queue.get(timeout=1)
        except Empty:
            status, solve_time, stats = "ERROR", time.perf_counter() - solve_start, {}
        print(f"\r  solving {solver_name}: finished in {time.perf_counter() - solve_start:.3f}s" + " " * 12, flush=True)
    return BenchmarkRow(size, "SAT", solver_name, ENCODINGS[enc_type], col_alo, cnf.nv, len(cnf.clauses), encoding_time, solve_time, encoding_time + solve_time, status, stats.get("conflicts", 0), stats.get("decisions", 0), stats.get("propagations", 0))


def _cryptosat_worker(clauses: list[list[int]], result_queue: Any) -> None:
    solver = pycryptosat.Solver()
    for clause in clauses:
        solver.add_clause(clause)
    result_queue.put(solver.solve()[0])


def benchmark_cryptosat(size: int, cnf: Any, encoding_time: float, enc_type: EncType, col_alo: bool, timeout: float) -> BenchmarkRow:
    result_queue = mp.Queue()
    process = mp.Process(target=_cryptosat_worker, args=(cnf.clauses, result_queue))
    solve_start = time.perf_counter()
    process.start()
    while process.is_alive() and time.perf_counter() - solve_start < timeout:
        process.join(1)
        elapsed = time.perf_counter() - solve_start
        if process.is_alive():
            print(f"\r  solving cryptosat: elapsed {elapsed:8.1f}s", end="", flush=True)
    timed_out = process.is_alive()
    if timed_out:
        process.terminate()
        process.join()
        print(f"\r  solving cryptosat: TIMEOUT after {timeout:.1f}s" + " " * 12, flush=True)
    solve_time = time.perf_counter() - solve_start
    solved = not result_queue.empty() and result_queue.get()
    if not timed_out:
        print(f"\r  solving cryptosat: finished in {solve_time:.3f}s" + " " * 12, flush=True)
    return BenchmarkRow(size, "SAT", "cryptosat", ENCODINGS[enc_type], col_alo, cnf.nv, len(cnf.clauses), encoding_time, solve_time, encoding_time + solve_time, "TIMEOUT" if timed_out else ("SAT" if solved else "UNSAT"))


def build_cp_model(size: int) -> cp_model.CpModel:
    model = cp_model.CpModel()
    queens = [[model.new_bool_var(f"q_{row}_{col}") for col in range(size)] for row in range(size)]
    for row in range(size):
        model.add_exactly_one(queens[row])
    for col in range(size):
        model.add_exactly_one(queens[row][col] for row in range(size))
    for diagonal in range(-(size - 1), size):
        model.add_at_most_one(queens[row][col] for row in range(size) for col in range(size) if row - col == diagonal)
    for diagonal in range(2 * size - 1):
        model.add_at_most_one(queens[row][col] for row in range(size) for col in range(size) if row + col == diagonal)
    return model


def benchmark_ortools(size: int, timeout: float) -> BenchmarkRow:
    start = time.perf_counter()
    model = build_cp_model(size)
    encoding_time = time.perf_counter() - start
    
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    solver.parameters.max_time_in_seconds = timeout
    
    solve_start = time.perf_counter()
    heartbeat_finished = threading.Event()
    heartbeat_thread = threading.Thread(target=_heartbeat, args=(solve_start, heartbeat_finished, "ortools_cp_sat"), daemon=True)
    heartbeat_thread.start()
    
    status = solver.solve(model)
    solve_time = time.perf_counter() - solve_start
    heartbeat_finished.set()
    
    print(f"\r  ortools_cp_sat: finished in {solve_time:.3f}s" + " " * 12, flush=True)
    return BenchmarkRow(
        size, 
        "CP", 
        "ortools_cp_sat", 
        "native_constraints", 
        True, size * size, 
        0, encoding_time, 
        solve_time, 
        encoding_time + solve_time, 
        solver.status_name(status), 
        solver.num_conflicts, 
        solver.num_branches, 0)


def benchmark_highs(size: int, timeout: float) -> BenchmarkRow:
    highs = Highs()
    highs.setOptionValue("output_flag", False)
    highs.setOptionValue("time_limit", timeout)
    
    start = time.perf_counter()
    queens = [[highs.addVariable(lb=0, ub=1, type=HighsVarType.kInteger, name=f"q_{row}_{col}") for col in range(size)] for row in range(size)]
    for row in range(size):
        highs.addConstr(sum(queens[row]) == 1)
    for col in range(size):
        highs.addConstr(sum(queens[row][col] for row in range(size)) == 1)
    for diagonal in range(-(size - 1), size):
        highs.addConstr(sum(queens[row][col] for row in range(size) for col in range(size) if row - col == diagonal) <= 1)
    for diagonal in range(2 * size - 1):
        highs.addConstr(sum(queens[row][col] for row in range(size) for col in range(size) if row + col == diagonal) <= 1)
    encoding_time = time.perf_counter() - start
    
    solve_start = time.perf_counter()
    heartbeat_finished = threading.Event()
    heartbeat_thread = threading.Thread(target=_heartbeat, args=(solve_start, heartbeat_finished, "highs"), daemon=True)
    heartbeat_thread.start()
    
    highs.run()
    solve_time = time.perf_counter() - solve_start
    heartbeat_finished.set()
    
    print(f"\r  highs: finished in {solve_time:.3f}s" + " " * 12, flush=True)
    return BenchmarkRow(size, "ILP", "highs", "native_constraints", True, size * size, 0, encoding_time, solve_time, encoding_time + solve_time, highs.modelStatusToString(highs.getModelStatus()))


def run_benchmark(
    sizes: list[int],
    repetitions: int,
    timeout: float,
    solvers: tuple[str, ...] = SAT_SOLVERS,
    encodings: tuple[str, ...] = ENCODING_CHOICES,
    alo_modes: tuple[bool, ...] = (False, True),
    include_native: bool = True,
    verbose: bool = True,
) -> list[BenchmarkRow]:
    rows: list[BenchmarkRow] = []
    encoding_items = [(enc_type, enc_name) for enc_type, enc_name in ENCODINGS.items() if enc_name in encodings]
    native_cases = 2 if include_native else 0
    total_cases = len(sizes) * (len(encoding_items) * len(solvers) * len(alo_modes) + native_cases)
    completed_cases = 0
    print(f"Starting benchmark: {total_cases} configurations x {repetitions} repetitions", flush=True)
    
    for size in sizes:
        print(f"\n=== Board size N={size} ===", flush=True)
        for enc_type, enc_name in encoding_items:
            for col_alo in alo_modes:
                print("  encoding CNF once for this ALO/encoding pair", flush=True)
                cnf, encoding_time = build_sat_instance(size, enc_type, col_alo)
                
                for solver_name in solvers:
                    label = f"SAT/{solver_name}/{enc_name}/{'ALO' if col_alo else 'no-ALO'}"
                    print(f"[{completed_cases + 1}/{total_cases}] {label}: running {repetitions} repetitions", flush=True)
                    trials = []
                    
                    for repetition in range(1, repetitions + 1):
                        if verbose:
                            print(f"  repetition {repetition}/{repetitions}", flush=True)
                        if solver_name == "cryptosat":
                            trials.append(benchmark_cryptosat(size, cnf, encoding_time, enc_type, col_alo, timeout))
                        else:
                            trials.append(benchmark_sat(size, cnf, encoding_time, solver_name, enc_type, col_alo, timeout))
                            
                    result = _average_row(trials)
                    rows.append(result)
                    completed_cases += 1
                    
                    print(f"  done: solve={result.solve_time:.6g}s, clauses={result.clauses}", flush=True)
        if include_native:
            for benchmarker in (benchmark_highs, benchmark_ortools):
                solver_name = "highs" if benchmarker is benchmark_highs else "ortools_cp_sat"
                print(f"[{completed_cases + 1}/{total_cases}] {solver_name}: running {repetitions} repetitions", flush=True)
            
                trials = []
                for repetition in range(1, repetitions + 1):
                    if verbose:
                        print(f"  repetition {repetition}/{repetitions}", flush=True)
                    trials.append(benchmarker(size, timeout))
                
                result = _average_row(trials)
                rows.append(result)
                completed_cases += 1
                print(f"  done: solve={result.solve_time:.6g}s, status={result.status}", flush=True)
    print(f"\nBenchmark complete: {completed_cases}/{total_cases} configurations", flush=True)
    return rows


def _average_row(rows: list[BenchmarkRow]) -> BenchmarkRow:
    result = BenchmarkRow(**asdict(rows[0]))
    for field in ("encoding_time", "solve_time", "total_time", "conflicts", "decisions", "propagations"):
        setattr(result, field, mean(getattr(row, field) for row in rows))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sizes", nargs="+", type=int, default=[8, 16, 32, 64])
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument("--timeout", type=float, default=300.0, help="Maximum seconds per solver repetition")
    parser.add_argument("--solvers", nargs="+", choices=SOLVER_CHOICES, default=list(SOLVER_CHOICES), help="SAT solvers to benchmark")
    parser.add_argument("--encodings", nargs="+", choices=ENCODING_CHOICES, default=list(ENCODING_CHOICES), help="Cardinality encodings to benchmark")
    parser.add_argument("--alo", choices=("both", "with", "without"), default="both", help="Column ALO cases to benchmark")
    parser.add_argument("--no-native", action="store_true", help="Skip HiGHS and OR-Tools")
    parser.add_argument("--output", type=Path, default=Path("results/nqueens_benchmark.csv"))
    parser.add_argument("--quiet", action="store_true", help="Hide per-repetition progress messages")
    args = parser.parse_args()
    alo_modes = {"both": (False, True), "with": (True,), "without": (False,)}[args.alo]
    rows = run_benchmark(
        args.sizes,
        args.repetitions,
        args.timeout,
        solvers=tuple(args.solvers),
        encodings=tuple(args.encodings),
        alo_modes=alo_modes,
        include_native=not args.no_native,
        verbose=not args.quiet,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=asdict(rows[0]).keys())
        writer.writeheader()
        writer.writerows(asdict(row) for row in rows)
    print(f"Wrote {len(rows)} benchmark rows to {args.output}")


if __name__ == "__main__":
    main()