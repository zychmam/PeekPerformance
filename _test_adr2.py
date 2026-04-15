from pathlib import Path
from src.demos.rating_calculator import compute_rating

demo = Path("tests/resources/1-37dcc63e-a583-44b2-ac32-3930afbdb274-1-1.dem")
summary, per_round = compute_rating(demo)
cols = ["Gracz", "Rating", "K", "A", "D", "ADR", "KPR", "KAST%", "Avg Swing"]
print(summary[cols].to_string(index=False))
print(f"\nMatch avg Rating: {summary['Rating'].mean():.3f}")


