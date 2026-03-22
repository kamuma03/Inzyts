import requests
import time
import os
import pandas as pd
import json

# Configuration
API_URL = "http://localhost:8000/api/v2"
TEST_DIR = os.path.join(os.path.dirname(__file__), "..", "test_data_multifile")

def setup_data():
    if not os.path.exists(TEST_DIR):
        os.makedirs(TEST_DIR)
        
    # Create Customers.csv (Healthcare domain trigger)
    customers_path = os.path.join(TEST_DIR, "patients.csv")
    pd.DataFrame({
        "PatientID": [1, 2, 3, 4],
        "Name": ["Alice", "Bob", "Charlie", "David"],
        "Age": [30, 45, 50, 35]
    }).to_csv(customers_path, index=False)
    
    # Create Admissions.csv
    admissions_path = os.path.join(TEST_DIR, "admissions.csv")
    pd.DataFrame({
        "AdmissionID": [101, 102, 103, 104],
        "PatientID": [1, 2, 3, 1], # Patient 1 admitted twice
        "Admission Date": ["2023-01-01", "2023-02-01", "2023-03-01", "2023-04-01"],
        "Diagnosis": ["Flu", "Broken Leg", "Heart Attack", "Checkup"]
    }).to_csv(admissions_path, index=False)
    
    return customers_path, admissions_path

def test_multi_file_workflow():
    print(">>> Setting up test data...")
    p_path, a_path = setup_data()
    
    # 1. Upload Files (to get file info? In this system, user provides paths usually, 
    # but let's assume local path execution for now as per dev logic)
    # The API might expect the files to be accessible by the backend.
    # Since I am running this test on the same machine/container setup, local paths verify logic.
    
    print(">>> Submitting Multi-File Job...")
    
    # Construct MultiFileInput payload
    # Note: 'csv_path' is required as primary. We'll use patients.csv
    
    
    # Convert host paths to Docker container paths for the API request
    # usage: replace host cwd with /app
    cwd = os.getcwd()
    path_patient_docker = p_path.replace(cwd, "/app")
    path_admissions_docker = a_path.replace(cwd, "/app")
    
    payload = {
        "csv_path": "patients.csv", # This is handled by main path resolution, assuming relative to root or handle specially
        "multi_file_input": {
            "files": [
                {"file_path": path_patient_docker, "file_hash": "hash_patients", "description": "Patient demographics"},
                {"file_path": path_admissions_docker, "file_hash": "hash_admissions", "description": "Admission records"}
            ],
            "join_keys": [], # Auto-detect
            "domain": "healthcare"
        },
        "mode": "exploratory",
        "interactive": False
    }
    
    try:
        response = requests.post(f"{API_URL}/analyze", json=payload)
        response.raise_for_status()
        job_data = response.json()
        job_id = job_data["job_id"]
        print(f">>> Job Submitted: {job_id}")
    except Exception as e:
        print(f"!!! Submission Failed: {e}")
        if 'response' in locals():
            print(response.text)
        return

    # 2. Poll for status
    print(">>> Polling for completion...")
    max_retries = 60 # 60 seconds (mock LLM is fast, real LLM might be slow)
    for _ in range(max_retries):
        try:
            r = requests.get(f"{API_URL}/jobs/{job_id}")
            r.raise_for_status()
            status_data = r.json()
            status = status_data["status"]
            
            print(f"Status: {status}")
            
            if status == "completed":
                print(">>> Job Completed Successfully!")
                print(json.dumps(status_data, indent=2))
                
                # Check results
                verify_results(status_data)
                return
            elif status == "failed":
                print("!!! Job Failed")
                print(json.dumps(status_data, indent=2))
                return
                
            time.sleep(2)
        except Exception as e:
            print(f"!!! Polling Error: {e}")
            time.sleep(2)
            
    print("!!! Timeout waiting for job completion")

def verify_results(job_data):
    # Verify basics
    assert job_data["status"] == "completed"
    
    # If we had access to the notebook output path, we'd check it.
    # The API returns result_path
    result_path = job_data.get("result_path")
    if result_path and os.path.exists(result_path):
        print(f">>> Verified Notebook exists at: {result_path}")
    else:
        print(f"!!! Notebook not found at: {result_path}")

if __name__ == "__main__":
    test_multi_file_workflow()
