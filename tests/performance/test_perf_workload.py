
import requests
import time

BASE_URL = "http://localhost:5000/api"
CSV_FILENAME = "airline_passenger_satisfaction.csv"
QUESTION = "What are the primary drivers of passenger satisfaction?"

def run_performance_test():
    print(f"Starting performance test with {CSV_FILENAME}...")
    
    # 1. Start Analysis
    payload = {
        "csv_path": CSV_FILENAME,
        "question": QUESTION,
        "pipeline_mode": "exploratory"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/analyze", json=payload)
        response.raise_for_status()
        job_id = response.json().get("job_id")
        print(f"Job started: {job_id}")
    except Exception as e:
        print(f"Failed to start analysis: {e}")
        return

    # 2. Poll Status
    start_time = time.time()
    while True:
        try:
            status_resp = requests.get(f"{BASE_URL}/status/{job_id}")
            status_data = status_resp.json()
            
            state = status_data.get("status")
            print(f"Status: {state} | Time elapsed: {time.time() - start_time:.1f}s")
            
            if state in ["completed", "failed"]:
                break
                
            time.sleep(2)
        except Exception as e:
            print(f"Polling error: {e}")
            break

    print(f"Test finished. Final status: {state}")

if __name__ == "__main__":
    run_performance_test()
