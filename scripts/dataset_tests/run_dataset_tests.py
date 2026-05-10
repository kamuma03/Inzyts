#!/usr/bin/env python3
"""
Inzyts Dataset Test Runner (API-Based)

A comprehensive test runner for running analysis tests on datasets defined in
inzyts_test_datasets.csv. Triggers jobs via the HTTP API (requires the application
to be running).

Prerequisites:
    - Backend server running at http://localhost:8000
    - Celery worker running
    - Redis running

Usage:
    # List all available datasets
    python run_dataset_tests.py --list

    # Run a specific dataset by name
    python run_dataset_tests.py --dataset "Titanic"

    # Run multiple datasets
    python run_dataset_tests.py --dataset "Titanic" --dataset "Wine Quality"

    # Run all datasets for a specific analysis mode
    python run_dataset_tests.py --mode "EDA"
    python run_dataset_tests.py --mode "Prediction"
    python run_dataset_tests.py --mode "Forecasting"

    # Run all datasets
    python run_dataset_tests.py --all

    # Interactive mode - select datasets from menu
    python run_dataset_tests.py --interactive

    # Dry run - show what would be tested
    python run_dataset_tests.py --all --dry-run

    # Run with verbose output
    python run_dataset_tests.py --dataset "Titanic" --verbose

    # Use custom API endpoint
    python run_dataset_tests.py --dataset "Titanic" --api-url "http://localhost:8000"
"""

import argparse
import csv
import json
import hashlib
import os
import sys
import time
import requests
import traceback as tb
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any

# Constants
SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent
DEFAULT_API_URL = "http://localhost:8000"
DEFAULT_POLL_INTERVAL = 5  # seconds
DEFAULT_TIMEOUT = 1800  # 30 minutes max per job


class AnalysisModeCategory(str, Enum):
    """Categories for analysis modes in the test datasets."""
    EDA = "EDA"
    PREDICTION = "Prediction"
    FORECASTING = "Forecasting"
    COMPARATIVE = "Comparative"
    DIAGNOSTIC = "Diagnostic"
    SEGMENTATION = "Segmentation"
    DIMENSIONALITY = "Dimensionality"
    MULTI_MODE = "Multi-Mode"


@dataclass
class DatasetConfig:
    """Configuration for a test dataset."""
    name: str
    link: str
    analysis_mode: str
    why: str
    data_dictionary: Optional[str]
    files: List[str]
    
    @property
    def mode_category(self) -> str:
        """Extract the main mode category from analysis_mode."""
        mode = self.analysis_mode.lower()
        if "eda" in mode or "exploratory" in mode:
            return AnalysisModeCategory.EDA.value
        elif "prediction" in mode or "classification" in mode or "regression" in mode:
            return AnalysisModeCategory.PREDICTION.value
        elif "forecast" in mode:
            return AnalysisModeCategory.FORECASTING.value
        elif "comparative" in mode or "a/b" in mode.lower():
            return AnalysisModeCategory.COMPARATIVE.value
        elif "diagnostic" in mode or "root cause" in mode:
            return AnalysisModeCategory.DIAGNOSTIC.value
        elif "segment" in mode or "cluster" in mode:
            return AnalysisModeCategory.SEGMENTATION.value
        elif "dimension" in mode or "pca" in mode or "t-sne" in mode:
            return AnalysisModeCategory.DIMENSIONALITY.value
        elif "multi" in mode:
            return AnalysisModeCategory.MULTI_MODE.value
        return self.analysis_mode

    @property
    def primary_file(self) -> Optional[str]:
        """Returns the first valid data file."""
        for f in self.files:
            if f and f.strip():
                return f.strip()
        return None
    
    @property
    def api_mode(self) -> str:
        """Get the API mode value (exploratory or predictive)."""
        mode = self.analysis_mode.lower()
        if "eda" in mode or "exploratory" in mode:
            return "exploratory"
        else:
            return "predictive"
    
    def validate_files(self) -> Dict[str, bool]:
        """Check if data files exist."""
        results = {}
        for f in self.files:
            if f and f.strip():
                path = Path(f.strip())
                results[f] = path.exists()
        return results


@dataclass
class TestResult:
    """Result of a single dataset test run."""
    dataset_name: str
    success: bool
    start_time: datetime
    end_time: datetime
    duration_seconds: float
    job_id: Optional[str] = None
    notebook_path: Optional[str] = None
    error_message: Optional[str] = None
    quality_score: Optional[float] = None
    tokens_used: int = 0
    analysis_mode: str = ""
    job_status: str = ""
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "dataset_name": self.dataset_name,
            "success": self.success,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "duration_seconds": self.duration_seconds,
            "job_id": self.job_id,
            "notebook_path": self.notebook_path,
            "error_message": self.error_message,
            "quality_score": self.quality_score,
            "tokens_used": self.tokens_used,
            "analysis_mode": self.analysis_mode,
            "job_status": self.job_status
        }


@dataclass
class TestReport:
    """Summary report for all test runs."""
    total_tests: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    results: List[TestResult] = field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    @property
    def total_duration_seconds(self) -> float:
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0
    
    @property
    def pass_rate(self) -> float:
        if self.total_tests == 0:
            return 0.0
        return (self.passed / self.total_tests) * 100
    
    def add_result(self, result: TestResult):
        """Add a test result."""
        self.results.append(result)
        self.total_tests += 1
        if result.success:
            self.passed += 1
        else:
            self.failed += 1
    
    def add_skipped(self):
        """Add a skipped test."""
        self.total_tests += 1
        self.skipped += 1
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "summary": {
                "total_tests": self.total_tests,
                "passed": self.passed,
                "failed": self.failed,
                "skipped": self.skipped,
                "pass_rate": f"{self.pass_rate:.1f}%",
                "total_duration_seconds": self.total_duration_seconds,
                "start_time": self.start_time.isoformat() if self.start_time else None,
                "end_time": self.end_time.isoformat() if self.end_time else None,
            },
            "results": [r.to_dict() for r in self.results]
        }
    
    def print_summary(self):
        """Print a formatted summary."""
        print("\n" + "=" * 70)
        print("📊 TEST SUMMARY REPORT")
        print("=" * 70)
        print(f"  Total Tests:  {self.total_tests}")
        print(f"  ✅ Passed:    {self.passed}")
        print(f"  ❌ Failed:    {self.failed}")
        print(f"  ⏭️  Skipped:   {self.skipped}")
        print(f"  Pass Rate:   {self.pass_rate:.1f}%")
        print(f"  Duration:    {self.total_duration_seconds:.1f}s")
        print("-" * 70)
        
        if self.failed > 0:
            print("\n❌ FAILED TESTS:")
            for r in self.results:
                if not r.success:
                    print(f"  • {r.dataset_name}: {r.error_message or 'Unknown error'}")
                    if r.job_id:
                        print(f"    Job ID: {r.job_id}")
        
        if self.passed > 0:
            print("\n✅ PASSED TESTS:")
            for r in self.results:
                if r.success:
                    score = f" (Q={r.quality_score:.2f})" if r.quality_score else ""
                    print(f"  • {r.dataset_name}{score} - {r.duration_seconds:.1f}s")
                    if r.notebook_path:
                        print(f"    Notebook: {r.notebook_path}")
        
        print("=" * 70)


class InzytsAPIClient:
    """Client for interacting with the Inzyts API."""
    
    def __init__(self, base_url: str = DEFAULT_API_URL, token: Optional[str] = None, verbose: bool = False):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.verbose = verbose
        
    def _get_headers(self) -> Dict[str, str]:
        """Get default headers with authentication."""
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers
    
    def check_health(self) -> bool:
        """Check if the API server is running."""
        try:
            response = requests.get(f"{self.base_url}/docs", timeout=5)
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False
    
    def submit_analysis(
        self,
        csv_path: str,
        mode: str = "exploratory",
        target_column: Optional[str] = None,
        question: Optional[str] = None,
        dict_path: Optional[str] = None,
        analysis_type: Optional[str] = None,
        title: Optional[str] = None,
        use_cache: bool = False,
        multi_file_input: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Submit an analysis job to the API.
        
        Returns:
            Dict containing job_id, status, and other metadata.
        """
        payload = {
            "csv_path": csv_path,
            "mode": mode,
            "use_cache": use_cache
        }
        
        if multi_file_input:
            payload["multi_file_input"] = multi_file_input
        
        if target_column:
            payload["target_column"] = target_column
        if question:
            payload["question"] = question
        if title:
            payload["title"] = title
        if dict_path:
            payload["dict_path"] = dict_path
        if analysis_type:
            payload["analysis_type"] = analysis_type
        
        if self.verbose:
            print(f"  📤 Submitting to API: {json.dumps(payload, indent=2)}")
        
        response = requests.post(
            f"{self.base_url}/api/v2/analyze",
            json=payload,
            headers=self._get_headers(),
            timeout=30
        )
        
        if response.status_code != 200:
            raise Exception(f"API error {response.status_code}: {response.text}")
        
        return response.json()
    
    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """Get the status of a job."""
        response = requests.get(
            f"{self.base_url}/api/v2/jobs/{job_id}",
            headers=self._get_headers(),
            timeout=30
        )
        
        if response.status_code == 404:
            raise Exception(f"Job not found: {job_id}")
        elif response.status_code != 200:
            raise Exception(f"API error {response.status_code}: {response.text}")
        
        return response.json()
    
    def wait_for_completion(
        self,
        job_id: str,
        poll_interval: int = DEFAULT_POLL_INTERVAL,
        timeout: int = DEFAULT_TIMEOUT,
        verbose: bool = False
    ) -> Dict[str, Any]:
        """
        Poll the API until the job completes.
        
        Returns:
            Final job status.
        """
        start_time = time.time()
        last_status = None
        
        while True:
            elapsed = time.time() - start_time
            if elapsed > timeout:
                raise TimeoutError(f"Job {job_id} timed out after {timeout}s")
            
            status = self.get_job_status(job_id)
            job_status = status.get("status", "unknown")
            
            if job_status != last_status:
                if verbose:
                    print(f"  ⏳ Status: {job_status} (elapsed: {elapsed:.0f}s)")
                last_status = job_status
            
            # Check terminal states
            if job_status in ["completed", "failed", "cancelled"]:
                return status
            
            time.sleep(poll_interval)


def load_datasets(csv_path: Path) -> List[DatasetConfig]:
    """Load dataset configurations from CSV file."""
    datasets = []
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Skip empty rows
            if not row.get('Dataset_Name'):
                continue
            
            # Collect file paths
            files = []
            for i in range(1, 7):
                file_col = f'File_{i}'
                if file_col in row and row[file_col]:
                    files.append(row[file_col].strip())
            
            dataset = DatasetConfig(
                name=row.get('Dataset_Name', '').strip(),
                link=row.get('Link', '').strip(),
                analysis_mode=row.get('Analysis_Mode', '').strip(),
                why=row.get('Why', '').strip(),
                data_dictionary=row.get('Data_Dictionary', '').strip() or None,
                files=files
            )
            datasets.append(dataset)
    
    return datasets


def list_datasets(datasets: List[DatasetConfig], show_files: bool = False):
    """Print all available datasets."""
    print("\n📋 AVAILABLE DATASETS")
    print("=" * 80)
    
    # Group by mode category
    by_mode: Dict[str, List[DatasetConfig]] = {}
    for ds in datasets:
        cat = ds.mode_category
        if cat not in by_mode:
            by_mode[cat] = []
        by_mode[cat].append(ds)
    
    for mode, ds_list in sorted(by_mode.items()):
        print(f"\n🔹 {mode} ({len(ds_list)} datasets)")
        print("-" * 40)
        for i, ds in enumerate(ds_list, 1):
            file_status = "✓" if ds.primary_file and Path(ds.primary_file).exists() else "✗"
            print(f"  [{file_status}] {ds.name}")
            print(f"      Mode: {ds.analysis_mode} → API: {ds.api_mode}")
            if show_files and ds.files:
                for f in ds.files:
                    if f:
                        exists = "✓" if Path(f).exists() else "✗"
                        print(f"      [{exists}] {f}")
    
    print(f"\n📊 Total: {len(datasets)} datasets across {len(by_mode)} categories")
    print("=" * 80)


def interactive_select(datasets: List[DatasetConfig]) -> List[DatasetConfig]:
    """Interactive menu to select datasets."""
    print("\n🎯 INTERACTIVE DATASET SELECTION")
    print("=" * 60)
    print("Select an option:")
    print("  1. Run all datasets")
    print("  2. Select by analysis mode")
    print("  3. Select specific datasets")
    print("  4. Cancel")
    
    choice = input("\nEnter choice (1-4): ").strip()
    
    if choice == "1":
        return datasets
    
    elif choice == "2":
        # Group by mode
        modes = list(set(ds.mode_category for ds in datasets))
        print("\nAvailable modes:")
        for i, mode in enumerate(sorted(modes), 1):
            count = sum(1 for ds in datasets if ds.mode_category == mode)
            print(f"  {i}. {mode} ({count} datasets)")
        
        mode_choice = input("\nEnter mode number(s) separated by comma: ").strip()
        selected_indices = [int(x.strip()) - 1 for x in mode_choice.split(",") if x.strip().isdigit()]
        selected_modes = [sorted(modes)[i] for i in selected_indices if 0 <= i < len(modes)]
        
        return [ds for ds in datasets if ds.mode_category in selected_modes]
    
    elif choice == "3":
        print("\nAvailable datasets:")
        for i, ds in enumerate(datasets, 1):
            file_status = "✓" if ds.primary_file and Path(ds.primary_file).exists() else "✗"
            print(f"  {i}. [{file_status}] {ds.name} ({ds.analysis_mode})")
        
        ds_choice = input("\nEnter dataset number(s) separated by comma: ").strip()
        selected_indices = [int(x.strip()) - 1 for x in ds_choice.split(",") if x.strip().isdigit()]
        
        return [datasets[i] for i in selected_indices if 0 <= i < len(datasets)]
    
    return []



def calculate_file_hash(path: str) -> str:
    """Calculate MD5 hash of file."""
    hash_md5 = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

_FILE_TYPE_BY_EXT = {
    '.csv': 'CSV', '.xlsx': 'EXCEL', '.xls': 'EXCEL',
    '.json': 'JSON', '.parquet': 'PARQUET',
}


def _build_multi_file_input(valid_files: List[str]) -> Dict[str, Any]:
    """Construct the MultiFileInput payload from a list of valid file paths."""
    return {
        "files": [
            {
                "file_path": str(Path(f).resolve()),
                "file_hash": calculate_file_hash(f),
                "file_type": _FILE_TYPE_BY_EXT.get(Path(f).suffix.lower(), "UNKNOWN"),
                "alias": Path(f).stem,
            }
            for f in valid_files
        ]
    }


def _run_one_job(
    *,
    client: InzytsAPIClient,
    label: str,
    csv_path: str,
    mode: str,
    title: str,
    dict_path: Optional[str],
    multi_file_input: Optional[Dict[str, Any]],
    analysis_mode: str,
    verbose: bool,
    timeout: int,
) -> TestResult:
    """Submit one analysis job, poll until done, build a TestResult.

    Shared body for the merged + sequential paths so the only difference
    between them is the payload-building step.
    """
    start_time = datetime.now()
    print(f"\n   📄 {label}")
    try:
        print("      📤 Submitting analysis job...")
        submit_response = client.submit_analysis(
            csv_path=csv_path,
            mode=mode,
            dict_path=dict_path,
            title=title,
            use_cache=False,
            multi_file_input=multi_file_input,
        )
        job_id = submit_response.get("job_id")
        if not job_id:
            raise Exception(f"No job_id in response: {submit_response}")
        print(f"      📋 Job ID: {job_id}")

        print("      ⏳ Waiting for job to complete...")
        final_status = client.wait_for_completion(job_id=job_id, timeout=timeout, verbose=verbose)
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        job_status = final_status.get("status", "unknown")
        result_path = final_status.get("result_path")
        error = final_status.get("error")
        token_usage = final_status.get("token_usage", {}) or {}
        tokens_used = token_usage.get("input", 0) + token_usage.get("output", 0)

        if job_status == "completed" and result_path:
            print(f"      ✅ SUCCESS: {label}")
            print(f"         Duration: {duration:.1f}s")
            return TestResult(
                dataset_name=label, success=True, start_time=start_time, end_time=end_time,
                duration_seconds=duration, job_id=job_id, notebook_path=result_path,
                tokens_used=tokens_used, analysis_mode=analysis_mode, job_status=job_status,
            )

        error_msg = error or f"Job ended with status: {job_status}"
        print(f"      ❌ FAILED: {label}")
        print(f"         Error: {error_msg}")
        return TestResult(
            dataset_name=label, success=False, start_time=start_time, end_time=end_time,
            duration_seconds=duration, job_id=job_id, error_message=error_msg,
            tokens_used=tokens_used, analysis_mode=analysis_mode, job_status=job_status,
        )

    except TimeoutError as e:
        end_time = datetime.now()
        print(f"      ⏰ TIMEOUT: {label}")
        return TestResult(
            dataset_name=label, success=False, start_time=start_time, end_time=end_time,
            duration_seconds=(end_time - start_time).total_seconds(),
            error_message=str(e), analysis_mode=analysis_mode, job_status="timeout",
        )
    except Exception as e:
        end_time = datetime.now()
        print(f"      ❌ FAILED: {label}")
        print(f"         Exception: {e}")
        if verbose:
            tb.print_exc()
        return TestResult(
            dataset_name=label, success=False, start_time=start_time, end_time=end_time,
            duration_seconds=(end_time - start_time).total_seconds(),
            error_message=str(e), analysis_mode=analysis_mode,
        )


def run_dataset_files_tests(
    dataset: DatasetConfig,
    client: InzytsAPIClient,
    verbose: bool = False,
    timeout: int = DEFAULT_TIMEOUT,
    merge: bool = False,
) -> List[TestResult]:
    """Run tests on all files within a dataset configuration."""
    valid_files = [f for f in dataset.files if f and Path(f).exists()]
    if not valid_files:
        print(f"\n{'='*60}\n🧪 Testing: {dataset.name}\n   Mode: {dataset.analysis_mode}\n   Status: No valid files found\n{'='*60}")
        return [TestResult(
            dataset_name=dataset.name, success=False,
            start_time=datetime.now(), end_time=datetime.now(), duration_seconds=0.0,
            error_message="No valid data files found", analysis_mode=dataset.analysis_mode,
        )]

    dict_path = dataset.data_dictionary if dataset.data_dictionary and Path(dataset.data_dictionary).exists() else None
    is_multi_file = merge or "multi-file" in dataset.analysis_mode.lower() or len(valid_files) > 1

    if is_multi_file and len(valid_files) > 1:
        print(f"\n{'='*60}\n🧪 Testing Dataset Group: {dataset.name} (MERGED)\n   Found {len(valid_files)} files to merge\n{'='*60}")
        return [_run_one_job(
            client=client,
            label=f"{dataset.name} (Merged)",
            csv_path=str(Path(valid_files[0]).resolve()),
            mode=dataset.api_mode,
            title=f"{dataset.name} (Merged)",
            dict_path=dict_path,
            multi_file_input=_build_multi_file_input(valid_files),
            analysis_mode=dataset.analysis_mode,
            verbose=verbose,
            timeout=timeout,
        )]

    print(f"\n{'='*60}\n🧪 Testing Dataset Group: {dataset.name}\n   Found {len(valid_files)} file(s)\n{'='*60}")
    return [
        _run_one_job(
            client=client,
            label=f"{dataset.name} ({Path(file_path).name})",
            csv_path=str(Path(file_path).resolve()),
            mode=dataset.api_mode,
            title=dataset.name,
            dict_path=dict_path,
            multi_file_input=None,
            analysis_mode=dataset.analysis_mode,
            verbose=verbose,
            timeout=timeout,
        )
        for file_path in valid_files
    ]


def run_tests(
    datasets: List[DatasetConfig],
    client: InzytsAPIClient,
    verbose: bool = False,
    dry_run: bool = False,
    skip_missing: bool = True,
    timeout: int = DEFAULT_TIMEOUT,
    merge: bool = False
) -> TestReport:
    """Run tests on multiple datasets."""
    report = TestReport()
    report.start_time = datetime.now()
    
    print(f"\n🚀 Running tests on {len(datasets)} dataset(s)...")
    
    for i, dataset in enumerate(datasets, 1):
        print(f"\n[{i}/{len(datasets)}] Processing: {dataset.name}")
        
        # Check file existence
        if skip_missing and (not dataset.primary_file or not Path(dataset.primary_file).exists()):
            print(f"⏭️  Skipping {dataset.name}: File not found")
            report.add_skipped()
            continue
        
        if dry_run:
            print(f"📋 [DRY RUN] Would test Group: {dataset.name}")
            valid_files = [f for f in dataset.files if f and Path(f).exists()]
            if merge or "multi-file" in dataset.analysis_mode.lower() or len(valid_files) > 1:
                 print(f"   MERGE: {len(valid_files)} files")
            for f in valid_files:
                print(f"   File: {Path(f).name}")
            continue
        
        # Run a test for EACH file in the dataset OR merged
        results_for_dataset = run_dataset_files_tests(dataset, client, verbose=verbose, timeout=timeout, merge=merge)
        for res in results_for_dataset:
            report.add_result(res)
    
    report.end_time = datetime.now()
    return report


def save_report(report: TestReport, output_path: Path):
    """Save test report to JSON file."""
    with open(output_path, 'w') as f:
        json.dump(report.to_dict(), f, indent=2)
    print(f"\n📁 Report saved: {output_path}")


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Inzyts Dataset Test Runner (API-Based)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Prerequisites:
  The Inzyts backend must be running:
    - Backend API at http://localhost:8000
    - Celery worker for background tasks
    - Redis for task queue

Examples:
  %(prog)s --list                        # List all datasets
  %(prog)s --dataset "Titanic"           # Run single dataset
  %(prog)s --mode "EDA"                  # Run all EDA datasets
  %(prog)s --all                         # Run all datasets
  %(prog)s --interactive                 # Interactive selection
  %(prog)s --all --dry-run               # Show what would run
        """
    )
    
    # Selection options
    selection = parser.add_argument_group("Selection Options")
    selection.add_argument(
        "--dataset", "-d",
        action="append",
        dest="datasets",
        help="Run specific dataset(s) by name (can be specified multiple times)"
    )
    selection.add_argument(
        "--mode", "-m",
        action="append",
        dest="modes",
        help="Run all datasets for specified mode(s) (EDA, Prediction, Forecasting, etc.)"
    )
    selection.add_argument(
        "--all", "-a",
        action="store_true",
        help="Run all datasets"
    )
    selection.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Interactive mode - select from menu"
    )
    
    # Display options
    display = parser.add_argument_group("Display Options")
    display.add_argument(
        "--list", "-l",
        action="store_true",
        help="List all available datasets"
    )
    display.add_argument(
        "--list-files",
        action="store_true",
        help="List datasets with file paths"
    )
    
    # Run options
    run_opts = parser.add_argument_group("Run Options")
    run_opts.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be tested without running"
    )
    run_opts.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )
    run_opts.add_argument(
        "--include-missing",
        action="store_true",
        help="Include datasets with missing files (they will fail)"
    )
    run_opts.add_argument(
        "--output", "-o",
        type=str,
        help="Output path for JSON test report"
    )
    run_opts.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help=f"Timeout in seconds per job (default: {DEFAULT_TIMEOUT})"
    )
    
    run_opts.add_argument(
        "--merge",
        action="store_true",
        help="Merge multiple files in a dataset group into a single analysis"
    )
    
    # API Configuration
    api_config = parser.add_argument_group("API Configuration")
    api_config.add_argument(
        "--api-url",
        type=str,
        default=DEFAULT_API_URL,
        help=f"Base URL for the Inzyts API (default: {DEFAULT_API_URL})"
    )
    
    # Authentication
    auth = parser.add_argument_group("Authentication")
    auth.add_argument(
        "--token",
        type=str,
        help="API Token (overrides INZYTS_API_TOKEN env var)"
    )
    
    # Configuration
    config = parser.add_argument_group("Configuration")
    config.add_argument(
        "--csv",
        type=str,
        default=str(SCRIPT_DIR / "inzyts_test_datasets.csv"),
        help="Path to dataset CSV file"
    )
    
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()
    
    # Load datasets
    csv_path = Path(args.csv)
    if not csv_path.exists():
        print(f"❌ Dataset CSV not found: {csv_path}")
        return 1
    
    datasets = load_datasets(csv_path)
    if not datasets:
        print("❌ No datasets found in CSV")
        return 1
    
    print(f"✅ Loaded {len(datasets)} datasets from {csv_path.name}")
    
    # Handle list commands
    if args.list or args.list_files:
        list_datasets(datasets, show_files=args.list_files)
        return 0
    
    # Determine which datasets to run
    selected: List[DatasetConfig] = []
    
    if args.interactive:
        selected = interactive_select(datasets)
    elif args.all:
        selected = datasets
    elif args.datasets:
        # Filter by name
        for name in args.datasets:
            for ds in datasets:
                if ds.name.lower() == name.lower():
                    selected.append(ds)
                    break
            else:
                print(f"⚠️  Dataset not found: {name}")
    elif args.modes:
        # Filter by mode category
        for mode in args.modes:
            mode_lower = mode.lower()
            for ds in datasets:
                if mode_lower in ds.mode_category.lower() or mode_lower in ds.analysis_mode.lower():
                    if ds not in selected:
                        selected.append(ds)
    
    if not selected:
        print("❌ No datasets selected. Use --help for options.")
        return 1
    
    print(f"\n📌 Selected {len(selected)} dataset(s) for testing")
    
    # Initialize API client
    token = args.token or os.environ.get("INZYTS_API_TOKEN")
    
    # Try loading from .env if not found
    if not token:
        env_path = PROJECT_ROOT / ".env"
        if env_path.exists():
            if args.verbose:
                print(f"📄 Loading .env from {env_path}")
            try:
                from dotenv import load_dotenv
                load_dotenv(env_path)
                token = os.environ.get("INZYTS_API_TOKEN")
            except ImportError:
                print("⚠️  dothevn not installed. Cannot load .env file.")
        elif args.verbose:
             print(f"⚠️  .env file not found at {env_path}")
            
    if not token:
        print("⚠️  WARNING: No API token found (INZYTS_API_TOKEN). Requests may fail.")
    elif args.verbose:
        print(f"🔑 API Token loaded (length: {len(token)})")
    
    client = InzytsAPIClient(
        base_url=args.api_url, 
        token=token,
        verbose=args.verbose
    )
    
    # Check if server is running (unless dry-run)
    if not args.dry_run:
        print(f"\n🔗 Checking API at {args.api_url}...")
        if not client.check_health():
            print(f"❌ Cannot connect to API at {args.api_url}")
            print("   Make sure the backend is running:")
            print("   - Start the backend: uvicorn src.server.main:app --reload")
            print("   - Start Celery worker: celery -A src.server.celery_app worker --loglevel=info")
            return 1
        print("✅ API is reachable")
    
    # Run tests
    report = run_tests(
        selected, 
        client, 
        verbose=args.verbose, 
        dry_run=args.dry_run, 
        skip_missing=not args.include_missing,
        timeout=args.timeout,
        merge=args.merge
    )
    
    if not args.dry_run:
        report.print_summary()
        
        # Save report
        if args.output:
            output_path = Path(args.output)
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = SCRIPT_DIR / f"test_report_{timestamp}.json"
        
        save_report(report, output_path)
    
    # Return exit code
    return 0 if report.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
