from typing import List
from src.models.cells import NotebookCell


class CodeInjector:
    """Helper for injecting safety code into generated cells."""

    @staticmethod
    def inject_safety_net(cells: List[NotebookCell]) -> List[NotebookCell]:
        """
        Inject safety net code to prevent string leakage.
        Finds the point before train/test split and forces selection of numeric types.
        """
        safety_line = "\n# SAFETY NET: Drop any remaining string columns (like Surname) to prevent training errors\nX = X.select_dtypes(include=[np.number])\n"

        injected = False
        for cell in cells:
            # Matches usage of train_test_split, excludes imports
            if cell.cell_type == "code" and "train_test_split(" in cell.source:
                # Confirm X is likely defined or used here
                if "X =" in cell.source or "X," in cell.source:
                    # Inject before split - logic: find the line and insert before it
                    lines = cell.source.split("\n")
                    new_lines = []
                    for line in lines:
                        if "train_test_split" in line:
                            # Update safety line to include 'bool' or 'boolean' if needed, or exclude 'object'/'category'
                            # include=['number', 'bool'] covers most quantitative needs
                            safety_line_improved = "\n# SAFETY NET: Drop string columns to prevent training errors, ensuring bools are kept\nX = X.select_dtypes(include=[np.number, 'bool'])\n"
                            new_lines.append(safety_line_improved.strip())
                            injected = True
                        new_lines.append(line)
                    cell.source = "\n".join(new_lines)
                    if injected:
                        break

        # Fallback: If no split (e.g. clustering), look for "fit("
        if not injected:
            for cell in cells:
                if cell.cell_type == "code" and ".fit(" in cell.source:
                    cell.source = safety_line + cell.source
                    injected = True
                    break

        return cells
