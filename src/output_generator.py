"""Output CSV generator for Ghost Data Still Exists.
Produces compliant output.csv with valid JSON escaping and sorting.
"""

import csv
import json
from typing import List, Tuple, Dict, Any


def write_output_csv(results: List[Tuple[str, str, List[Dict[str, Any]]]], output_path: str = "output.csv"):
    """Writes the prediction results to the target CSV file.
    
    Each tuple is (case_id, deletion_status, steps).
    """
    # Sort results by case_id numeric index
    sorted_results = sorted(results, key=lambda x: int(x[0].split("_")[1]) if "_" in x[0] else x[0])
    
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(["case_id", "deletion_status", "steps_json"])
        
        for case_id, status, steps in sorted_results:
            steps_json_str = json.dumps(steps, separators=(",", ":"))
            writer.writerow([case_id, status, steps_json_str])
