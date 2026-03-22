import hashlib
import re
from pathlib import Path
from typing import List, Dict, Optional, Set

import pandas as pd
from difflib import SequenceMatcher

from ..models.multi_file import JoinCandidate, JoinType, MergedDataset, FileInput


class JoinDetector:
    """
    Detects and executes joins across multiple CSV files.

    Enhanced in v1.9 to use Dataset Info and user Analysis Question/Goal
    to intelligently determine how to link multiple files into a unified
    dataset for analysis and prediction.
    """

    # Thresholds
    NAME_SIMILARITY_THRESHOLD = 0.85  # Fuzzy match score
    VALUE_OVERLAP_THRESHOLD = 0.30  # Jaccard similarity minimum
    CONFIDENCE_THRESHOLD = 0.70  # Minimum to auto-execute

    # Keywords that indicate relationship hints in dataset info
    RELATIONSHIP_KEYWORDS = [
        "foreign key",
        "fk",
        "references",
        "links to",
        "related to",
        "joined with",
        "associated with",
        "primary key",
        "pk",
        "id",
        "identifier",
        "connects to",
        "lookup",
        "dimension",
        "fact",
    ]

    def detect_join_candidates(
        self,
        files: List[FileInput],
        dataframes: Dict[str, pd.DataFrame],
        dataset_info: Optional[Dict[str, str]] = None,
        user_question: Optional[str] = None,
    ) -> List[JoinCandidate]:
        """
        Detect potential join relationships between files.

        Enhanced to use Dataset Info and user's Analysis Question/Goal to:
        1. Identify explicit relationship hints in column descriptions
        2. Prioritize joins relevant to the user's analysis goal
        3. Provide smarter preprocessing recommendations for multi-file datasets

        Args:
            files: List of File inputs with metadata
            dataframes: Dictionary mapping file hashes to DataFrames
            dataset_info: Field descriptions from Dataset Info (col -> description)
            user_question: The user's analysis question/goal

        Returns:
            Sorted list of JoinCandidate objects by confidence
        """
        candidates = []

        # Parse relationship hints from dataset info
        relationship_hints = self._parse_relationship_hints(dataset_info or {})

        # Extract entities mentioned in user question for relevance scoring
        question_entities = self._extract_question_entities(user_question or "", files)

        # Get all pairs
        for i, left_file in enumerate(files):
            for j, right_file in enumerate(files):
                if i >= j:
                    continue

                left_df = dataframes[left_file.file_hash]
                right_df = dataframes[right_file.file_hash]
                left_alias = left_file.alias or left_file.file_hash
                right_alias = right_file.alias or right_file.file_hash

                # Check all column pairs
                for left_col in left_df.columns:
                    for right_col in right_df.columns:
                        candidate = self._evaluate_column_pair(
                            left_alias,
                            left_df,
                            left_col,
                            right_alias,
                            right_df,
                            right_col,
                            dataset_info=dataset_info,
                            relationship_hints=relationship_hints,
                            question_entities=question_entities,
                        )

                        if (
                            candidate and candidate.confidence_score >= 0.4
                        ):  # Keep somewhat low for inspection
                            candidates.append(candidate)

        # Sort by confidence
        candidates.sort(key=lambda x: x.confidence_score, reverse=True)
        return candidates

    def _parse_relationship_hints(
        self, dataset_info: Dict[str, str]
    ) -> Dict[str, List[str]]:
        """
        Parse dataset info descriptions to find relationship hints.

        Returns mapping of column -> list of referenced columns/tables
        Example: {"customer_id": ["customers", "id"]} if description says "Foreign key to customers.id"
        """
        hints = {}

        for col, description in dataset_info.items():
            if not description:
                continue

            desc_lower = description.lower()
            referenced = []

            # Look for relationship keywords
            for keyword in self.RELATIONSHIP_KEYWORDS:
                if keyword in desc_lower:
                    # Extract referenced table/column names
                    # Pattern: "foreign key to table.column" or "references table(column)"
                    patterns = [
                        r"(?:foreign key|fk|references|links to|related to)\s+(?:to\s+)?(\w+)(?:\.(\w+))?",
                        r"(\w+)_id\b",  # Common FK naming convention
                    ]
                    for pattern in patterns:
                        matches = re.findall(pattern, desc_lower)
                        for match in matches:
                            if isinstance(match, tuple):
                                referenced.extend([m for m in match if m])
                            else:
                                referenced.append(match)

            if referenced:
                hints[col] = list(set(referenced))

        return hints

    def _extract_question_entities(
        self, question: str, files: List[FileInput]
    ) -> Set[str]:
        """
        Extract relevant entities from the user's analysis question.

        Identifies table/file names and domain concepts that should be prioritized.
        """
        entities = set()
        question_lower = question.lower()

        # Extract file aliases mentioned in question
        for f in files:
            alias = (f.alias or "").lower()
            if alias and alias in question_lower:
                entities.add(alias)
            # Also check filename without extension
            filename = Path(f.file_path).stem.lower()
            if filename in question_lower:
                entities.add(filename)

        # Common data analysis entities that suggest relationships
        relationship_words = [
            "customer",
            "order",
            "product",
            "transaction",
            "user",
            "account",
            "purchase",
            "sale",
            "payment",
            "invoice",
            "item",
            "category",
            "employee",
            "department",
            "region",
            "store",
            "supplier",
        ]

        for word in relationship_words:
            if word in question_lower:
                entities.add(word)

        return entities

    def _evaluate_column_pair(
        self,
        left_name: str,
        left_df: pd.DataFrame,
        left_col: str,
        right_name: str,
        right_df: pd.DataFrame,
        right_col: str,
        dataset_info: Optional[Dict[str, str]] = None,
        relationship_hints: Optional[Dict[str, List[str]]] = None,
        question_entities: Optional[Set[str]] = None,
    ) -> Optional[JoinCandidate]:
        """
        Evaluate a single pair of columns for join potential.

        Enhanced in v1.9 to use dataset_info context and user question relevance.
        """

        # 1. Name Similarity
        name_score = SequenceMatcher(None, left_col.lower(), right_col.lower()).ratio()

        # 2. Type Compatibility
        left_dtype = str(left_df[left_col].dtype)
        right_dtype = str(right_df[right_col].dtype)

        type_score = 0.0
        if left_dtype == right_dtype:
            type_score = 1.0
        elif pd.api.types.is_numeric_dtype(
            left_df[left_col]
        ) and pd.api.types.is_numeric_dtype(right_df[right_col]):
            type_score = 0.8
        elif pd.api.types.is_string_dtype(
            left_df[left_col]
        ) and pd.api.types.is_string_dtype(right_df[right_col]):
            type_score = 0.8

        if type_score < 0.5:
            return None  # Incompatible types

        # 3. Value Overlap
        # Sample if too large
        SAMPLE_SIZE = 10000
        left_vals = set(left_df[left_col].dropna().unique()[:SAMPLE_SIZE])
        right_vals = set(right_df[right_col].dropna().unique()[:SAMPLE_SIZE])

        if not left_vals or not right_vals:
            return None

        intersection = left_vals.intersection(right_vals)
        union = left_vals.union(right_vals)
        overlap_score = len(intersection) / len(union) if union else 0.0

        # 4. Cardinality / Relationship Type
        l_unique = len(left_vals)
        r_unique = len(right_vals)
        l_count = len(left_df)
        r_count = len(right_df)

        is_l_unique = l_unique == l_count or l_unique == len(left_df[left_col].dropna())
        is_r_unique = r_unique == r_count or r_unique == len(
            right_df[right_col].dropna()
        )

        cardinality = "M:N"
        if is_l_unique and is_r_unique:
            cardinality = "1:1"
        elif is_l_unique:
            cardinality = "1:N"
        elif is_r_unique:
            cardinality = "N:1"

        # Cardinality boost: 1:1 and 1:N are better than M:N
        cardinality_score = 1.0 if cardinality != "M:N" else 0.5

        # 5. Dataset Info / Semantic Context Score (NEW in v1.9)
        context_score = 0.0

        # Check if dataset info contains relationship hints for these columns
        if relationship_hints:
            # Check left column hints
            if left_col in relationship_hints:
                refs = relationship_hints[left_col]
                # Check if right_col or right table is referenced
                if any(
                    ref in right_col.lower() or ref in right_name.lower()
                    for ref in refs
                ):
                    context_score = 1.0  # Strong explicit relationship

            # Check right column hints
            if right_col in relationship_hints:
                refs = relationship_hints[right_col]
                if any(
                    ref in left_col.lower() or ref in left_name.lower() for ref in refs
                ):
                    context_score = 1.0

        # 6. Question Relevance Score (NEW in v1.9)
        question_relevance = 0.0
        if question_entities:
            # Check if file names or column names match entities from user question
            relevant_terms = [
                left_name.lower(),
                right_name.lower(),
                left_col.lower(),
                right_col.lower(),
            ]
            matching_entities = sum(
                1
                for entity in question_entities
                if any(entity in term for term in relevant_terms)
            )
            if matching_entities > 0:
                question_relevance = min(1.0, matching_entities * 0.3)  # Up to 1.0

        # Weighted Score (Updated for v1.9)
        # Name 25%, Type 10%, Overlap 30%, Cardinality 15%, Context 10%, Question 10%
        final_score = (
            (name_score * 0.25)
            + (type_score * 0.10)
            + (overlap_score * 0.30)
            + (cardinality_score * 0.15)
            + (context_score * 0.10)
            + (question_relevance * 0.10)
        )

        return JoinCandidate(
            left_file=left_name,
            right_file=right_name,
            left_column=left_col,
            right_column=right_col,
            name_similarity=name_score,
            type_compatibility=type_score,
            value_overlap=overlap_score,
            cardinality_ratio=cardinality,
            confidence_score=final_score,
            recommended_join_type=JoinType.LEFT,  # Default
        )

    def execute_joins(
        self,
        dataframes: Dict[str, pd.DataFrame],
        join_plan: List[JoinCandidate],
        output_path: str,
        files: List[FileInput] | None = None,
    ) -> MergedDataset:
        """
        Execute join plan and return merged dataset.
        """
        if not join_plan:
            raise ValueError("No joins to execute")

        # Create Alias -> Hash mapping if files provided
        # Fallback to direct lookup if no mapping
        alias_to_hash = {}
        if files:
            for f in files:
                key = f.alias or f.file_hash
                alias_to_hash[key] = f.file_hash

        def get_df_key(identifier: str) -> str:
            if identifier in dataframes:
                return identifier
            if identifier in alias_to_hash:
                return alias_to_hash[identifier]
            raise KeyError(f"Could not find dataframe for identifier: {identifier}")

        first_join = join_plan[0]

        left_key = get_df_key(first_join.left_file)
        merged = dataframes[left_key].copy()
        provenance = [first_join.left_file]
        warnings = []
        executed_joins = []

        processed_files = {
            first_join.left_file
        }  # Track by candidate identifier (Alias or Hash)
        # Note: processed_files should track the Identifier used in JoinCandidate

        for candidate in join_plan:
            # Determine which side is already in merged
            is_left_in = candidate.left_file in processed_files
            is_right_in = candidate.right_file in processed_files

            if is_left_in and is_right_in:
                continue  # Already joined

            if not is_left_in and not is_right_in:
                # Disconnected component
                # For robust implementation, we should find a connected edge
                # But skipping strict graph logical sort for now
                continue

            # Determine join direction
            if is_left_in:
                # candidate.left_file is in. We need to join candidate.right_file
                right_key = candidate.right_file
                left_on = candidate.left_column
                right_on = candidate.right_column

                df_key = get_df_key(right_key)
                df_to_join = dataframes[df_key]

                processed_files.add(right_key)
                join_type = candidate.recommended_join_type
                suffix_key = right_key
            else:
                # right is in, joining left
                right_key = candidate.left_file  # This is the NEW file
                left_on = (
                    candidate.right_column
                )  # Existing df col (from Candidate.right)
                right_on = candidate.left_column  # New df col (from Candidate.left)

                df_key = get_df_key(right_key)
                df_to_join = dataframes[df_key]

                processed_files.add(right_key)
                join_type = candidate.recommended_join_type
                suffix_key = right_key

            # Execute Join
            pre_rows = len(merged)

            merged = pd.merge(
                merged,
                df_to_join,
                left_on=left_on,
                right_on=right_on,
                how=join_type.value if hasattr(join_type, "value") else join_type,  # type: ignore
                suffixes=("", f"_{suffix_key}"),
            )

            post_rows = len(merged)

            if post_rows > pre_rows * 5:
                warnings.append(f"Row count explosion: {pre_rows} -> {post_rows}")

            provenance.append(right_key)
            executed_joins.append(candidate)

        # Save merged
        merged.to_csv(output_path, index=False)

        # Calculate hash
        with open(output_path, "rb") as out_file:
            file_hash = hashlib.sha256(out_file.read()).hexdigest()

        return MergedDataset(
            merged_df_path=output_path,
            merged_hash=file_hash,
            source_files=provenance,
            join_plan_executed=executed_joins,
            final_row_count=len(merged),
            final_column_count=len(merged.columns),
            rows_dropped=0,  # Simplified
            rows_added=0,
            warnings=warnings,
        )
