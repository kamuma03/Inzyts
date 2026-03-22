"""
Profile Code Generator Agent - Generates Jupyter notebook cells for profiling.

This agent takes the logical specification from the Data Profiler (e.g., "create a
histogram for column X") and translates it into actual executable Python code
(pandas/matplotlib/seaborn).

It supports:
1. LLM-based code generation for custom, context-aware plotting.
2. Robust template fallback if the LLM produces invalid JSON or code.
"""

import json
import textwrap
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.agents.base import BaseAgent
from src.prompts import PROFILE_CODEGEN_PROMPT
from src.models.state import AnalysisState, Phase
from src.models.cells import NotebookCell
from src.models.handoffs import (
    ProfilerToCodeGenHandoff,
    ProfileCodeToValidatorHandoff,
    DataType,
)
from src.utils.cache_manager import CacheManager
from src.utils.logger import get_logger

logger = get_logger()


class ProfileCodeGeneratorAgent(BaseAgent):
    """
    Profile Code Generator Agent for Phase 1.

    Responsibility: Convert high-level analysis requirements into
    concrete, bug-free Python code cells for a Jupyter notebook.
    """

    def __init__(self, provider: Optional[str] = None, model: Optional[str] = None):
        super().__init__(
            name="ProfileCodeGenerator",
            phase=Phase.PHASE_1,
            system_prompt=PROFILE_CODEGEN_PROMPT,
            provider=provider,
            model=model,
        )

    def process(self, state: AnalysisState, **kwargs) -> Dict[str, Any]:
        """
        Generate notebook cells based on profiling specification.

        Args:
            state: Current analysis state.
            **kwargs: Must include 'specification' (ProfilerToCodeGenHandoff).

        Returns:
            Dictionary containing 'handoff' (ProfileCodeToValidatorHandoff)
            with the generated cells.
        """
        spec: ProfilerToCodeGenHandoff | None = kwargs.get("specification")

        if spec is None:
            return {
                "handoff": None,
                "confidence": 0.0,
                "issues": [
                    self._create_issue(
                        "no_spec",
                        "missing_input",
                        "error",
                        "No profiling specification provided",
                    )
                ],
                "suggestions": ["Ensure Data Profiler runs first"],
            }

        # CACHE CHECK
        cache_manager = CacheManager()
        csv_hash = cache_manager.get_csv_hash(spec.csv_path)

        cached_result = None
        if state.using_cached_profile:
            cached_result = cache_manager.load_artifact(
                csv_hash, "profile_codegen_output"
            )

        if cached_result:
            # Reconstruct generated cells and handoff from cache
            try:
                cells = [
                    NotebookCell(**cell) for cell in cached_result.get("cells", [])
                ]
                result = cached_result.get("result", {})

                # We need to rebuild the handoff using the cached result logic
                # The cached_result should basically store what we need to build the handoff
                # Let's assume we cache the 'result' dict from LLM/Template and reconstruct

                handoff = ProfileCodeToValidatorHandoff(
                    cells=cells,
                    total_cells=len(cells),
                    cell_purposes=result.get("cell_purposes", {}),
                    required_imports=result.get(
                        "required_imports", ["pandas", "numpy", "matplotlib", "seaborn"]
                    ),
                    expected_statistics=result.get("expected_statistics", []),
                    expected_visualizations=result.get("expected_visualizations", 0),
                    expected_markdown_sections=result.get(
                        "expected_markdown_sections", []
                    ),
                    source_specification=spec,
                )

                return {
                    "handoff": handoff,
                    "confidence": result.get("confidence", 0.8),
                    "issues": [],
                    "suggestions": [],
                }
            except Exception as e:
                # If cache reconstruction fails, proceed to generate
                logger.warning(f"Failed to use cached profile codegen: {e}")

        # Build prompt with specification
        prompt = self._build_generation_prompt(spec)

        # Try LLM generation
        response = ""
        try:
            response = self.llm_agent.invoke_with_json(prompt)
            result = json.loads(response)
            cells = [NotebookCell(**cell) for cell in result.get("cells", [])]
        except Exception as e:
            logger.warning(f"Failed to parse profiler output as JSON: {e}")
            logger.warning(f"Raw response was: {response[:1000]}")
            # Fall back to template-based generation
            cells = self._generate_template_cells(spec)
            result = self._build_template_result(cells, spec)

        # Save to cache
        cache_data = {
            "cells": [
                c.model_dump() for c in cells
            ],
            "result": result,
        }
        cache_manager.save_artifact(csv_hash, "profile_codegen_output", cache_data)
        
        # Build handoff
        handoff = ProfileCodeToValidatorHandoff(
            cells=cells,
            total_cells=len(cells),
            cell_purposes=result.get("cell_purposes", {}),
            required_imports=result.get(
                "required_imports", ["pandas", "numpy", "matplotlib", "seaborn"]
            ),
            expected_statistics=result.get("expected_statistics", []),
            expected_visualizations=result.get("expected_visualizations", 0),
            expected_markdown_sections=result.get("expected_markdown_sections", []),
            source_specification=spec,
        )

        return {
            "handoff": handoff,
            "confidence": result.get("confidence", 0.8),
            "issues": [],
            "suggestions": [],
        }

    def _build_generation_prompt(self, spec: ProfilerToCodeGenHandoff) -> str:
        """Build the prompt for LLM code generation."""
        # Group columns by type to save tokens
        cols_by_type: Dict[str, List[str]] = {}
        for col in spec.columns:
            dtype = col.detected_type.value
            if dtype not in cols_by_type:
                cols_by_type[dtype] = []
            cols_by_type[dtype].append(col.name)

        columns_info = []
        for dtype, cols in cols_by_type.items():
            columns_info.append(f"  - {dtype}: {', '.join(cols)}")
        columns_info_str = "\n".join(columns_info)

        stats_info = "\n".join(
            [
                f"  - {req.stat_type}: {req.target_columns}"
                for req in spec.statistics_requirements
            ]
        )

        viz_info = "\n".join(
            [
                f"  - {req.viz_type}: {req.target_columns} - '{req.title}'"
                for req in spec.visualization_requirements
            ]
        )

        quality_info = "\n".join(
            [
                f"  - {req.check_type}: {req.target_columns}"
                for req in spec.quality_check_requirements
            ]
        )

        remediation_instruction = ""
        if spec.remediation_plans:
            remediation_instruction = """
        DUAL-PATH ANALYSIS REQUIRED:
        You must perform analysis on BOTH the original data and the remediated data.
        1. Perform full profiling on the original data (df).
        2. Create a new dataframe 'df_remediated = df.copy()'.
        3. Apply the following remediations to 'df_remediated':
        """
            for plan in spec.remediation_plans:
                remediation_instruction += f"   - {plan.issue.issue_id}: {plan.code_explanation} (Code: {plan.code_snippet})\n"

            remediation_instruction += """
        4. Perform summary profiling on 'df_remediated' (at least df.info() and df.describe()).
        5. Compare key metrics between original and remediated data.
        """

        pca_instruction = ""
        if spec.pca_config and spec.pca_config.enabled:
            pca_instruction = f"""
        DIMENSIONALITY REDUCTION (PCA) REQUIRED:
        Perform PCA analysis on numeric columns:
        1. Standardize the data (StandardScaler).
        2. Fit PCA (n_components={spec.pca_config.feature_count_threshold} or heuristic).
        3. Generate Scree Plot (explained variance).
        4. Generate 2D projection scatter plot (first 2 components).
        5. Provide interpretation of component loadings.
        """

        return f"""Generate Jupyter notebook cells for data profiling based on this specification:
        
        CSV FILENAME: {Path(spec.csv_path).name}
        ROWS: {spec.row_count}
        COLUMNS: {spec.column_count}

        COLUMN SPECIFICATIONS:
        {columns_info_str}

        STATISTICS REQUIREMENTS:
        {stats_info}

        VISUALIZATION REQUIREMENTS:
        {viz_info}

        QUALITY CHECK REQUIREMENTS:
        {quality_info}
        
        {remediation_instruction}
        
        {pca_instruction}

        Generate complete, executable code cells that:
        1. Import all necessary libraries
        2. Load the CSV file
        3. Display basic data info
        4. Generate all required statistics (For correlation: create dummies from specific columns and concat with numeric, DO NOT replace columns in main df)
        5. Create all required visualizations
        6. Assess data quality
        7. Summarize findings
        8. Do not include a separate title/header cell (handled by Orchestrator).
        9. IMPORTANT: Use the following robust code snippet to load the CSV, to handle various delimiters (like ;, |, tab) and encodings:
           ```python
           import pandas as pd
           import csv
           from pathlib import Path

           filename = '{spec.csv_path}'
           if not Path(filename).exists():
               base_name = Path(filename).name
               if Path(base_name).exists():
                   filename = base_name
               elif (Path("data/uploads") / base_name).exists():
                   filename = str(Path("data/uploads") / base_name)
           
           # Robust data loading
           try:
               # Try reading with default settings first
               df = pd.read_csv(filename)
               
               # Check if we only read one column but there are separators in the first line
               if len(df.columns) == 1:
                   with open(filename, 'r', errors='ignore') as f:
                       first_line = f.readline()
                   
                   # Check for common delimiters
                   for sep in [';', '\\t', '|']:
                       if sep in first_line:
                           # Retry with this separator
                           df = pd.read_csv(filename, sep=sep)
                           break
           except Exception:
               # Fallback to python engine which can auto-detect
               try:
                   df = pd.read_csv(filename, sep=None, engine='python')
               except:
                   # Last resort: try encodings
                   for encoding in ['utf-8', 'latin-1', 'cp1252']:
                       try:
                           df = pd.read_csv(filename, sep=None, engine='python', encoding=encoding)
                           break
                       except:
                           continue
           ```

Return as JSON with the specified format."""

    def _generate_template_cells(
        self, spec: ProfilerToCodeGenHandoff
    ) -> List[NotebookCell]:
        """Generate cells using templates when LLM fails."""
        cells = []

        # Title cell removed (handled by Orchestrator)

        # Imports cell
        imports = textwrap.dedent("""
            import csv
            from pathlib import Path
            import pandas as pd
            import numpy as np
            import matplotlib.pyplot as plt
            import seaborn as sns
            import warnings

            warnings.filterwarnings('ignore')
            plt.style.use('seaborn-v0_8-whitegrid')
            %matplotlib inline
        """).strip()
        cells.append(NotebookCell(cell_type="code", source=imports))

        # Data loading cell
        load_code = textwrap.dedent(f"""
            # Load the dataset with support for CSV and Parquet
            import csv
            from pathlib import Path

            filename = '{spec.csv_path}'
            if not Path(filename).exists():
                base_name = Path(filename).name
                if Path(base_name).exists():
                    filename = base_name
                elif (Path("data/uploads") / base_name).exists():
                    filename = str(Path("data/uploads") / base_name)
            
            # Check for Parquet
            if filename.lower().endswith('.parquet'):
                df = pd.read_parquet(filename)
                print(f"Successfully loaded Parquet file: {{filename}}")
            else:
                # Assume CSV - Auto-detect delimiter and encoding
                encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']
                df = None
                
                for encoding in encodings:
                    try:
                        # Auto-detect delimiter
                        delimiter = ','
                        try:
                            with open(filename, 'r', encoding=encoding) as f:
                                sample = f.read(4096)
                                dialect = csv.Sniffer().sniff(sample, delimiters=',;\\t|')
                                delimiter = dialect.delimiter
                        except Exception:
                            pass
                            
                        df = pd.read_csv(filename, delimiter=delimiter, encoding=encoding)
                        print(f"Successfully loaded CSV with encoding: {{encoding}}")
                        break
                    except UnicodeDecodeError:
                        continue
                    except Exception as e:
                        # If this was the last encoding, raise error
                        if encoding == encodings[-1]:
                            raise e
            
            if df is None:
                raise ValueError("Failed to load file with tried methods")

            if 'delimiter' in locals():
                print(f"Detected delimiter: '{{delimiter}}'")
            print(f"Dataset Shape: {{df.shape[0]}} rows x {{df.shape[1]}} columns")
            df.head()
        """).strip()
        cells.append(NotebookCell(cell_type="code", source=load_code))

        # Data overview markdown
        cells.append(
            NotebookCell(
                cell_type="markdown",
                source="### 2.1 Data Overview\n\nBasic information about the dataset structure and data types.",
            )
        )

        # Data info cell
        info_code = textwrap.dedent("""
            # Data types and non-null counts
            df.info()
            print("\\n" + "="*50 + "\\n")
            print("Column data types:")
            print(df.dtypes)
        """).strip()
        cells.append(NotebookCell(cell_type="code", source=info_code))

        # Statistics markdown
        cells.append(
            NotebookCell(
                cell_type="markdown",
                source="### 2.2 Descriptive Statistics\n\nSummary statistics for numeric columns.",
            )
        )

        # Descriptive stats cell
        numeric_cols = [
            col.name
            for col in spec.columns
            if col.detected_type
            in [DataType.NUMERIC_CONTINUOUS, DataType.NUMERIC_DISCRETE]
        ]

        stats_code = textwrap.dedent("""
            # Descriptive statistics
            df.describe(include='all').T
        """).strip()
        cells.append(NotebookCell(cell_type="code", source=stats_code))

        # Correlation section (if numeric columns exist)
        if len(numeric_cols) > 1:
            cells.append(
                NotebookCell(
                    cell_type="markdown",
                    source="### 2.3 Correlation Analysis\n\nCorrelation matrix for numeric columns.",
                )
            )

            corr_code = textwrap.dedent("""
                # Correlation matrix
                # Select values for correlation: Numeric + One-Hot Encoded Low-Cardinality Categoricals
                numeric_df = df.select_dtypes(include=['number'])
                
                # Encode categorical variables with < 15 unique values
                cat_cols = [c for c in df.select_dtypes(include=['object', 'category']).columns 
                           if df[c].nunique() < 15]
                
                if cat_cols:
                    encoded_df = pd.get_dummies(df[cat_cols], drop_first=False)
                    corr_df = pd.concat([numeric_df, encoded_df], axis=1)
                else:
                    corr_df = numeric_df
                
                if len(corr_df.columns) > 1:
                    plt.figure(figsize=(12, 10))
                    correlation_matrix = corr_df.corr()
                    
                    # Mask upper triangle to reduce noise
                    mask = np.triu(np.ones_like(correlation_matrix, dtype=bool))
                    
                    sns.heatmap(correlation_matrix, annot=True, mask=mask, cmap='coolwarm', center=0, fmt='.2f', linewidths=0.5)
                    plt.title('Correlation Matrix (Numeric & Encoded Categorical Features)')
                    plt.tight_layout()
                    plt.show()
            """).strip()
            cells.append(NotebookCell(cell_type="code", source=corr_code))

        # Visualizations markdown
        cells.append(
            NotebookCell(
                cell_type="markdown",
                source="### 2.4 Data Distributions\n\nVisualizations of column distributions.",
            )
        )

        # Distribution plots
        # Distribution plots
        dist_code = textwrap.dedent("""
            # Distribution plots for numeric columns
            numeric_df = df.select_dtypes(include=[np.number])
            
            if not numeric_df.empty:
                n_cols = min(len(numeric_df.columns), 4)
                n_rows = (len(numeric_df.columns) + n_cols - 1) // n_cols
                
                fig, axes = plt.subplots(n_rows, n_cols, figsize=(4*n_cols, 4*n_rows))
                axes = np.array(axes).flatten() if isinstance(axes, np.ndarray) else [axes]
                
                for idx, col in enumerate(numeric_df.columns):
                    if idx < len(axes):
                        axes[idx].hist(numeric_df[col].dropna(), bins=30, edgecolor='black', alpha=0.7)
                        axes[idx].set_title(f'{col}')
                        axes[idx].set_xlabel(col)
                        axes[idx].set_ylabel('Frequency')
                
                # Hide empty subplots
                for idx in range(len(numeric_df.columns), len(axes)):
                    axes[idx].set_visible(False)
                
                plt.tight_layout()
                plt.show()
        """).strip()
        cells.append(NotebookCell(cell_type="code", source=dist_code))

        # Box plots
        # Box plots
        box_code = textwrap.dedent("""
            # Box plots for numeric columns
            if not numeric_df.empty:
                n_cols = min(len(numeric_df.columns), 4)
                n_rows = (len(numeric_df.columns) + n_cols - 1) // n_cols
                
                fig, axes = plt.subplots(n_rows, n_cols, figsize=(4*n_cols, 4*n_rows))
                axes = np.array(axes).flatten() if isinstance(axes, np.ndarray) else [axes]
                
                for idx, col in enumerate(numeric_df.columns):
                    if idx < len(axes):
                        axes[idx].boxplot(numeric_df[col].dropna())
                        axes[idx].set_title(f'{col}')
                
                for idx in range(len(numeric_df.columns), len(axes)):
                    axes[idx].set_visible(False)
                
                plt.tight_layout()
                plt.show()
        """).strip()
        cells.append(NotebookCell(cell_type="code", source=box_code))

        # Data quality markdown
        cells.append(
            NotebookCell(
                cell_type="markdown",
                source="### 2.5 Data Quality Assessment\n\nAnalysis of missing values, duplicates, and potential issues.",
            )
        )

        # Missing values analysis
        # Missing values analysis
        quality_code = textwrap.dedent("""
            # Missing values analysis
            missing_df = pd.DataFrame({
                'Column': df.columns,
                'Missing Count': df.isnull().sum(),
                'Missing Percentage': (df.isnull().sum() / len(df) * 100).round(2)
            })
            missing_df = missing_df[missing_df['Missing Count'] > 0].sort_values('Missing Percentage', ascending=False)
            
            if not missing_df.empty:
                print("Columns with Missing Values:")
                print(missing_df.to_string(index=False))
                
                # Visualize missing values
                plt.figure(figsize=(10, 6))
                plt.bar(missing_df['Column'], missing_df['Missing Percentage'])
                plt.title('Missing Values by Column')
                plt.xlabel('Column')
                plt.ylabel('Missing Percentage (%)')
                plt.xticks(rotation=45, ha='right')
                plt.tight_layout()
                plt.show()
            else:
                print("No missing values found in the dataset!")
            
            # Duplicate rows
            duplicates = df.duplicated().sum()
            print(f"\\nDuplicate rows: {duplicates} ({duplicates/len(df)*100:.2f}%)")
        """).strip()
        cells.append(NotebookCell(cell_type="code", source=quality_code))

        # Summary markdown
        cells.append(
            NotebookCell(
                cell_type="markdown",
                source="### 2.6 Profiling Summary\n\nKey findings from the data profiling analysis.",
            )
        )

        # Summary cell
        summary_code = textwrap.dedent(f"""
            # Data Profiling Summary
            print("="*60)
            print("DATA PROFILING SUMMARY")
            print("="*60)
            print(f"Dataset: {spec.csv_path}")
            print(f"Rows: {{len(df):,}}")
            print(f"Columns: {{len(df.columns)}}")
            print(f"Memory Usage: {{df.memory_usage(deep=True).sum() / 1024 / 1024:.2f}} MB")
            print(f"Missing Values: {{df.isnull().sum().sum():,}} ({{(df.isnull().sum().sum() / df.size * 100):.2f}}%)")
            print(f"Duplicate Rows: {{df.duplicated().sum():,}}")
            print("="*60)
            
            # Data types breakdown
            print("\\nData Types:")
            for dtype, count in df.dtypes.value_counts().items():
                print(f"  - {{dtype}}: {{count}} columns")
        """).strip()
        cells.append(NotebookCell(cell_type="code", source=summary_code))

        # v1.9.0: Remediation Section
        if spec.remediation_plans:
            cells.append(
                NotebookCell(
                    cell_type="markdown",
                    source="### 2.7 Data Quality Remediation\n\nApplying automated remediations to create a clean dataset for dual-path analysis.",
                )
            )

            remediation_code = "df_remediated = df.copy()\n\n"
            for plan in spec.remediation_plans:
                remediation_code += (
                    f"# {plan.issue.issue_id}: {plan.code_explanation}\n"
                )
                remediation_code += f"{plan.code_snippet}\n"

            remediation_code += textwrap.dedent("""
                
                print("Remediation complete. Comparing shapes:")
                print(f"Original: {df.shape}")
                print(f"Remediated: {df_remediated.shape}")
            """).strip()

            cells.append(NotebookCell(cell_type="code", source=remediation_code))

            # Profile Remediated
            cells.append(
                NotebookCell(
                    cell_type="markdown",
                    source="### 2.8 Remediated Data Profile\n\nSummary of the remediated dataset.",
                )
            )

            profile_rem_code = textwrap.dedent("""
                # Profile Remediated Data
                print("Remediated Data Info:")
                df_remediated.info()
                
                print("\\nRemediated Data Statistics:")
                display(df_remediated.describe(include='all').T)
            """).strip()
            cells.append(NotebookCell(cell_type="code", source=profile_rem_code))

        # v1.9.0: PCA Section
        if spec.pca_config and spec.pca_config.enabled:
            cells.append(
                NotebookCell(
                    cell_type="markdown",
                    source="### 2.9 Dimensionality Reduction (PCA)\n\nPrincipal Component Analysis to identify key dimensions.",
                )
            )

            pca_code = textwrap.dedent(f"""
                from sklearn.decomposition import PCA
                from sklearn.preprocessing import StandardScaler
                
                # Select numeric columns for PCA
                # If remediation happened, use df_remediated, else df
                target_df = df_remediated if 'df_remediated' in locals() else df
                numeric_cols_pca = target_df.select_dtypes(include=[np.number]).columns.tolist()
                
                if len(numeric_cols_pca) > 1:
                    # Standardize
                    scaler = StandardScaler()
                    X_scaled = scaler.fit_transform(target_df[numeric_cols_pca].dropna())
                    
                    # Fit PCA
                    n_components = min({spec.pca_config.feature_count_threshold}, len(numeric_cols_pca), 10)
                    pca = PCA(n_components=n_components)
                    pca_components = pca.fit_transform(X_scaled)
                    
                    # Variance
                    explained_variance = pca.explained_variance_ratio_
                    cumulative_variance = np.cumsum(explained_variance)
                    
                    print(f"Explained Variance Ratios: {{explained_variance}}")
                    
                    # Scree Plot
                    plt.figure(figsize=(10, 6))
                    plt.plot(range(1, len(explained_variance) + 1), cumulative_variance, marker='o', linestyle='--')
                    plt.title('PCA Explained Variance (Scree Plot)')
                    plt.xlabel('Number of Components')
                    plt.ylabel('Cumulative Explained Variance')
                    plt.grid(True)
                    plt.show()
                else:
                    print("Not enough numeric columns for PCA.")
            """).strip()
            cells.append(NotebookCell(cell_type="code", source=pca_code))

        return cells

    def _build_template_result(
        self, cells: List[NotebookCell], spec: ProfilerToCodeGenHandoff
    ) -> Dict[str, Any]:
        """Build result dictionary for template-generated cells."""
        cell_purposes = {}
        for idx, cell in enumerate(cells):
            if cell.cell_type == "markdown":
                # Extract title from markdown
                first_line = cell.source.split("\n")[0].strip("#").strip()
                cell_purposes[str(idx)] = first_line or "Markdown"
            else:
                cell_purposes[str(idx)] = f"Code cell {idx}"

        return {
            "expected_markdown_sections": [
                "Data Profiling Report",
                "Data Overview",
                "Descriptive Statistics",
                "Data Quality Assessment",
                "Summary",
            ],
            "confidence": 0.85,
        }
