# Environment Setup & Reproducibility Guide

Documentation for setting up and managing the Conda execution environment (`sat_env`) used by the benchmark suite.

---

## 1. Environment Overview

The benchmark relies on Python 3.12 with SAT/SMT backends, CP/MIP solvers, and data processing libraries:

| Category | Primary Packages | Role |
| :--- | :--- | :--- |
| **SAT Solvers & Encodings** | `python-sat` (PySAT), `pycryptosat`, `pyapproxmc`, `py-aiger`, `py-aiger-cnf` | CDCL backends (MiniSat, Glucose, CaDiCaL, CryptoMiniSat) and CNF/cardinality circuit conversions |
| **Native/Baseline Solvers** | `ortools`, `highspy` | Google OR-Tools (CP-SAT) and HiGHS MIP baselines |
| **Analysis & Visualization** | `pandas`, `numpy`, `matplotlib`, `tabulate` | Metric processing, table outputs, and scaling plot generation |

---

## 2. Installation & Synchronization

### Recreating from Environment File
To construct the exact environment using `environment.yml`:

```bash
conda env create -f environment.yml
conda activate sat_env
```

# N-Queens Benchmark CLI Reference

Command-line benchmark runner for evaluating N-Queens problem instances across board sizes, SAT encodings, and solver backends.

## Options

| Flag | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `--sizes` | `INT [INT ...]` | `8 16 32 64` | Target board dimensions ($N$). |
| `--repetitions` | `INT` | `5` | Iterations per configuration. |
| `--timeout` | `FLOAT` | `300.0` | Execution ceiling in seconds per run. |
| `--solvers` | `STR [STR ...]` | All choices | SAT solver engines to evaluate. |
| `--encodings` | `STR [STR ...]` | All choices | Cardinality encoding techniques. |
| `--alo` | `{both,with,without}` | `both` | Column At-Least-One (ALO) constraint mode. |
| `--no-native` | Flag | `False` | Disables non-SAT solvers (HiGHS, OR-Tools). |
| `--output` | `PATH` | `results/nqueens_benchmark.csv` | Output file destination for benchmark metrics. |
| `--quiet` | Flag | `False` | Disables per-repetition stdout logging. |

---

## Examples

### Default Benchmark
Executes default sizes (8, 16, 32, 64) across all configured backends and encodings with 5 repetitions:
```bash
python benchmark.py
```
# Data
Benchmark data in [result](results)
