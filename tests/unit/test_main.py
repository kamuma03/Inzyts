import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from src.main import parse_args, resolve_file_path, main, run_analysis
from src.models.state import AnalysisState, Phase


def _closeable_iter(items):
    """Wrap a list in an iterator that has a .close() method like a generator."""
    class _Iter:
        def __init__(self):
            self._it = iter(items)
        def __iter__(self):
            return self
        def __next__(self):
            return next(self._it)
        def close(self):
            pass
    return _Iter()


@patch("sys.argv", ["main.py", "--csv", "test.csv", "--target", "price", "--type", "regression"])
def test_parse_args_basic():
    args = parse_args()
    assert args.csv == "test.csv"
    assert args.target == "price"
    assert args.type == "regression"


@patch("src.main.Path.exists")
def test_resolve_file_path_exists(mock_exists):
    mock_exists.return_value = True
    path = resolve_file_path("some_file.csv")
    assert path.name == "some_file.csv"


@patch("src.main.settings.file_search_paths", [])
@patch("src.main.Path.exists")
def test_resolve_file_path_not_exists(mock_exists):
    mock_exists.return_value = False
    path = resolve_file_path("missing_file.csv")
    assert path.name == "missing_file.csv"


@patch("src.main.parse_args")
@patch("src.main.console")
def test_main_no_files_provided(mock_console, mock_parse_args):
    mock_args = MagicMock()
    mock_args.csv = None
    mock_args.files = None
    mock_args.db_uri = None
    mock_args.clear_cache = False
    mock_parse_args.return_value = mock_args

    result = main()
    assert result == 1


@patch("src.main.parse_args")
@patch("src.main.CacheManager")
def test_main_clear_cache(mock_cache_manager, mock_parse_args):
    mock_args = MagicMock()
    mock_args.clear_cache = True
    mock_args.csv = "dummy.csv"
    mock_args.files = None
    mock_args.db_uri = None
    mock_parse_args.return_value = mock_args

    with patch("src.main.run_analysis", side_effect=FileNotFoundError("Mocked")):
        main()

    mock_cm_instance = mock_cache_manager.return_value
    mock_cm_instance.clear_expired_caches.assert_called_once()


@patch("src.main.resolve_file_path")
def test_run_analysis_file_not_found(mock_resolve):
    mock_path = MagicMock()
    mock_path.exists.return_value = False
    mock_resolve.return_value = mock_path

    with pytest.raises(FileNotFoundError):
        run_analysis(csv_path="nonexistent.csv")


@patch("src.main.console")
@patch("src.main.resolve_file_path")
@patch("src.main.get_graph")
@patch("src.main.CacheManager")
def test_run_analysis_success(mock_cm, mock_get_graph, mock_resolve, mock_console):
    mock_path = MagicMock(spec=Path)
    mock_path.exists.return_value = True
    mock_path.name = "test.csv"
    mock_path.__str__ = MagicMock(return_value="/data/test.csv")
    mock_resolve.return_value = mock_path

    mock_check = MagicMock()
    mock_check.status.value = "miss"
    mock_cm.return_value.check_cache.return_value = mock_check

    # graph.stream returns state dicts in "values" mode
    mock_graph = MagicMock()
    mock_graph.stream.return_value = _closeable_iter([
        {"current_phase": Phase.PHASE_1, "csv_path": "/data/test.csv"},
        {
            "current_phase": Phase.COMPLETE,
            "csv_path": "/data/test.csv",
            "final_notebook_path": "out.ipynb",
            "final_quality_score": 9.5,
        },
    ])
    mock_get_graph.return_value = mock_graph

    state = run_analysis(
        csv_path="test.csv",
        no_cache=True,
        interactive=False,
        verbose=False,
    )

    assert state is not None
    assert state.final_notebook_path == "out.ipynb"
    assert state.final_quality_score == 9.5


@patch("src.main.console")
@patch("src.main.resolve_file_path")
@patch("src.main.get_graph")
@patch("src.main.CacheManager")
def test_run_analysis_cache_hit_use_cache(mock_cm, mock_get_graph, mock_resolve, mock_console):
    mock_path = MagicMock(spec=Path)
    mock_path.exists.return_value = True
    mock_path.name = "test.csv"
    mock_path.__str__ = MagicMock(return_value="/data/test.csv")
    mock_resolve.return_value = mock_path

    mock_check = MagicMock()
    mock_check.status = MagicMock()
    mock_check.status.__eq__ = lambda self, other: str(other).endswith("VALID")
    mock_check.status.value = "valid"
    # Make the == comparison with CacheStatus.VALID work
    from src.utils.cache_manager import CacheStatus, ProfileCache
    from datetime import datetime, timedelta
    mock_check.status = CacheStatus.VALID
    # Use model_construct to bypass Pydantic validation for required fields
    mock_check.cache = ProfileCache.model_construct(
        cache_id="test_cache",
        csv_path="/data/test.csv",
        csv_hash="abc123",
        csv_size_bytes=100,
        csv_row_count=10,
        csv_column_count=3,
        created_at=datetime.now(),
        expires_at=datetime.now() + timedelta(days=5),
        profile_lock={},
        profile_cells=[],
        profile_handoff=None,
        pipeline_mode="exploratory",
        phase1_quality_score=8.0,
        user_intent=None,
        agent_version="test",
    )
    mock_cm.return_value.check_cache.return_value = mock_check

    mock_graph = MagicMock()
    mock_graph.stream.return_value = _closeable_iter([
        {
            "current_phase": Phase.COMPLETE,
            "csv_path": "/data/test.csv",
            "final_notebook_path": "cached_out.ipynb",
            "final_quality_score": 8.0,
        }
    ])
    mock_get_graph.return_value = mock_graph

    state = run_analysis(
        csv_path="test.csv",
        use_cache=True,
        no_cache=False,
        interactive=False,
        verbose=False,
    )

    assert state.final_notebook_path == "cached_out.ipynb"


@patch("src.main.console")
@patch("src.main.resolve_file_path")
@patch("src.main.get_graph")
@patch("src.main.CacheManager")
def test_run_analysis_graph_error(mock_cm, mock_get_graph, mock_resolve, mock_console):
    mock_path = MagicMock(spec=Path)
    mock_path.exists.return_value = True
    mock_path.name = "test.csv"
    mock_path.__str__ = MagicMock(return_value="/data/test.csv")
    mock_resolve.return_value = mock_path

    mock_check = MagicMock()
    mock_check.status.value = "miss"
    mock_cm.return_value.check_cache.return_value = mock_check

    mock_graph = MagicMock()
    mock_graph.stream.return_value = _closeable_iter([])
    # Make the stream iteration raise
    mock_graph.stream.return_value = MagicMock()
    mock_graph.stream.return_value.__iter__ = MagicMock(side_effect=ValueError("Graph exploded"))
    mock_graph.stream.return_value.close = MagicMock()
    mock_get_graph.return_value = mock_graph

    state = run_analysis(
        csv_path="test.csv",
        no_cache=True,
        interactive=False,
        verbose=False,
    )

    assert state is not None
    assert any("Graph exploded" in str(err) for err in state.errors)


@patch("src.main.parse_args")
@patch("src.main.console")
def test_main_cli_execution_success(mock_console, mock_parse_args):
    mock_args = MagicMock()
    mock_args.csv = "test.csv"
    mock_args.files = None
    mock_args.db_uri = None
    mock_args.clear_cache = False
    mock_args.target = "price"
    mock_parse_args.return_value = mock_args

    mock_state = MagicMock()
    mock_state.final_notebook_path = "output.ipynb"
    mock_state.final_quality_score = 9.0

    with patch("src.main.run_analysis", return_value=mock_state):
        exit_code = main()
        assert exit_code == 0


@patch("src.main.console")
@patch("src.main.resolve_file_path")
@patch("src.main.get_graph")
@patch("src.main.CacheManager")
def test_run_analysis_verbose_interactive(mock_cm, mock_get_graph, mock_resolve, mock_console):
    mock_path = MagicMock(spec=Path)
    mock_path.exists.return_value = True
    mock_path.name = "test.csv"
    mock_path.__str__ = MagicMock(return_value="/data/test.csv")
    mock_resolve.return_value = mock_path

    mock_check = MagicMock()
    mock_check.status.value = "miss"
    mock_cm.return_value.check_cache.return_value = mock_check

    mock_graph = MagicMock()
    mock_graph.stream.return_value = _closeable_iter([
        {"current_phase": Phase.PHASE_2, "csv_path": "/data/test.csv"},
        {
            "current_phase": Phase.COMPLETE,
            "csv_path": "/data/test.csv",
            "final_notebook_path": "out.ipynb",
            "final_quality_score": 9.5,
        },
    ])
    mock_get_graph.return_value = mock_graph

    with patch("builtins.input", return_value="y"):
        state = run_analysis(
            csv_path="test.csv",
            use_cache=False,
            no_cache=True,
            interactive=True,
            verbose=True,
        )

    assert state.final_notebook_path == "out.ipynb"


@patch("src.main.console")
@patch("src.main.resolve_file_path")
@patch("src.main.get_graph")
@patch("src.main.CacheManager")
def test_run_analysis_interactive_cache_decline(mock_cm, mock_get_graph, mock_resolve, mock_console):
    mock_path = MagicMock(spec=Path)
    mock_path.exists.return_value = True
    mock_path.name = "test.csv"
    mock_path.__str__ = MagicMock(return_value="/data/test.csv")
    mock_resolve.return_value = mock_path

    from src.utils.cache_manager import CacheStatus, ProfileCache
    from datetime import datetime, timedelta
    mock_check = MagicMock()
    mock_check.status = CacheStatus.VALID
    mock_check.cache = ProfileCache.model_construct(
        cache_id="test_cache",
        csv_path="/data/test.csv",
        csv_hash="abc123",
        csv_size_bytes=100,
        csv_row_count=10,
        csv_column_count=3,
        created_at=datetime.now(),
        expires_at=datetime.now() + timedelta(days=5),
        profile_lock={},
        profile_cells=[],
        profile_handoff=None,
        pipeline_mode="exploratory",
        phase1_quality_score=8.0,
        user_intent=None,
        agent_version="test",
    )
    mock_cm.return_value.check_cache.return_value = mock_check

    mock_graph = MagicMock()
    mock_graph.stream.return_value = _closeable_iter([
        {
            "current_phase": Phase.COMPLETE,
            "csv_path": "/data/test.csv",
            "final_notebook_path": "graph.ipynb",
            "final_quality_score": 5.0,
        }
    ])
    mock_get_graph.return_value = mock_graph

    with patch("builtins.input", return_value="n"):
        state = run_analysis("test.csv", interactive=True, no_cache=False)
        assert state.final_notebook_path == "graph.ipynb"


@patch("src.main.console")
@patch("src.main.resolve_file_path")
@patch("src.main.get_graph")
@patch("src.main.CacheManager")
def test_run_analysis_state_corruption_fallback(mock_cm, mock_get_graph, mock_resolve, mock_console):
    mock_path = MagicMock(spec=Path)
    mock_path.exists.return_value = True
    mock_path.name = "test.csv"
    mock_path.__str__ = MagicMock(return_value="/data/test.csv")
    mock_resolve.return_value = mock_path

    mock_check = MagicMock()
    mock_check.status.value = "miss"
    mock_cm.return_value.check_cache.return_value = mock_check

    mock_graph = MagicMock()
    # Stream yields a dict with an invalid phase string that will cause
    # AnalysisState.model_validate to fail
    mock_graph.stream.return_value = _closeable_iter([
        {"current_phase": "NOT_A_REAL_PHASE", "total_tokens_used": 500, "csv_path": "/data/test.csv"}
    ])
    mock_get_graph.return_value = mock_graph

    state = run_analysis(csv_path="test.csv", no_cache=True, interactive=False)

    assert hasattr(state, "errors")
    assert any("State Reconstruction Error" in str(err) for err in state.errors)
    assert getattr(state, "total_tokens_used", 0) == 500


@patch("src.main.parse_args")
@patch("src.main.resolve_file_path")
@patch("src.main.console")
def test_main_cli_multi_files(mock_console, mock_resolve, mock_parse_args):
    mock_args = MagicMock()
    mock_args.csv = None
    mock_args.files = ["file1.csv", "file2.json"]
    mock_args.db_uri = None
    mock_args.clear_cache = False
    mock_args.target = None
    mock_args.type = None
    mock_parse_args.return_value = mock_args

    mock_path_1 = MagicMock(spec=Path)
    mock_path_1.exists.return_value = True
    mock_path_1.suffix = ".csv"
    mock_path_1.stem = "file1"
    mock_path_1.__str__ = MagicMock(return_value="file1.csv")

    mock_path_2 = MagicMock(spec=Path)
    mock_path_2.exists.return_value = True
    mock_path_2.suffix = ".json"
    mock_path_2.stem = "file2"
    mock_path_2.__str__ = MagicMock(return_value="file2.json")

    mock_resolve.side_effect = [mock_path_1, mock_path_2]

    with patch("src.main.run_analysis") as mock_run, \
         patch("src.main.CacheManager") as mock_cm_main:
        mock_state = MagicMock()
        mock_state.final_notebook_path = "multi.ipynb"
        mock_run.return_value = mock_state

        mock_cm_instance = mock_cm_main.return_value
        mock_cm_instance.compute_combined_hash.return_value = "fake_hash_string"
        exit_code = main()

    assert exit_code == 0
    _, kwargs = mock_run.call_args
    assert kwargs["multi_file_input"] is not None
    assert len(kwargs["multi_file_input"].files) == 2


@patch("src.main.parse_args")
@patch("src.main.CacheManager")
@patch("src.main.console")
def test_main_cli_configuration_error(mock_console, mock_cache, mock_parse_args):
    mock_args = MagicMock()
    mock_args.csv = "test.csv"
    mock_args.files = None
    mock_args.db_uri = None
    mock_args.clear_cache = True
    mock_parse_args.return_value = mock_args

    with patch("src.main.run_analysis", side_effect=KeyError("Missing configs")):
        exit_code = main()
        assert exit_code == 1
