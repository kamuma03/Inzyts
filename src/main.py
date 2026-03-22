"""
Multi-Agent Data Analysis System - Entry Point.

Usage:
    python -m src.main --csv path/to/data.csv [--target column] [--type classification]
"""

import argparse
import time
import traceback
import os
from pathlib import Path
from typing import Optional, Callable

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from src.models.state import AnalysisState, Phase
from src.models.handoffs import UserIntent, AnalysisType, PipelineMode
from src.models.multi_file import MultiFileInput, FileInput, FileType
from src.workflow.graph import get_graph
from src.config import settings
from src.utils.cache_manager import CacheManager, CacheStatus


from src.utils.logger import get_logger

# Initialize logger (this will attach to root if configured correctly or we use it directly)
# Since this runs inside the worker process where engine.py has configured the root logger,
# using get_logger() (which returns "Inzyts" logger) should propagate to root.
logger = get_logger().logger  # Access underlying standard logger

console = Console()


def parse_args():
    """
    Parse command line arguments for the Data Analysis Agent.

    Returns:
        argparse.Namespace: Parsed arguments containing:
            - csv: Path to input file
            - target: Target column (optional)
            - type: Analysis type hint (optional)
            - question: Specific user question (optional)
            - exclude: List of columns to ignore
            - verbose: Boolean flag for logging
    """
    parser = argparse.ArgumentParser(description="Multi-Agent Data Analysis System")
    parser.add_argument(
        "--csv",
        "-c",
        required=False,
        help="Path to CSV file to analyze (Required unless --files or --db-uri is used)",
    )
    parser.add_argument(
        "--db-uri",
        help="Database connection URI for SQL extraction",
    )
    parser.add_argument(
        "--db-query",
        help="SQL query to execute for database extraction",
    )
    parser.add_argument(
        "--files", "-f", nargs="+", help="List of files to analyze (merged)"
    )
    parser.add_argument("--target", "-t", help="Target column for supervised learning")
    parser.add_argument(
        "--type",
        choices=["classification", "regression", "clustering", "exploratory"],
        help="Analysis type hint",
    )
    parser.add_argument("--question", "-q", help="Analysis question to answer")
    parser.add_argument("--title", help="Title of the analysis")
    parser.add_argument(
        "--exclude", nargs="*", default=[], help="Columns to exclude from analysis"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose output"
    )
    parser.add_argument(
        "--data-dictionary",
        "-d",
        help="Path to Data Dictionary CSV (Field, Description)",
    )

    # v1.5.0 Arguments
    parser.add_argument(
        "--mode",
        choices=["exploratory", "predictive"],
        help="Force execution mode (Exploratory vs Predictive)",
    )
    parser.add_argument(
        "--use-cache",
        action="store_true",
        help="Force use of profile cache if available",
    )
    parser.add_argument("--no-cache", action="store_true", help="Disable all caching")
    parser.add_argument(
        "--clear-cache",
        action="store_true",
        help="Clear all expired caches before running",
    )
    return parser.parse_args()


def resolve_file_path(path_str: str) -> Path:
    """
    Attempt to find the file in common locations if direct path fails.
    Avoids aggressive full-disk recursive globbing.
    """
    path = Path(path_str).resolve()

    # Docker Path Mapping Fix:
    # When running inside the container the host-side DATASETS_DIR is mounted
    # at /data/datasets (Unix) or the platform equivalent.  Re-map so the
    # worker finds the file at the container path.
    datasets_host_dir = settings.datasets_dir
    container_datasets = Path("/data/datasets")
    if datasets_host_dir:
        clean_host = Path(datasets_host_dir).resolve()
        clean_input = Path(path_str).resolve()

        try:
            relative = clean_input.relative_to(clean_host)
            remapped_path = (container_datasets / relative).resolve()
            # Ensure it actually resolves under the container datasets dir
            if remapped_path.is_relative_to(container_datasets) and remapped_path.exists():
                logger.info(
                    f"Remapped host path '{path_str}' to container path '{remapped_path}'"
                )
                return remapped_path
        except ValueError:
            pass  # clean_input is not under clean_host — skip remapping

    if path.exists():
        return path

    # If path doesn't exist, try searching for the filename in common dataset directories
    # WITHOUT deep recursion if the root is too high level (like ~)
    filename = Path(path_str).name

    for p in settings.file_search_paths:
        root = Path(p).expanduser().resolve()

        if not root.exists():
            continue

        # Just check immediate children or 1 level deep to avoid blocking hangs
        # We assume datasets are somewhat organized, not buried 15 folders deep in ~
        try:
            # Check root
            direct_match = root / filename
            if direct_match.exists():
                return direct_match

            # Check 1 level deep directories
            for subdir in root.iterdir():
                if subdir.is_dir():
                    sub_match = subdir / filename
                    if sub_match.exists():
                        return sub_match
        except PermissionError:
            continue

    return path


def run_analysis(
    csv_path: Optional[str] = None,
    target_column: str | None = None,
    analysis_type: str | None = None,
    analysis_question: str | None = None,
    title: str | None = None,
    exclude_columns: list | None = None,
    data_dictionary_path: str | None = None,
    mode: str | None = None,
    use_cache: bool = False,
    no_cache: bool = False,
    verbose: bool = True,
    interactive: bool = True,
    cancellation_check: Callable[[], bool]
    | None = None,  # Function returning True if cancelled
    multi_file_input: Optional[MultiFileInput] = None,
    db_uri: Optional[str] = None,
    api_url: Optional[str] = None,
    api_headers: Optional[dict] = None,
    api_auth: Optional[dict] = None,
    json_path: Optional[str] = None,
) -> Optional[AnalysisState]:
    """
    Run the complete data analysis workflow.

    This function initializes the analysis state and executes the LangGraph workflow.
    It handles:
    1. Input validation
    2. User Intent creation
    3. State initialization
    4. Graph execution and monitoring
    5. Result reporting

    Args:
        csv_path: Absolute or relative path to the CSV file.
        target_column: Name of the target variable for predictive modeling.
        analysis_type: User's hint about the type of analysis (e.g., 'classification').
        analysis_question: Specific question the user wants answered.
        exclude_columns: List of column names to ignore.
        verbose: If True, prints detailed step-by-step logs.

    Returns:
        Final AnalysisState object containing results and notebook path,
        or None if execution failed.
    """
    # Validate CSV exists (skip when using autonomous SQL agent — no CSV yet)
    resolved_csv_path = resolve_file_path(csv_path) if csv_path else Path("")
    if csv_path and not resolved_csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {resolved_csv_path}")

    msg = (
        f"Multi-Agent Data Analysis System ({settings.app_version})\n"
        f"CSV: {resolved_csv_path.name}\n"
        f"Target: {target_column or 'Auto-detect'}\n"
        f"Type: {analysis_type or 'Auto-detect'}\n"
        f"Mode: {mode or 'Auto-detect'}"
    )
    logger.info(msg)
    console.print(Panel(msg, title="Starting Analysis"))

    # Cache Management Logic
    cache_manager = CacheManager()
    preloaded_cache = None
    using_cache_decision = use_cache
    pipeline_mode_decision = None

    # Determine Mode Hint
    if mode:
        pipeline_mode_decision = PipelineMode(mode.lower())

    if not no_cache:
        # Check if we have a valid cache
        check = cache_manager.check_cache(str(resolved_csv_path))

        if check.status == CacheStatus.VALID and check.cache:
            if use_cache:
                # Force use
                msg = f"Using cached profile (expires in {check.cache.days_until_expiry()} days)"
                logger.info(msg)
                console.print(f"[green]{msg}[/green]")
                preloaded_cache = check.cache
                using_cache_decision = True
            else:
                # Prompt user if interactive
                should_use = "n"  # default: skip cache; only use if user explicitly confirms
                if interactive:
                    try:
                        should_use = (
                            input(
                                f"\n[?] Found valid cached profile ({check.cache.days_until_expiry()} days left). Use it? [Y/n] "
                            )
                            .strip()
                            .lower()
                        )
                    except EOFError:
                        should_use = "n"

                if should_use in ["", "y", "yes"] and interactive:
                    logger.info("Using cached profile.")
                    console.print("[green]Using cached profile.[/green]")
                    preloaded_cache = check.cache
                    using_cache_decision = True
                else:
                    logger.info("Ignoring cache, running fresh profile.")
                    console.print(
                        "[yellow]Ignoring cache (Interactive=False or selected No), running fresh profile.[/yellow]"
                    )

    # If using cache, we allow skipping Phase 1.
    # The Orchestrator and Graph handle this if `using_cached_profile=True` in initial state.

    # Create user intent
    analysis_type_enum = None
    if analysis_type:
        analysis_type_enum = AnalysisType(analysis_type)

    # Parse Data Dictionary if provided
    data_dictionary = {}
    if data_dictionary_path:
        dictionary_path = resolve_file_path(data_dictionary_path)
        if dictionary_path.exists():
            try:
                from src.services.dictionary_manager import DictionaryParser

                parsed_dict = DictionaryParser.parse(str(dictionary_path))

                if parsed_dict and parsed_dict.entries:
                    # Convert to Dict[str, str] format expected by UserIntent
                    # Format: {column_name: description}
                    for entry in parsed_dict.entries:
                        if entry.column_name and entry.description:
                            data_dictionary[entry.column_name.lower()] = (
                                entry.description
                            )

                    if verbose:
                        logger.info(
                            f"Loaded Data Dictionary with {len(data_dictionary)} definitions"
                        )
                        console.print(
                            f"[green]Loaded Data Dictionary with {len(data_dictionary)} definitions[/green]"
                        )
                else:
                    console.print(
                        f"[yellow]Warning: Data Dictionary could not be parsed or was empty: {dictionary_path}[/yellow]"
                    )

            except Exception as e:
                console.print(f"[red]Error loading Data Dictionary: {e}[/red]")
                if verbose:
                    console.print(traceback.format_exc())
        else:
            logger.warning(f"Data Dictionary file not found: {data_dictionary_path}")
            console.print(
                f"[yellow]Warning: Data Dictionary file not found: {data_dictionary_path}[/yellow]"
            )

    user_intent = UserIntent(
        csv_path=str(resolved_csv_path) if csv_path else "",
        analysis_question=analysis_question,
        target_column=target_column,
        title=title,
        analysis_type_hint=analysis_type_enum,
        exclude_columns=exclude_columns or [],
        data_dictionary=data_dictionary,
        multi_file_input=multi_file_input,
        db_uri=db_uri,
        api_url=api_url,
        api_headers=api_headers,
        api_auth=api_auth,
        json_path=json_path,
    )

    # Create initial state
    initial_state = AnalysisState(
        csv_path=str(resolved_csv_path) if (csv_path and resolved_csv_path.exists()) else "",
        user_intent=user_intent,
        current_phase=Phase.PHASE_1,
        pipeline_mode=pipeline_mode_decision,
        using_cached_profile=using_cache_decision,
        cache=preloaded_cache,  # Pre-inject cache if loaded
    )

    # Run workflow
    start_time = time.time()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Running analysis workflow...", total=None)

        # Execute graph. LangGraph's stream(mode="values") yields full state dicts
        # after each node, so final_state is always a dict after the loop.
        current_state_dict: dict = initial_state.model_dump()

        # Use stream_mode="values" to get the fully accumulated state at each step.
        # Store the generator in a variable so we can close it explicitly on exception
        # to avoid leaving LangGraph in an inconsistent state with dangling coroutines.
        graph = get_graph()
        graph_stream = graph.stream(initial_state, stream_mode="values")

        try:
            # We iterate over the stream of full state snapshots
            for event in graph_stream:
                # With stream_mode="values", event is the full state dict after each node.
                output_state = event
                current_state_dict = output_state

                # Check for external cancellation
                if cancellation_check and cancellation_check():
                    console.print("[bold red]Analysis Cancelled by User.[/bold red]")
                    if verbose:
                        console.print("[dim]Stopping graph execution...[/dim]")
                    return None

                # User logging: we can try to diff to see what changed, or just log the phase
                if verbose:
                    # Heuristic to detect phase change or step completion
                    # For now, just print current phase if available
                    phase = output_state.get("current_phase")
                    # node_name isn't explicitly yielded in 'values' mode, checking last step is harder
                    # but state checking is reliable.

                if "current_phase" in output_state:
                    phase = output_state["current_phase"]
                    if phase == Phase.PHASE_2:
                        progress.update(
                            task, description="Phase 2: Analysis & Modeling..."
                        )
                    elif phase == Phase.COMPLETE:
                        progress.update(task, description="Assembling notebook...")

            # The last event is the final state dict.
            final_state_dict = current_state_dict

        except (ValueError, KeyError, TypeError, FileNotFoundError) as e:
            logger.error(f"Configuration/Input error during analysis: {e}")
            console.print(f"[red]Error during analysis: {e}[/red]")
            current_state_dict.setdefault("errors", [])
            current_state_dict["errors"].append(str(e))
            final_state_dict = current_state_dict
        except Exception as e:
            logger.critical(
                f"Critical system failure during analysis: {e}", exc_info=True
            )
            console.print(f"[bold red]Critical system failure: {e}[/bold red]")
            current_state_dict.setdefault("errors", [])
            current_state_dict["errors"].append(f"System Crash: {e}")
            final_state_dict = current_state_dict
        finally:
            # Close the generator so LangGraph can release any internal resources.
            graph_stream.close()

    execution_time = time.time() - start_time

    # Convert the final state dict back to an object for a consistent return type.
    try:
        final_state_obj = AnalysisState.model_validate(final_state_dict)
    except Exception as e:
        logger.warning(f"Could not reconstruct full AnalysisState from dictionary: {e}")
        logger.debug(f"Corrupted state dict keys: {list(final_state_dict.keys())}")
        console.print(f"[red]Warning: State corruption detected: {e}[/red]")
        # Fall back to a minimal valid state preserving any partial results.
        # Use model_copy to avoid direct attribute mutation on a Pydantic model instance.
        existing_errors = list(initial_state.errors) if hasattr(initial_state, "errors") else []
        partial_update: dict = {
            "total_tokens_used": final_state_dict.get("total_tokens_used", 0),
            "errors": existing_errors + [f"State Reconstruction Error: {e}"] + final_state_dict.get("errors", []),
        }
        # Carry over any partial results that survived the crash.
        for key in ("final_notebook_path", "result_path", "execution_time"):
            if final_state_dict.get(key) is not None:
                partial_update[key] = final_state_dict[key]
        final_state_obj = initial_state.model_copy(update=partial_update)

    # Report results
    if final_state_obj and getattr(final_state_obj, "final_notebook_path", None):
        msg = (
            f"Analysis Complete!\n"
            f"Notebook: {final_state_obj.final_notebook_path}\n"
            f"Quality Score: {final_state_obj.final_quality_score:.2f}\n"
            f"Time: {execution_time:.1f}s"
        )
        logger.info(msg)
        console.print(
            Panel(
                f"[green]✓ Analysis Complete![/green]\n\n"
                f"Notebook: {final_state_obj.final_notebook_path}\n"
                f"Quality Score: {final_state_obj.final_quality_score:.2f}\n"
                f"Time: {execution_time:.1f}s\n"
                f"Total Iterations: {final_state_obj.phase1_iteration + final_state_obj.phase2_iteration}",
                title="Results",
            )
        )
        return final_state_obj
    else:
        logger.warning("Analysis completed but no notebook generated")
        console.print(
            "[yellow]Warning: Analysis completed but no notebook generated[/yellow]"
        )
        return final_state_obj


def main():
    """Main entry point."""
    args = parse_args()

    # Clear Cache if requested
    if args.clear_cache:
        cm = CacheManager()
        cm.clear_expired_caches()
        # If user ONLY wanted to clear cache, we might stop?
        # Typically flags are modifiers.
        # Requirement says "CLI options ... --clear-cache".
        console.print("[green]Expired caches cleared.[/green]")

    # Validate mutually exclusive arguments for input
    if not args.csv and not args.files and not args.db_uri:
        console.print("[red]Either --csv, --files, or --db-uri must be provided.[/red]")
        return 1

    # Multi-file Logic
    multi_file_input = None
    csv_path = args.csv

    # Handle DB Extraction (Approach 1)
    if args.db_uri and args.db_query:
        from src.server.services.data_ingestion import ingest_from_sql
        try:
            console.print(f"[cyan]Extracting data from database...[/cyan]")
            csv_path = ingest_from_sql(args.db_uri, args.db_query, output_dir="data/uploads")
            console.print(f"[green]Data extracted to {csv_path}[/green]")
        except Exception as e:
            console.print(f"[red]Database extraction failed: {e}[/red]")
            return 1

    if args.files:
        files = []
        cm = CacheManager()  # Used for hashing

        for f_path in args.files:
            p = resolve_file_path(f_path)
            if not p.exists():
                console.print(f"[red]File not found: {f_path}[/red]")
                return 1

            # Determine Type
            ext = p.suffix.lower()
            ft = FileType.UNKNOWN
            if ext == ".csv":
                ft = FileType.CSV
            elif ext in [".xlsx", ".xls"]:
                ft = FileType.EXCEL
            elif ext == ".json":
                ft = FileType.JSON
            elif ext == ".parquet":
                ft = FileType.PARQUET

            # Compute Hash
            f_hash = cm.compute_combined_hash([str(p)])  # Single file hash

            files.append(
                FileInput(
                    file_path=str(p), file_hash=f_hash, file_type=ft, alias=p.stem
                )
            )

        if len(files) > 1:
            multi_file_input = MultiFileInput(files=files)
            # Use the first file as the primary path for compatibility until merged
            if not csv_path:
                csv_path = str(files[0].file_path)
        elif len(files) == 1:
            # Just treating as single file
            if not csv_path:
                csv_path = str(files[0].file_path)

    try:
        final_state = run_analysis(
            csv_path=csv_path,
            target_column=args.target,
            analysis_type=args.type,
            analysis_question=args.question,
            title=args.title,
            exclude_columns=args.exclude,
            data_dictionary_path=args.data_dictionary,
            mode=args.mode,
            use_cache=args.use_cache,
            no_cache=args.no_cache,
            verbose=args.verbose,
            multi_file_input=multi_file_input,
            db_uri=args.db_uri,
        )

        if final_state and final_state.final_notebook_path:
            console.print(
                f"\n[bold]Open notebook:[/bold] jupyter notebook {final_state.final_notebook_path}"
            )

    except FileNotFoundError as e:
        console.print(f"[red]Error: {e}[/red]")
        return 1
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user.[/yellow]")
        return 130
    except (ValueError, KeyError) as e:
        console.print(f"[red]Configuration/Input Error: {e}[/red]")
        if args.verbose:
            console.print(traceback.format_exc())
        return 1
    except Exception as e:
        console.print(f"[red]Unexpected Error: {e}[/red]")
        if args.verbose:
            console.print(traceback.format_exc())
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
