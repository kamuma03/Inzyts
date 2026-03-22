from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
import traceback

from src.agents.base import BaseAgent
from src.models.state import AnalysisState, Phase
from src.models.multi_file import JoinExecutionReport
from src.services.join_detector import JoinDetector
from src.services.data_manager import DataManager
from src.utils.logger import get_logger
from src.config import settings
from src.utils.path_validator import ensure_dir

logger = get_logger()


class DataMergerAgent(BaseAgent):
    """
    Data Merger Agent.

    Responsible for:
    1. Detecting potential joins between multiple input files.
    2. Executing joins based on auto-detection or user explicit commands.
    3. Creating a unified MergedDataset for downstream analysis.
    """

    def __init__(self, provider: Optional[str] = None, model: Optional[str] = None):
        super().__init__(
            name="DataMerger",
            phase=Phase.PHASE_1,
            system_prompt="You are a Data Merger Agent responsible for combining multiple datasets into a single analytical dataset.",
            provider=provider,
            model=model,
        )
        self._join_detector = None
        self._data_manager = None

    @property
    def join_detector(self):
        if self._join_detector is None:
            self._join_detector = JoinDetector()
        return self._join_detector

    @property
    def data_manager(self):
        if self._data_manager is None:
            self._data_manager = DataManager()
        return self._data_manager

    def process(self, state: AnalysisState, **kwargs) -> Dict[str, Any]:
        """
        Execute the data merging process.

        Args:
            state: Current analysis state containing multi_file_input.

        Returns:
            State updates with merged_dataset and join_report.
        """
        logger.info("Starting Data Merger Agent...")

        user_intent = state.user_intent
        multi_file_input = user_intent.multi_file_input if user_intent else None

        if not multi_file_input or len(multi_file_input.files) < 2:
            logger.warning("DataMerger called but no valid multi-file input found.")
            return {}

        try:
            logger.info(
                f"Processing {len(multi_file_input.files)} files for merging..."
            )

            # 1. Load all dataframes
            dfs = {}
            file_inputs = []

            for f in multi_file_input.files:
                try:
                    # Resolve path for local dev/docker setups
                    file_path = f.file_path
                    if not Path(file_path).exists():
                        upload_path = Path("data/uploads") / Path(file_path).name
                        if upload_path.exists():
                            file_path = str(upload_path)
                            
                    # Use file hash as key for join detector logic
                    # Using data_manager which handles caching/loading
                    d = self.data_manager.load_data(file_path)
                    
                    # Update the object with the resolved path for downstream
                    f.file_path = file_path
                    
                    dfs[f.file_hash] = d
                    file_inputs.append(f)
                except Exception as e:
                    logger.error(f"Failed to load {f.file_path}: {e}")
                    # Fail hard or partial? For now, we need all files to join as requested.
                    return {
                        "error": f"Failed to load file {f.file_path} for merging: {e}"
                    }

            if len(dfs) < 2:
                return {"error": "Insufficient valid files loaded for merging."}

            # 2. Detect Joins
            # Pass data dictionary (if any) and user question for context-aware detection
            candidates = self.join_detector.detect_join_candidates(
                file_inputs,
                dfs,
                dataset_info=user_intent.data_dictionary if user_intent else None,
                user_question=user_intent.analysis_question if user_intent else None,
            )

            # 3. Execute Joins
            # Simplified for v1: Auto-execute best chain
            output_dir = Path(settings.output_dir) / "merged"
            ensure_dir(output_dir)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            merged_path = output_dir / f"merged_{timestamp}.csv"

            merged_ds = self.join_detector.execute_joins(
                dfs, candidates, str(merged_path), files=file_inputs
            )

            # 4. Create Report
            join_report = JoinExecutionReport(
                files_analyzed=len(file_inputs),
                candidate_joins_found=len(candidates),
                candidates=candidates,
                joins_executed=len(merged_ds.join_plan_executed),
                joins_skipped=[],
                merged_dataset=merged_ds,
                fallback_mode=False,
            )

            logger.info(f"Merging complete. Output: {merged_path}")

            # Return state updates
            # We update:
            # - merged_dataset
            # - join_report
            # - csv_path (to point to the NEW merged file for downstream agents)
            # - user_intent (maybe? No, intent remains raw intent. State has the effective path)

            # NOTE: Downstream agents (Profiler) usually look at state.csv_path.
            # We should update state.csv_path to the merged file so they process the result.

            return {
                "merged_dataset": merged_ds,
                "join_report": join_report,
                "csv_path": str(merged_path),
            }

        except Exception as e:
            logger.error(f"Data merging failed: {e}")
            logger.error(traceback.format_exc())
            return {"error": f"Data merging failed: {str(e)}"}
