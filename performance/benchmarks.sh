#!/bin/bash
# Zero Tower Battle - Performance Benchmarks

# System Info
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "   ZERO TOWER BATTLE BENCHMARKS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo

# CPU Benchmarks
echo "📊 CPU PERFORMANCE:"
python3 -c "from benchmark import cpu_test, memory_test; print(f'CPU: {cpu_test()}ms')"
python3 -c "from benchmark import memory_test; print(f'Memory: {memory_test()}MB')"

# Load Test
echo
echo "📊 LOAD TESTS:"
python3 -c "
from concurrent.futures import ThreadPoolExecutor
from benchmark import load_test
with ThreadPoolExecutor(max_workers=10) as executor:
    results = executor.map(load_test, range(10))
    print(f'Concurrent Load: {sum(results)} ops')
"

