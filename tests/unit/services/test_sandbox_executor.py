import pytest
from unittest.mock import MagicMock, patch
import queue

from src.services.sandbox_executor import SandboxExecutor, ExecutionResult

@pytest.fixture
def mock_jupyter_client():
    """Mocks jupyter_client.manager.start_new_kernel"""
    with patch("src.services.sandbox_executor.jupyter_client") as mock_jc:
        mock_km = MagicMock()
        mock_kc = MagicMock()
        mock_jc.manager.start_new_kernel.return_value = (mock_km, mock_kc)
        yield mock_km, mock_kc

def test_executor_initialization(mock_jupyter_client):
    """Test successful initialization starts channels and waits."""
    mock_km, mock_kc = mock_jupyter_client
    executor = SandboxExecutor(kernel_name="python3")
    
    assert executor.km == mock_km
    assert executor.kc == mock_kc

def test_executor_initialization_failure():
    """Test standard shutdown on initialization failure."""
    with patch("src.services.sandbox_executor.jupyter_client") as mock_jc:
        mock_jc.manager.start_new_kernel.side_effect = Exception("Kernel died")
        with pytest.raises(RuntimeError, match="Sandbox kernel initialization failed"):
            SandboxExecutor()
        
def test_execute_cell_no_client(mock_jupyter_client):
    """Test executing a cell when the kernel client is missing."""
    mock_km, mock_kc = mock_jupyter_client
    executor = SandboxExecutor()
    executor.kc = None  # Simulate broken state
    
    result = executor.execute_cell("print('hi')")
    assert result.success is False
    assert result.error_name == "KernelError"

def test_execute_cell_success(mock_jupyter_client):
    """Test a successful cell execution getting stdout and plain text results."""
    mock_km, mock_kc = mock_jupyter_client
    mock_kc.execute.return_value = "msg_123"
    
    # Mock sequence of IOPub messages
    msg1 = {
        "parent_header": {"msg_id": "msg_123"},
        "header": {"msg_type": "stream"},
        "content": {"name": "stdout", "text": "Hello World\n"}
    }
    msg2 = {
        "parent_header": {"msg_id": "msg_123"},
        "header": {"msg_type": "execute_result"},
        "content": {"data": {"text/plain": "42"}}
    }
    msg3 = {
        "parent_header": {"msg_id": "msg_123"},
        "header": {"msg_type": "status"},
        "content": {"execution_state": "idle"}
    }
    mock_kc.get_iopub_msg.side_effect = [msg1, msg2, msg3]
    
    # Shell reply
    mock_kc.get_shell_msg.return_value = {
        "parent_header": {"msg_id": "msg_123"},
        "content": {"status": "ok", "execution_count": 1}
    }
    
    executor = SandboxExecutor()
    result = executor.execute_cell("print('Hello World')\n42")
    
    assert result.success is True
    assert "Hello World" in result.output
    assert "42" in result.output
    assert result.execution_count == 1

def test_execute_cell_stderr_and_error(mock_jupyter_client):
    """Test tracking stderr and explicit error messages."""
    mock_km, mock_kc = mock_jupyter_client
    mock_kc.execute.return_value = "msg_err"
    
    msg1 = {
        "parent_header": {"msg_id": "msg_err"},
        "header": {"msg_type": "stream"},
        "content": {"name": "stderr", "text": "Warning!\n"}
    }
    msg2 = {
        "parent_header": {"msg_id": "msg_err"},
        "header": {"msg_type": "error"},
        "content": {"ename": "ValueError", "evalue": "Bad data", "traceback": ["Traceback..."]}
    }
    msg3 = {
        "parent_header": {"msg_id": "msg_err"},
        "header": {"msg_type": "status"},
        "content": {"execution_state": "idle"}
    }
    mock_kc.get_iopub_msg.side_effect = [msg1, msg2, msg3]
    
    mock_kc.get_shell_msg.return_value = {
        "parent_header": {"msg_id": "msg_err"},
        "content": {"status": "error", "ename": "ValueError"}
    }
    
    executor = SandboxExecutor()
    result = executor.execute_cell("raise ValueError('Bad data')")
    
    assert result.success is False
    assert "[STDERR] Warning!" in result.output
    assert result.error_name == "ValueError"
    assert "Traceback" in result.traceback[0]

def test_execute_cell_timeout(mock_jupyter_client):
    """Test timeout when cell runs endlessly."""
    mock_km, mock_kc = mock_jupyter_client
    mock_kc.execute.return_value = "msg_timeout"
    
    # Make get_iopub_msg raise queue.Empty indefinitely to trigger timeout logic
    def mock_get_iopub(timeout=1):
        raise queue.Empty()
    mock_kc.get_iopub_msg.side_effect = mock_get_iopub
    
    # Use a tiny timeout for fast testing
    executor = SandboxExecutor(execution_timeout=0.1)
    result = executor.execute_cell("while True: pass")
    
    assert result.success is False
    assert result.error_name == "TimeoutError"
    mock_km.interrupt_kernel.assert_called()

def test_execute_shell_error(mock_jupyter_client):
    """Test capturing execution error via the shell reply fallback."""
    mock_km, mock_kc = mock_jupyter_client
    mock_kc.execute.return_value = "msg_shell"
    
    msg1 = {
        "parent_header": {"msg_id": "msg_shell"},
        "header": {"msg_type": "status"},
        "content": {"execution_state": "idle"}
    }
    mock_kc.get_iopub_msg.side_effect = [msg1]
    
    mock_kc.get_shell_msg.return_value = {
        "parent_header": {"msg_id": "msg_shell"},
        "content": {
            "status": "error", 
            "ename": "SyntaxError", 
            "evalue": "invalid syntax",
            "traceback": ["SyntaxError: invalid syntax"],
            "execution_count": 2
        }
    }
    
    executor = SandboxExecutor()
    result = executor.execute_cell("invalid code")
    
    assert result.success is False
    assert result.error_name == "SyntaxError"
    assert result.error_value == "invalid syntax"

def test_shutdown_and_context_manager(mock_jupyter_client):
    """Test context manager triggers shutdown."""
    mock_km, mock_kc = mock_jupyter_client
    
    with SandboxExecutor() as executor:
        assert executor.km is not None
        
    mock_kc.stop_channels.assert_called_once()
    mock_km.shutdown_kernel.assert_called_once_with(now=True)
