from nqueens_cnf import n_queens_cnf
from pysat.solvers import Solver
from pysat.card import EncType
from statistics import mean, stdev
from trial_data import TrialData

MATRIX_SIZE = 100
SOLVER = "cadical153"

ENC_TYPES= {
    EncType.pairwise: "pairwise",
    EncType.seqcounter: "seqcounter",
    EncType.ladder: "ladder"
}


trials: list[TrialData] = []
id = 1
for enc_type, enc_str in ENC_TYPES.items():
    non_col_alo_cnf = n_queens_cnf(MATRIX_SIZE, enc_type=enc_type, col_alo=False)
    col_alo_cnf = n_queens_cnf(MATRIX_SIZE, enc_type=enc_type, col_alo=True)
    for i in range(0, 10):
        with Solver(name=SOLVER, use_timer=True) as solver:
            cnf = col_alo_cnf  if i % 2 == 0 else non_col_alo_cnf
            key = "col_alo" if i % 2 == 0 else "non_col_alo"
            solver.append_formula(cnf)
            if solver.solve():
                print(f"Solution found for size {MATRIX_SIZE} with encoding {enc_str} using solver {SOLVER}.")
                stats = solver.accum_stats()
                trials.append(TrialData(
                    trial_id=id,
                    matrix_size=MATRIX_SIZE,
                    solver=SOLVER,
                    encoding=enc_str,
                    col_alo=True if i % 2 == 0 else False,
                    variables=cnf.nv,
                    clauses=len(cnf.clauses),
                    time=solver.time(),
                    **stats,
                ))
            else:
                print(f"No solution found for size {MATRIX_SIZE} with encoding {enc_str} using solver {SOLVER}.")
    id = id + 1
print(trials)