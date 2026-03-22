"""
Sandbox Execution Service using jupyter_client.

Runs Python code in an isolated Jupyter kernel environment, capturing
outputs, errors, and execution status. Useful for actually validating
AI-generated code instead of relying on string heuristics.
"""

import queue
import time
from typing import List, Optional
import jupyter_client

from src.utils.logger import get_logger

logger = get_logger()

MAX_IMAGE_SIZE = int(5 * 1024 * 1024)  # 5MB limit
MAX_OUTPUT_LEN = 1500
MAX_TRACEBACK_LEN = 2000


def truncate_str(text: str, max_len: int = MAX_OUTPUT_LEN) -> str:
    """Truncate a string to max_len, keeping head and tail with a marker in between."""
    if not text:
        return ""
    if not isinstance(text, str):
        text = str(text)
    if len(text) > max_len:
        half = max_len // 2
        return text[:half] + "\n\n...[TRUNCATED_FOR_SIZE]...\n\n" + text[-half:]
    return text


class ExecutionResult:
    """Represents the result of a single cell execution."""

    def __init__(self):
        self.success: bool = True
        self.output: str = ""
        self.error_name: Optional[str] = None
        self.error_value: Optional[str] = None
        self.traceback: List[str] = []
        self.execution_count: Optional[int] = None
        self.images: List[str] = []  # Base64-encoded images from display_data


class SandboxExecutor:
    """Manages an isolated Jupyter Kernel for safely executing AI generated code."""

    def __init__(self, kernel_name: str = "python3", execution_timeout: int = 60):
        self.kernel_name = kernel_name
        self.execution_timeout = execution_timeout
        self.km = None
        self.kc = None
        self._start_kernel()

    def _start_kernel(self):
        """Starts the Jupyter kernel and client."""
        try:
            self.km, self.kc = jupyter_client.manager.start_new_kernel(
                kernel_name=self.kernel_name
            )
            logger.info("Sandbox executor kernel started successfully.")
        except Exception as e:
            logger.error(f"Failed to start sandbox kernel: {e}")
            self.shutdown()
            raise RuntimeError(f"Sandbox kernel initialization failed: {e}")

    def execute_cell(self, code: str) -> ExecutionResult:
        """
        Executes a single code cell inside the sandbox.

        Args:
            code (str): The Python code to execute.

        Returns:
            ExecutionResult Object containing output logs, error status, and tracebacks.
        """
        result = ExecutionResult()
        output_parts = []

        if not self.kc:
            result.success = False
            result.error_name = "KernelError"
            result.error_value = "Kernel client not initialized."
            return result

        try:
            # Send execution request
            msg_id = self.kc.execute(code)

            # Poll for IOPub messages (stdout, stderr, display data)
            start_time = time.time()

            while True:
                if time.time() - start_time > self.execution_timeout:
                    result.success = False
                    result.error_name = "TimeoutError"
                    result.error_value = f"Cell execution exceeded {self.execution_timeout}s timeout (Infinite loop detected)."
                    logger.warning(
                        f"Sandbox execution timed out after {self.execution_timeout}s."
                    )
                    try:
                        self.km.interrupt_kernel()
                    except Exception:
                        pass
                    break

                try:
                    # Use a short per-call timeout so the loop yields the thread
                    # between messages instead of spinning at 100% CPU.
                    msg = self.kc.get_iopub_msg(timeout=0.1)

                    if msg["parent_header"].get("msg_id") == msg_id:
                        msg_type = msg["header"]["msg_type"]
                        content = msg["content"]

                        if msg_type == "status":
                            if content["execution_state"] == "idle":
                                # Execution finished
                                break
                        elif msg_type == "stream":
                            if content["name"] == "stdout":
                                output_parts.append(content["text"])
                            elif content["name"] == "stderr":
                                output_parts.append(f"[STDERR] {content['text']}")
                        elif msg_type == "execute_result" or msg_type == "display_data":
                            if "image/png" in content["data"]:
                                img_data = content["data"]["image/png"]
                                if len(img_data) > MAX_IMAGE_SIZE:
                                    logger.warning(f"Skipped image of size {len(img_data)} exceeding MAX_IMAGE_SIZE")
                                else:
                                    result.images.append(img_data)
                            if "text/plain" in content["data"]:
                                output_parts.append(content["data"]["text/plain"])
                        elif msg_type == "error":
                            result.success = False
                            result.error_name = content["ename"]
                            result.error_value = content["evalue"]
                            result.traceback = content["traceback"]

                except queue.Empty:
                    # No message yet — yield the thread briefly and let the outer
                    # wall-clock check handle the overall timeout.
                    time.sleep(0.01)
                    continue

            # Try getting execution reply from shell channel for exact pass/fail status
            try:
                reply = self.kc.get_shell_msg(timeout=2)
                if reply["parent_header"].get("msg_id") == msg_id:
                    reply_content = reply["content"]
                    if reply_content["status"] == "error":
                        result.success = False
                        if not result.error_name:
                            result.error_name = reply_content.get("ename")
                            result.error_value = reply_content.get("evalue")
                            result.traceback = reply_content.get("traceback", [])

                    result.execution_count = reply_content.get("execution_count")
            except queue.Empty:
                pass

        except Exception as e:
            logger.error(f"Sandbox execution crashed: {e}")
            result.success = False
            result.error_name = "SandboxSystemError"
            result.error_value = str(e)

        # Truncate massive outputs to prevent LLM token bloat on retries

        result.output = truncate_str("".join(output_parts))
        if result.error_value:
            result.error_value = truncate_str(result.error_value)
        if result.traceback:
            tb_str = "\\n".join(result.traceback)
            result.traceback = [truncate_str(tb_str, max_len=MAX_TRACEBACK_LEN)]

        return result

    def shutdown(self):
        """Shutdown the kernel client and manager forcefully."""
        if self.kc:
            try:
                self.kc.stop_channels()
            except Exception:
                pass
            self.kc = None

        if self.km:
            try:
                self.km.shutdown_kernel(now=True)
            except Exception:
                pass
            self.km = None

        logger.info("Sandbox executor kernel shut down.")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown()
