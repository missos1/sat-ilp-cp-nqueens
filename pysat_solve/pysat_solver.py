MATRIX_SIZES = [8, 16, 32, 64, 128, 256] 
ENC_TYPES = [EncType.seqcounter, EncType.cardnetwrk, EncType.pairwise, EncType.sortnetwrk, EncType.totalizer]
SAT_SOLVERS = ["cadical153", "glucose42", "cryptominisat5", "minisat22"]
ENC_TYPES = {
    EncType.pairwise: "pairwise",
    EncType.seqcounter: "seqcounter",
    EncType.sortnetwrk: "sortnetwrk",
    EncType.cardnetwrk: "cardnetwrk",
    EncType.bitwise: "bitwise"
}
SOLVER = "cadical153"

for size in MATRIX_SIZES:
    for (enc_type, enc_type_name) in ENC_TYPES.items():
        start_enc = time.perf_counter()
        cnf = n_queens_cnf(size, enc_type)
        end_enc = time.perf_counter()
        print(f"Encoding time for size {size} with encoding {enc_type_name}: {end_enc - start_enc:.6f} seconds")
        print(len(cnf.clauses), "clauses")
        
        solver_time_list = []
        for i in range(0, 5):
            with Solver(name=SOLVER, use_timer=True) as solver:
                solver.append_formula(cnf)
                if solver.solve():
                    print(f"Solution found for size {size} with encoding {enc_type_name} using solver {SOLVER}.")
                    solver_time_list.append(solver.time())
                    # print(solver.accum_stats())
                else:
                    print(f"No solution found for size {size} with encoding {enc_type_name} using solver {SOLVER}.")
        
        print(solver_time_list.sort()[2])# median time
        print("\n")