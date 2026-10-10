from dataclasses import dataclass

@dataclass
class TrialData:
    trial_id: int
    matrix_size: int
    solver: str
    encoding: str
    col_alo: bool
    variables: int
    clauses: int
    time: float
    restarts: int
    conflicts: int
    decisions: int
    propagations: int
    