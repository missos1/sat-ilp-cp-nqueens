from collections import defaultdict
from pysat.card import CardEnc, EncType
from pysat.formula import CNF
from pysat.solvers import Solver

def n_queens_cnf(n: int, enc_type: EncType = EncType.seqcounter, col_alo: bool = False) -> CNF:
    cnf = CNF()
    
    def var_map(row, col) -> int:
        return (row - 1) * n + col
    
    # ALO for each row (i.e {1 or 2 or 3})
    for row in range(1, n + 1):
        cnf.append([var_map(row, col) for col in range(1, n + 1)])
    
    #
    if col_alo:
        for col in range(1, n + 1):
            cnf.append([var_map(row, col) for row in range(1, n + 1)])
            
    top_id = n * n
    
    def apply_amo(var_list):
        nonlocal top_id
        if len(var_list) <= 1:
            return
        amo = CardEnc.atmost(lits=var_list, bound=1, vpool=None, encoding=enc_type, top_id=top_id)
        cnf.extend(amo.clauses)
        if amo.nv > top_id:
            top_id = amo.nv
    
    for row in range(1, n + 1):
        apply_amo([var_map(row, col) for col in range(1, n + 1)])
    for col in range(1, n + 1):
        apply_amo([var_map(row, col) for row in range(1, n + 1)])
        
    diag_diff = defaultdict(list)
    diag_sum = defaultdict(list)
    
    for row in range(1, n + 1):
        for col in range(1, n + 1):
            diag_diff[row - col].append(var_map(row, col))
            diag_sum[row + col].append(var_map(row, col))
            
    for group in diag_diff.values():
        apply_amo(group)
    for group in diag_sum.values():
        apply_amo(group)
    
    return cnf

