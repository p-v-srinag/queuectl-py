# queuectl: A CLI-based Background Job Queue
---

## Features
* **Persistent Jobs:** Uses SQLite to ensure jobs are not lost on restart.
* **Parallel Workers:** Run multiple worker processes to consume jobs concurrently.
* **Atomic Operations:** Safely picks jobs from the queue without race conditions.
* **Automatic Retries:** Failed jobs (non-zero exit) are retried automatically.
* **Exponential Backoff:** Implements a simple worker-side delay for retries.
* **Dead Letter Queue (DLQ):** Jobs that exhaust all retries are moved to the DLQ.
* **CLI Management:** All operations are managed via the `queuectl` command.

---

## Setup and Installation

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/p-v-srinag/queuectl-py.git](https://github.com/p-v-srinag/queuectl-py.git)
    cd queuectl-py
    ```

2.  **Create a virtual environment and install dependencies:**
    (Note: This project must be run from a non-cloud-synced folder, like `/tmp` or `~/dev`, to avoid SQLite database locking issues.)
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```

3.  **Install the CLI in "editable" mode:**
    ```bash
    pip install -e .
    ```

4.  **Verify installation:**
    ```bash
    queuectl --help
    ```

---

## Usage Examples (CLI Command Reference)

### 1. Enqueue a Job
```bash
queuectl enqueue '{"id":"job1", "command":"echo Hello World"}'
```
### 2. Manage Workers
```bash
# Start 3 worker processes
queuectl worker start --count 3

# Stop all running workers
queuectl worker stop
```
### 3. Check Status

```bash
queuectl status
```
### 4. List Jobs

```bash
# List pending jobs
queuectl list --state pending

# List completed jobs
queuectl list --state completed
```
### 5. Manage the Dead Letter Queue (DLQ)

```bash
# List all jobs in the DLQ
queuectl dlq list

# Retry a specific job from the DLQ
queuectl dlq retry job1
```
### 6. Configuration

```bash
# Set max retries to 5
queuectl config set max_retries 5

# Show the current configuration
queuectl config show
```
### Architecture Overview

"Job Lifecycle"

A job progresses through the following states: PENDING -> PROCESSING -> ( COMPLETED | FAILED)                
If FAILED, it retries: FAILED -> PENDING If all retries are exhausted: FAILED -> DEAD (moved to DLQ)

### Data Persistence

* Database: All job and configuration data is stored in a .queuectl_data folder created within the project directory.

* Storage: SQLite is used for the queue.db file. This provides robust, persistent storage and, critically, the ability to perform atomic, locked transactions.

* Config: config.json stores retry and backoff settings.

### Worker Logic & Concurrency

* Process Management: Workers are started as background processes using os.fork(). Their PIDs are tracked in a .pid file for graceful shutdown (SIGTERM).

* Concurrency Control (Locking): To prevent multiple workers from grabbing the same job (a race condition), the system uses SQLite's transactional locking. A worker requests an IMMEDIATE lock, atomically selects the next pending job, and updates its state to PROCESSING before releasing the lock.

* Connection Handling: To prevent os.fork() from sharing a stale database connection, the main process closes its connection, and each child worker process creates its own fresh connection.

### Assumptions & Trade-offs
* SQLite: Chosen over a JSON file for its superior handling of persistence, concurrency, and atomic transactions, which is essential for preventing race conditions.

* os.fork(): Used for simplicity in creating worker processes. This works well on Unix-like systems (macOS/Linux) but is not portable to Windows (which would require using the multiprocessing module).

* Backoff: The retry backoff is a simple time.sleep() in the worker after a failed job. A more robust system might use a run_at timestamp and put the job back in the queue, so the worker isn't blocked.

* File Location: The system must be run from a local, non-cloud-synced directory (e.g., /tmp or ~/dev). Cloud-sync services (iCloud, Google Drive) interfere with SQLite's file-locking mechanism, causing disk I/O errors.

### Testing Instructions
There are two ways to test the system:

* 1. Automated Test Script

The included test_flow.sh script runs a full end-to-end test of the job lifecycle.

```bash
# First, make the script executable
chmod +x test_flow.sh

# Run the test
./test_flow.sh
```
* 2. Manual Demo Walkthrough

This is the recommended script for a manual demonstration. Run these commands one by one.

Step 1: Reset the Environment

```bash
queuectl worker stop
rm .queuectl_data/queue.db
```
Step 2: Show Initial Status

```bash
queuectl status
```
Step 3: Configure Retries

```bash
queuectl config set max_retries 2
queuectl config show
```
Step 4: Enqueue Jobs

```bash
queuectl enqueue '{"id": "job-good", "command": "echo GOOD JOB RAN && sleep 2"}'
queuectl enqueue '{"id": "job-fail", "command": "echo FAILED JOB RAN && ls /nonexistent-file"}'
```
Step 5: List Pending Jobs

```bash
queuectl list --state pending
```
Step 6: Start Workers

```bash
queuectl worker start --count 2
```
Step 7: Watch the Jobs Run (Wait ~10 seconds. You will see worker output in your terminal as they process, fail, and retry.)

Step 8: Check Final Status

```bash
queuectl status
```
Step 9: List Completed Jobs

```bash
queuectl list --state completed
```
Step 10: Manage the Dead Letter Queue (DLQ)

```bash
queuectl dlq list
```
Step 11: Retry a DLQ Job

```bash
queuectl dlq retry job-fail
```
Step 12: Show Final State (The workers will immediately pick up the retried job and process it.) (Wait ~10 seconds for it to fail again and move back to the DLQ.)

```bash
queuectl dlq list
queuectl list --state pending
```
Step 13: Stop the Workers

```bash
queuectl worker stop
```
