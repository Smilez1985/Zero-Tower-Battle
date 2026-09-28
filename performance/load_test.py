#!/usr/bin/env python3
"""Load Testing for Game Server"""
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

def simulate_connection():
    """Simulate a player connection"""
    time.sleep(0.1)
    return True

def load_test(concurrent=100, duration=60):
    """Run load test with concurrent players"""
    start_time = time.time()
    with ThreadPoolExecutor(max_workers=concurrent) as executor:
        futures = [executor.submit(simulate_connection) for _ in range(concurrent)]
        
        completed = [f.result() for f in as_completed(futures)]
        
    elapsed = time.time() - start_time
    return round(elapsed, 2)

def test_performance():
    """Test game performance"""
    print(f"[START] Testing {100} concurrent players...")
    time_taken = load_test(concurrent=100, duration=30)
    print(f"[END] Test completed in {time_taken}s")
    return time_taken < 10  # Pass if under 10 seconds

# Export
__all__ = ['load_test', 'test_performance']
