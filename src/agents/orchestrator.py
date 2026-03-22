"""
Orchestrator Agent - Central coordinator and final assembler.

This agent acts as the 'CPU' of the system. It handles:
1. Initializing the workflow (inputs, state).
2. Managing the heavy lifting of data passing between phases.
3. Enforcing high-level constraints (like checking locks).
4. Physical assembly of the final Jupyter Notebook artifact.
"""

import traceback
from typing import Any, Dict, Optional

import pandas as pd

from src.agents.base import BaseAgent
from src.models.state import AnalysisState, Phase, ProfileLock
from src.models.handoffs import (
    UserIntent,
    OrchestratorToProfilerHandoff,
    PipelineMode,
    CacheStatus,
    ExtendedMetadata,
)
from src.models.multi_file import MultiFileInput
from src.services.join_detector import JoinDetector
from src.services.mode_detector import ModeDetector
from src.services.notebook_assembler import NotebookAssembler
from src.services.data_manager import DataManager
from src.utils.cache_manager import CacheManager
from src.utils.logger import get_logger

# Initialize logger
logger = get_logger()


class OrchestratorAgent(BaseAgent):
    """
    Orchestrator Agent - Central coordinator.

    Responsibilities:
    - Parse and validate CSV input
    - Capture user intent
    - Manage phase transitions
    - Enforce Profile Lock
    - Assemble final notebook
    """

    def __init__(self, provider: Optional[str] = None, model: Optional[str] = None):
        super().__init__(
            name="Orchestrator",
            phase=Phase.PHASE_1,  # Starts in Phase 1
            system_prompt="You are an Orchestrator Agent coordinating the data analysis workflow.",
            provider=provider,
            model=model,
        )
        # Services are lazily initialized on first access
        self._cache_manager = None
        self._join_detector = None
        self._mode_detector = None
        self._notebook_assembler = None
        self._data_manager = None

    @property
    def cache_manager(self):
        if self._cache_manager is None:
            self._cache_manager = CacheManager()
        return self._cache_manager

    @property
    def join_detector(self):
        if self._join_detector is None:
            self._join_detector = JoinDetector()
        return self._join_detector

    @property
    def mode_detector(self):
        if self._mode_detector is None:
            self._mode_detector = ModeDetector()
        return self._mode_detector

    @property
    def notebook_assembler(self):
        if self._notebook_assembler is None:
            self._notebook_assembler = NotebookAssembler()
        return self._notebook_assembler

    @property
    def data_manager(self):
        if self._data_manager is None:
            self._data_manager = DataManager()
        return self._data_manager

    def process(self, state: AnalysisState, **kwargs) -> Dict[str, Any]:
        """
        Process request based on the specific action required.

        The Orchestrator is a multi-modal agent; it performs different tasks
        depending on where we are in the graph execution.

        Args:
            state: Current analysis state.
            **kwargs: Must contain 'action' key (e.g., 'initialize', 'assemble_notebook').

        Returns:
            Dictionary of state updates.
        """
        action = kwargs.get("action", "initialize")

        if action == "initialize":
            return self._initialize(
                state=state,
                csv_path=str(kwargs.get("csv_path", "")),
                user_intent=kwargs.get("user_intent"),
                data_dictionary_path=kwargs.get("data_dictionary_path"),
                mode=kwargs.get("mode"),
                use_cache=bool(kwargs.get("use_cache", False)),
                no_cache=bool(kwargs.get("no_cache", False)),
            )
        elif action == "phase1_handoff":
            return self._create_phase1_handoff(state)
        elif action == "transition_to_phase2":
            return self._transition_to_phase2(state)
        elif action == "rollback_phase2":
            return self._rollback_phase2(state)
        elif action == "assemble_notebook":
            return self.notebook_assembler.assemble_notebook(
                state, kwargs.get("assembly_handoff")
            )
        elif action == "restore_cache":
            return self._restore_cache(state)
        elif action == "save_cache":
            return self._save_cache(state)
        else:
            return {"error": f"Unknown action: {action}"}

    def _initialize(
        self,
        state: AnalysisState,
        csv_path: str,
        user_intent: Optional[Dict] = None,
        data_dictionary_path: Optional[str] = None,
        mode: Optional[str] = None,
        use_cache: bool = False,
        no_cache: bool = False,
    ) -> Dict[str, Any]:
        """
        Initialize the analysis workflow.

        Loads the CSV, verifies its existence, and populates the initial state.
        Determines Pipeline Mode and checks for cached profiles.
        """
        # Validate CSV can be loaded
        try:
            self.data_manager.load_data(csv_path)
        except (pd.errors.EmptyDataError, pd.errors.ParserError) as e:
            logger.error(f"Data loading error: {e}")
            return {"error": f"Invalid CSV/Excel file: {str(e)}", "confidence": 0.0}
        except FileNotFoundError as e:
            logger.error(f"File not found: {e}")
            return {"error": f"File not found: {str(e)}", "confidence": 0.0}
        except Exception as e:
            logger.error(
                f"Unexpected error loading data: {e}\n{traceback.format_exc()}"
            )
            return {"error": f"Failed to load data: {str(e)}", "confidence": 0.0}

        # Parse Data Dictionary if provided
        data_dictionary = {}
        if data_dictionary_path:
            try:
                from src.utils.file_utils import load_csv_robust

                dict_df = load_csv_robust(data_dictionary_path)
                # Expect 'Field' and 'Description', robust to case
                cols = {c.lower(): c for c in dict_df.columns}
                if "field" in cols and "description" in cols:
                    field_col = cols["field"]
                    desc_col = cols["description"]
                    data_dictionary = dict(zip(dict_df[field_col], dict_df[desc_col]))
            except Exception as e:
                logger.warning(f"Failed to load Data Dictionary: {e}")

        # Extract intent details
        target = user_intent.get("target_column") if user_intent else None
        question = user_intent.get("analysis_question") if user_intent else None

        # Determine Pipeline Mode using Service
        pipeline_mode, detection_method = self.mode_detector.determine_mode(
            mode_arg=mode, target_column=target, user_question=question
        )

        # Log mode detection
        logger.mode_detected(pipeline_mode.value, detection_method)

        # Multi-File Handling (v1.8.0)
        multi_file_input = None
        merged_dataset = None
        join_report = None

        # Check if multi-file input provided in intent
        if user_intent and user_intent.get("multi_file_input"):
            try:
                # Load multi-file input
                multi_file_input = MultiFileInput(**user_intent["multi_file_input"])
                logger.info(
                    f"Multi-file input detected: {len(multi_file_input.files)} files."
                )
                # We defer actual merging to the DataMergerAgent node in the graph.

            except Exception as e:
                logger.error(f"Multi-file input parsing failed: {e}")
                logger.error(traceback.format_exc())
                # Fallback to single file logic (original csv_path)

        # Check Cache
        cache_status = CacheStatus.NOT_FOUND
        cached_profile = None
        using_cache = False

        if not no_cache:
            if multi_file_input:
                # Use combined hash of INPUTS because merged file changes content/hash slightly?
                # Or just to utilize the combined_hash feature explicitly.
                # Note: We need the ORIGINAL input paths.
                # multi_file_input object has them.
                input_paths = [f.file_path for f in multi_file_input.files]
                cache_result = self.cache_manager.check_multi_file_cache(input_paths)
            else:
                cache_result = self.cache_manager.check_cache(csv_path)

            cache_status = cache_result.status

            # Log cache check result
            logger.cache_check(csv_path, cache_status.value)

            if cache_result.status == CacheStatus.VALID and use_cache:
                cached_profile = cache_result.cache
                using_cache = True
                from src.utils.logger import LogEvents

                logger.log_event(
                    LogEvents.UPGRADE_FROM_CACHE,
                    f"Using cached profile for {pipeline_mode.value} analysis",
                    level="info",
                )

        # Normalize UserIntent into Pydantic model
        intent = UserIntent(
            csv_path=csv_path,
            analysis_question=question,
            target_column=target,
            title=user_intent.get("title") if user_intent else None,
            analysis_type_hint=user_intent.get("analysis_type")
            if user_intent
            else None,
            exclude_columns=user_intent.get("exclude_columns", [])
            if user_intent
            else [],
            data_dictionary=data_dictionary,
            multi_file_input=multi_file_input,
        )

        # State updates
        # If using cache, we might prepopulate lock?
        # Graph logic handles the skipping. We just set flags here.

        return {
            "csv_path": csv_path,
            "csv_data": None,  # Performance: Do not serialize full DF to state. Use path.
            "user_intent": intent,
            "current_phase": Phase.PHASE_1,
            "pipeline_mode": pipeline_mode,
            "cache_status": cache_status,
            "using_cached_profile": using_cache,
            "cache": cached_profile,  # Store the full cache object for retrieval
            "phase1_iteration": 0,
            "confidence": 1.0,
            "multi_file_input": multi_file_input,
            "merged_dataset": merged_dataset,
            "join_report": join_report,
        }

    def _create_phase1_handoff(self, state: AnalysisState) -> Dict[str, Any]:
        """
        Create the handoff package for the Data Profiler.

        Prepares the data required for Phase 1 to begin:
        - A row sample (head)
        - Column names and counts
        - User's goals
        """
        # Use DataManager to load data
        try:
            df = self.data_manager.load_data(state.csv_path)
        except Exception:
            # Fallback if load fails here (shouldn't if state is valid)
            df = self.data_manager.load_data(state.csv_path)

        # Calculate metadata using DataManager helpers
        meta = self.data_manager.get_basic_metadata(df)
        unique_counts = self.data_manager.get_unique_counts(df)
        sample_df = self.data_manager.get_sample(df)
        preview_df = self.data_manager.get_head(df)

        intent = state.user_intent or UserIntent(csv_path=state.csv_path)

        handoff = OrchestratorToProfilerHandoff(
            csv_path=state.csv_path,
            csv_preview=preview_df.to_dict(),
            row_count=meta["row_count"],
            column_names=meta["columns"],
            user_intent=intent,
            iteration=state.phase1_iteration + 1,
            column_missing_values=meta["missing_values"],
            column_initial_types=meta["types"],
            duplicate_row_count=meta["duplicates"],
            column_unique_counts=unique_counts,
            csv_sample=sample_df.to_dict(),
            data_dictionary=intent.data_dictionary or {},
            multi_file_input=intent.multi_file_input,
            merged_dataset=state.merged_dataset,
            join_report=state.join_report,
            extended_metadata=ExtendedMetadata(
                row_count=meta["row_count"],
                column_count=meta["column_count"],
                column_names=meta["columns"],
                nan_counts=meta["missing_values"],
                initial_dtypes=meta["types"],
                duplicate_count=meta["duplicates"],
                unique_counts=unique_counts,
                sample_data=preview_df.to_dict(orient="list"),
                memory_usage_bytes=meta["memory_usage"],
            ),
        )

        return {
            "profiler_handoff": handoff,
            "phase1_iteration": 0,  # Reset to 0, will be incremented by nodes logic
            "confidence": 1.0,
        }

    def _transition_to_phase2(self, state: AnalysisState) -> Dict[str, Any]:
        """
        Execute transition logic from Phase 1 to Phase 2.

        Verifies that Phase 1 was completed successfully (Profile Locked)
        before allowing movement to Phase 2.
        """
        if not state.profile_lock.is_locked():
            return {
                "error": "Cannot transition to Phase 2: Profile not locked",
                "confidence": 0.0,
            }

        return {
            "current_phase": Phase.PHASE_2,
            "phase2_iteration": 0,
            "confidence": 1.0,
        }

    def _rollback_phase2(self, state: AnalysisState) -> Dict[str, Any]:
        """
        Execute Rollback logic for Phase 2.

        If immediate improvements degrade quality, revert to the last best known
        strategy and code.
        """
        updates: Dict[str, Any] = {}

        if state.phase2_best_strategy:
            # Restore best strategy
            strategy_outputs = list(state.strategy_outputs)
            strategy_outputs.append(state.phase2_best_strategy)
            updates["strategy_outputs"] = strategy_outputs

        if state.phase2_best_code:
            # Restore best code
            code_outputs = list(state.analysis_code_outputs)
            code_outputs.append(state.phase2_best_code)
            updates["analysis_code_outputs"] = code_outputs

        return updates

    def _restore_cache(self, state: AnalysisState) -> Dict[str, Any]:
        """
        Restore a previously validated profile from the cache.

        This action is triggered when the Orchestrator has detected a valid cache
        and the user (or config) has opted to use it. It bypasses Phase 1 entirely,
        hydrating the state with the locked profile and moving directly to either
        Phase 2 (Predictive) or Assembly (Exploratory).

        Args:
            state: Current analysis state.

        Returns:
            State updates including the hydrated profile lock and quality trajectory.
        """
        # Reconstruct ProfileLock directly from the cached dictionary
        if not state.cache:
            raise ValueError("No cache found")
        profile_lock = ProfileLock(**state.cache.profile_lock)

        return {
            "profile_lock": profile_lock,
            "phase1_quality_trajectory": [state.cache.phase1_quality_score],
            "current_phase": Phase.PHASE_1,
            "confidence": 1.0,
        }

    def _save_cache(self, state: AnalysisState) -> Dict[str, Any]:
        """
        Persist the currently locked Phase 1 profile to the disk cache.

        This is typically called immediately after the Profile Validator grants a lock.
        It calculates the CSV hash, serializes the profile metadata, and stores it
        in the user's home directory (`~/.multi_agent_cache`).

        Args:
            state: Current analysis state containing the valid ProfileLock.

        Returns:
            Empty dict (side-effect only), or logs error if lock is invalid.
        """
        if not state.profile_lock or not state.profile_lock.is_locked():
            return {}

        if state.multi_file_input:
            input_paths = [f.file_path for f in state.multi_file_input.files]
            csv_hash = self.cache_manager.compute_combined_hash(input_paths)
        else:
            csv_hash = self.cache_manager.get_csv_hash(state.csv_path)

        # Determine latest quality score from trajectory
        score = (
            state.phase1_quality_trajectory[-1]
            if state.phase1_quality_trajectory
            else 0.0
        )

        self.cache_manager.save_cache(
            csv_path=state.csv_path,
            csv_hash=csv_hash,
            profile_lock=state.profile_lock,
            profile_cells=state.profile_lock.profile_cells,
            profile_handoff=state.profile_lock.profile_handoff,
            phase1_quality_score=score,
            pipeline_mode=state.pipeline_mode,
            user_intent=state.user_intent,
        )
        return {}
