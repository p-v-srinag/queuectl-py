# This is the full content for test_flow.sh
#!/bin/bash

# A simple script to validate the core flow of queuectl

echo "--- 1. Resetting environment ---"
# Stop any old workers
queuectl worker stop
# Remove old database
# This new path is inside your project folder
rm -f ./.queuectl_data/queue.db
sleep 1 # Give time for file handles to close

echo "\n--- 2. Checking initial status (should be empty) ---"
queuectl status

echo "\n--- 3. Setting config ---"
queuectl config set max_retries 2   # <-- FIX: Use underscore
queuectl config set backoff_base 1   # <-- FIX: Use underscore
queuectl config show

echo "\n--- 4. Enqueuing jobs ---"
queuectl enqueue '{"id": "job-good", "command": "echo GOOD JOB && sleep 1"}'
queuectl enqueue '{"id": "job-bad", "command": "echo BAD JOB && ls /nonexistent-file"}'
queuectl enqueue '{"id": "job-long", "command": "echo LONG JOB && sleep 3"}'

echo "\n--- 5. Listing pending jobs ---"
queuectl list --state pending

echo "\n--- 6. Starting workers ---"
queuectl worker start --count 2
sleep 1 # Give workers time to start

echo "\n--- 7. Monitoring status (waiting for jobs to clear) ---"
# Wait for jobs to finish (max 15 seconds)
for i in {1..15}; do
    echo "Checking status (second $i)..."
    
    # FIX: Use grep -i (case-insensitive) and fix grep -v logic
    pending_count=$(queuectl status | grep -i -E "(pending|processing|failed):" | grep -v ": *0$" | wc -l)
    
    if [ "$pending_count" -eq "0" ]; then
        echo "All jobs processed."
        break
    fi
    sleep 1
done

echo "\n--- 8. Stopping workers ---"
queuectl worker stop
sleep 1
queuectl status

echo "\n--- 9. Checking final state ---"
echo "\n[COMPLETED JOBS]"
queuectl list --state completed
echo "\n[DEAD LETTER QUEUE]"
queuectl list --state dead

echo "\n--- 10. Retrying DLQ job ---"
queuectl dlq retry job-bad
echo "\n[DLQ after retry]"
queuectl dlq list
echo "\n[PENDING after retry]"
queuectl list --state pending

echo "\n--- 11. Final test flow complete ---"