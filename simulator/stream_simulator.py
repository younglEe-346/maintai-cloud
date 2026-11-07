import time
import os
import pandas as pd
import requests

SERVER_URL = "http://localhost:8000/api/v1/mesures"
# Update this with your machine's API key generated in Swagger or Streamlit
MACHINE_API_KEY = "maint_YOUR_COPIED_KEY_HERE"

def generate_sample_data():
    return [
        {"air_temp": 300.1, "process_temp": 310.1, "rotational_speed": 1500, "torque": 40.0, "tool_wear": 120},
        {"air_temp": 300.2, "process_temp": 310.2, "rotational_speed": 1510, "torque": 42.0, "tool_wear": 122},
        {"air_temp": 300.5, "process_temp": 308.2, "rotational_speed": 2600, "torque": 68.5, "tool_wear": 215}, # Trigger row
        {"air_temp": 298.5, "process_temp": 309.0, "rotational_speed": 1480, "torque": 38.0, "tool_wear": 50},
        {"air_temp": 301.0, "process_temp": 311.5, "rotational_speed": 1490, "torque": 62.0, "tool_wear": 225}  # Trigger row
    ]

def start_stream(delay=1.0):
    print(f"Streaming telemetry to {SERVER_URL}...")
    headers = {"x-api-key": MACHINE_API_KEY, "Content-Type": "application/json"}
    
    count = 0
    sample_batch = generate_sample_data()
    
    while True:
        count += 1
        try:
            res = requests.post(SERVER_URL, json=sample_batch, headers=headers)
            print(f"[{count}] Status: {res.status_code} | Payload: {res.json()}")
        except Exception as e:
            print(f"[{count}] Connection Error: {e}")
        time.sleep(delay)

if __name__ == "__main__":
    start_stream()
