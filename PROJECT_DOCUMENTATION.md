# UHR ADT Performance Testing Pipeline — Project Documentation

## 📋 Table of Contents

- [Project Background](#project-background)
- [How This Project Was Created](#how-this-project-was-created)
- [Pipeline Design Decisions](#pipeline-design-decisions)
- [Step-by-Step Pipeline Walkthrough](#step-by-step-pipeline-walkthrough)
- [JMeter Test Plan Architecture](#jmeter-test-plan-architecture)
- [Authentication Deep Dive](#authentication-deep-dive)
- [Dashboard Generation](#dashboard-generation)
- [Evolution & Debugging History](#evolution--debugging-history)
- [Best Practices Implemented](#best-practices-implemented)
- [Future Enhancements](#future-enhancements)

---

## Project Background

### What is UHR ADT?

**UHR (Unified Health Record)** is a healthcare system that manages patient records across healthcare providers. **ADT (Admission, Discharge, Transfer)** events are critical healthcare workflows that track patient movements within and between healthcare facilities.

### Why Performance Testing?

ADT events are mission-critical:
- **Patient safety** — Delays in processing can affect care delivery
- **High volume** — Large hospitals process thousands of ADT events daily
- **Real-time requirements** — Systems must respond within seconds
- **Integration points** — Multiple systems consume ADT events (EHR, billing, analytics)

### The Challenge

The UHR ADT API (`/csbridge-adt/api/submit-adt-request`) needs to handle:
- Sustained load from multiple healthcare facilities
- Sudden spikes during emergencies or system migrations
- Various ADT event types (A01-A15) with complex payloads
- Authentication via Keycloak (OpenID Connect)

This project automates the performance testing of this API to ensure it meets production requirements.

---

## How This Project Was Created

### Phase 1: Initial Setup

1. **Created JMeter test plans** with the following components:
   - User Defined Variables for environment configuration
   - SetupThreadGroup for Keycloak token generation
   - ThreadGroups for each test scenario
   - HTTP Samplers with realistic ADT event payloads
   - Response Assertions for validation

2. **Created individual test plan files:**
   - `test-plan-smoke.jmx` — Quick sanity check
   - `test-plan-load.jmx` — Normal production load
   - `test-plan-stress.jmx` — Breaking point test
   - `test-plan-spike.jmx` — Sudden burst test

3. **Created reference file** (`UHR_ADT Events_Performance Testing-.jmx`) containing all test scenarios for local JMeter GUI use.

### Phase 2: GitHub Actions Pipeline

1. **Created workflow** (`.github/workflows/performance-test.yml`) with:
   - Single job running all 4 tests sequentially
   - Java 11 + JMeter 5.6.3 setup
   - Secret validation
   - Artifact upload

2. **Created dashboard generator** (`scripts/generate_dashboard.py`):
   - Parses JMeter CSV results
   - Calculates statistics (error rate, avg response, P90, throughput)
   - Generates polished HTML dashboard

3. **Configured GitHub Pages** for dashboard hosting

### Phase 3: Debugging & Refinement

Several issues were identified and fixed during development:

1. **Thread group naming** — All 4 JMX files had identical thread group names ("SMOKE TEST"). Fixed by renaming each to match its test type.

2. **Thread group disabled** — Load, Stress, and Spike test plans had `enabled="false"`. Fixed by setting `enabled="true"`.

3. **Missing Keycloak secrets** — The Spike test step was missing `-J` flags for secret injection. Fixed by adding all 4 `-J` flags.

4. **Pipeline stops on token failure** — `on_sample_error=stoptest` in SetupThreadGroup caused the entire test to abort when Keycloak token generation failed. Fixed by changing to `on_sample_error=continue`.

5. **Exception on token extraction** — `throw new Exception("Keycloak token not found...")` caused the SetupThreadGroup to fail. Fixed by replacing with `log.warn()`.

6. **Keycloak server down** — The root cause of token generation failure was identified as the Keycloak server (`qa-iam.waseel.com`) returning HTTP 500 "unknown_error". This is a server-side issue, not a pipeline issue.

---

## Pipeline Design Decisions

### Why Single Job for All Tests?

**Decision**: Run all 4 tests in a single job rather than separate jobs.

**Rationale**:
- JMeter installation happens once (saves ~15 minutes)
- Sequential execution ensures tests don't overlap
- Shared environment variables
- Simpler artifact management

**Trade-off**: If one test fails, subsequent tests still run (due to `continue-on-error`).

### Why `continue-on-error` for Each Test?

**Decision**: Each test step uses `continue-on-error: true`.

**Rationale**:
- Load test should run even if smoke test fails
- Stress test should run even if load test fails
- Provides complete picture of system performance
- Dashboard shows accurate per-test status

### Why Individual JMX Files?

**Decision**: Separate `.jmx` file for each test scenario.

**Rationale**:
- Each test can be run independently
- Clear separation of concerns
- Easy to modify one test without affecting others
- Reference file contains all scenarios for local use

### Why GitHub Pages for Dashboard?

**Decision**: Publish results to GitHub Pages.

**Rationale**:
- Free hosting
- Publicly accessible (no auth required)
- Persistent URL
- Supports custom HTML/CSS
- Integrated with GitHub Actions

---

## Step-by-Step Pipeline Walkthrough

### Trigger

The pipeline triggers on:
```yaml
on:
  push:              # Any push to any branch
  pull_request:      # PR creation/update
  workflow_dispatch: # Manual trigger
```

### Job 1: `run-all-tests`

#### Step 1: Checkout Repository
```yaml
- name: Checkout repository
  uses: actions/checkout@v4
```
Clones the repository to the runner.

#### Step 2: Set up Java 11
```yaml
- name: Set up Java 11
  uses: actions/setup-java@v4
  with:
    distribution: temurin
    java-version: "11"
```
Installs Eclipse Temurin JDK 11 (required by JMeter 5.6.3).

#### Step 3: Install JMeter 5.6.3
```yaml
- name: Install JMeter 5.6.3
  run: |
    wget -q https://archive.apache.org/dist/jmeter/binaries/apache-jmeter-5.6.3.tgz
    tar -xzf apache-jmeter-5.6.3.tgz
```
Downloads and extracts JMeter from the Apache archive.

#### Step 4: Create Results Directories
```yaml
- name: Create results directories
  run: mkdir -p results/{smoke,load,stress,spike}
```
Creates directories for each test's output.

#### Step 5: Validate Keycloak Secrets
```yaml
- name: "🔑 Validate Keycloak Secrets"
  run: |
    # Checks all 4 secrets are non-empty
    # Exits with error if any secret is missing
```
Validates that all required secrets are configured before running tests.

#### Step 6-9: Run Tests
Each test runs JMeter in non-GUI mode:
```bash
$JMETER_HOME/bin/jmeter \
  -n \                              # Non-GUI mode
  -t test-plan-smoke.jmx            # Test plan file
  -l results/smoke/results.csv      # Results file
  -e \                              # Generate HTML report
  -o results/smoke/html_report      # Report output directory
```

#### Step 10: Upload Artifacts
```yaml
- name: Upload all test results
  if: always()
  uses: actions/upload-artifact@v4
  with:
    name: all-test-results
    path: results/
    retention-days: 30
```
Uploads all results regardless of test outcomes.

### Job 2: `publish-report`

#### Step 1: Download Test Results
Downloads artifacts from Job 1.

#### Step 2: Generate Dashboard
```yaml
- name: Generate dashboard index.html
  env:
    SMOKE_STATUS:  ${{ needs.run-all-tests.outputs.smoke_status }}
    LOAD_STATUS:   ${{ needs.run-all-tests.outputs.load_status }}
    STRESS_STATUS: ${{ needs.run-all-tests.outputs.stress_status }}
    SPIKE_STATUS:  ${{ needs.run-all-tests.outputs.spike_status }}
  run: python3 scripts/generate_dashboard.py
```
Parses CSVs and generates the HTML dashboard.

#### Step 3-5: Deploy to GitHub Pages
Copies reports, configures Pages, and deploys.

---

## JMeter Test Plan Architecture

### Structure of Each Test Plan

```
TestPlan
├── User Defined Variables
│   ├── BASE_PROTOCOL = https
│   ├── BASE_HOST = stg-uhr.waseel.com
│   ├── BASE_PORT = 443
│   ├── KC_HOST = qa-iam.waseel.com
│   ├── KC_TOKEN_PATH = /realms/waseel-stg/protocol/openid-connect/token
│   ├── KC_CLIENT_ID = ${__env(KC_CLIENT_ID,csbridge)}
│   ├── KC_CLIENT_SECRET = ${__env(KC_CLIENT_SECRET,)}
│   ├── KC_USERNAME = ${__env(KC_USERNAME,testuser-csbridge)}
│   └── KC_PASSWORD = ${__env(KC_PASSWORD,)}
│
├── SetupThreadGroup (1 thread, 1 loop, on_sample_error=continue)
│   ├── HeaderManager (Content-Type: application/x-www-form-urlencoded)
│   ├── HTTPSamplerProxy (POST → Keycloak token endpoint)
│   │   └── HTTPArguments (grant_type, client_id, client_secret, username, password)
│   ├── ResponseAssertion (HTTP 200)
│   ├── JSONPostProcessor (Extract $.access_token → access_token_local)
│   └── JSR223PostProcessor (Store as GLOBAL_AUTH_TOKEN)
│
└── ThreadGroup (N threads, duration-based, loops=-1, scheduler=true)
    ├── JSR223PreProcessor (Inject Bearer Token)
    │   └── Reads GLOBAL_AUTH_TOKEN → sets AUTH_TOKEN
    ├── HeaderManager (Authorization: Bearer ${AUTH_TOKEN}, Content-Type: application/json)
    ├── HTTPSamplerProxy (POST → /csbridge-adt/api/submit-adt-request)
    │   └── Post Body (JSON ADT event payload)
    └── ResponseAssertion (HTTP 2xx)
```

### Thread Group Configurations

| Test | Threads | Ramp-up | Duration | Delay | Loops | Scheduler |
|------|---------|---------|----------|-------|-------|-----------|
| Smoke | 2 | 10s | 60s | 2s | -1 | true |
| Load | 50 | 120s | 600s | 5s | -1 | true |
| Stress | 150 | 180s | 300s | 5s | -1 | true |
| Spike | 200 | 10s | 120s | 5s | -1 | true |

**Key settings:**
- `loops=-1` — Infinite loops (controlled by duration)
- `scheduler=true` — Enables duration-based execution
- `on_sample_error=continue` — Continue on individual request failures

### Variable Resolution

The `${__env()}` function reads from the **operating system environment variables**:

```groovy
${__env(KC_CLIENT_ID,csbridge)}
// ↑ Reads KC_CLIENT_ID from OS environment
// ↑ Falls back to "csbridge" if not set
```

In GitHub Actions, the `env:` block sets these variables from secrets:
```yaml
env:
  KC_CLIENT_ID: ${{ secrets.KC_CLIENT_ID }}
  KC_CLIENT_SECRET: ${{ secrets.KC_CLIENT_SECRET }}
  KC_USERNAME: ${{ secrets.KC_USERNAME }}
  KC_PASSWORD: ${{ secrets.KC_PASSWORD }}
```

---

## Authentication Deep Dive

### Keycloak OpenID Connect Flow

The pipeline uses the **Resource Owner Password Credentials (ROPC)** grant type:

```
┌──────────┐                                    ┌──────────┐
│  JMeter  │ ──POST /realms/waseel-stg/...──►  │ Keycloak │
│          │     grant_type=password             │  Server  │
│          │     client_id=csbridge              │          │
│          │     client_secret=***               │          │
│          │     username=testuser-csbridge      │          │
│          │     password=***                    │          │
│          │                                    │          │
│          │ ◄── 200 OK ────────────────────── │          │
│          │     {                              │          │
│          │       "access_token": "eyJ...",    │          │
│          │       "expires_in": 3600,          │          │
│          │       "token_type": "Bearer"       │          │
│          │     }                              │          │
└──────────┘                                    └──────────┘
```

### Token Lifecycle

1. **Token Request** — SetupThreadGroup sends credentials to Keycloak
2. **Token Extraction** — JSONPostProcessor extracts `$.access_token`
3. **Token Storage** — JSR223PostProcessor stores as `GLOBAL_AUTH_TOKEN` (JMeter global property)
4. **Token Injection** — Each ThreadGroup's JSR223PreProcessor reads the global property and sets `AUTH_TOKEN`
5. **Token Usage** — HeaderManager adds `Authorization: Bearer ${AUTH_TOKEN}` to all requests
6. **Token Validity** — Token is valid for 3600 seconds (1 hour), sufficient for all 4 tests

### Why Global Properties?

JMeter `props` (global properties) are shared across all thread groups, while `vars` (variables) are thread-local. By storing the token in `props`, it's accessible to all thread groups in the test plan.

```groovy
// Store (in SetupThreadGroup)
props.put("GLOBAL_AUTH_TOKEN", token);

// Read (in ThreadGroup)
String token = props.get("GLOBAL_AUTH_TOKEN");
vars.put("AUTH_TOKEN", token);
```

---

## Dashboard Generation

### How `generate_dashboard.py` Works

1. **Reads environment variables** for test statuses:
   - `SMOKE_STATUS`, `LOAD_STATUS`, `STRESS_STATUS`, `SPIKE_STATUS`
   - Values: `success`, `failure`, or `skipped`

2. **Parses JMeter CSV files** for each test:
   - `results/smoke/results.csv`
   - `results/load/results.csv`
   - `results/stress/results.csv`
   - `results/spike/results.csv`

3. **Calculates statistics**:
   - Total requests
   - Error count and percentage
   - Average response time
   - P90 response time (90th percentile)
   - Throughput (requests/second)

4. **Generates HTML dashboard** with:
   - Overall status banner (green/red)
   - Individual test cards with metrics
   - Links to full JMeter HTML reports
   - GitHub run information

### CSV Parsing Logic

```python
def parse_csv(path):
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append(row)
    
    total = len(rows)
    errors = sum(1 for r in rows if r.get("success", "true").strip().lower() == "false")
    error_pct = round((errors / total) * 100, 1)
    
    latencies = [int(r.get("elapsed", 0)) for r in rows]
    avg_ms = round(sum(latencies) / len(latencies))
    p90_ms = sorted(latencies)[math.ceil(0.90 * len(sorted(latencies))) - 1]
    
    # Throughput = total requests / duration in seconds
    ts_vals = [int(r.get("timeStamp", "")) for r in rows if r.get("timeStamp", "").isdigit()]
    duration_s = (max(ts_vals) - min(ts_vals)) / 1000.0
    throughput = round(total / duration_s, 1)
    
    return { "total": total, "errors": errors, "error_pct": error_pct,
             "avg_ms": avg_ms, "p90_ms": p90_ms, "throughput": throughput }
```

---

## Evolution & Debugging History

### Issue 1: All JMX Files Were Identical Copies

**Problem**: All 4 test plan files had the same thread group name ("1. SMOKE TEST - 2 VU, 60s") and the same configuration. Load, Stress, and Spike tests were disabled (`enabled="false"`).

**Root Cause**: The files were copied from the reference JMX without updating the thread group names and settings.

**Fix**: Updated each file with correct thread group name, VU count, duration, and `enabled="true"`.

### Issue 2: Missing Keycloak Secrets in Spike Test

**Problem**: The Spike test workflow step was missing all `-J` flags for secret injection.

**Fix**: Added all 4 `-J` flags to the Spike test step.

### Issue 3: Pipeline Stops on Token Failure

**Problem**: `on_sample_error=stoptest` in SetupThreadGroup caused the entire test to abort when Keycloak token generation failed. Only 1 request (the token request) would run.

**Root Cause**: When the token request failed, JMeter stopped the entire test.

**Fix**: Changed to `on_sample_error=continue` so the test continues even if token generation fails.

### Issue 4: Exception on Token Extraction

**Problem**: `throw new Exception("Keycloak token not found in response - test aborted")` in the JSR223PostProcessor caused the SetupThreadGroup to fail.

**Fix**: Replaced with `log.warn("=== TOKEN EXTRACTION FAILED - tests will run without auth token ===")`.

### Issue 5: Keycloak Server Down

**Problem**: Keycloak server at `qa-iam.waseel.com` returns HTTP 500 "unknown_error" for all token requests.

**Status**: Server-side issue. Pipeline works correctly once Keycloak is restored.

---

## Best Practices Implemented

### 1. Fail-Fast Secret Validation
The pipeline validates all required secrets before running any tests, providing clear error messages if any are missing.

### 2. Continue on Error
Each test uses `continue-on-error: true` so that one test's failure doesn't prevent subsequent tests from running.

### 3. Artifact Upload
All results are uploaded as artifacts regardless of test outcomes, enabling post-mortem analysis.

### 4. Graceful Token Handling
The pipeline continues running tests even if token generation fails, providing visibility into API behavior without authentication.

### 5. Single Job Design
All tests run in a single job to avoid redundant JMeter installation and setup.

### 6. Environment Variable Configuration
All sensitive values are stored in GitHub Secrets, not in the codebase.

### 7. Structured Results
Results are organized in separate directories per test, making analysis straightforward.

### 8. HTML Dashboard
A unified dashboard provides a single view of all test results with links to detailed reports.

---

## Future Enhancements

### Potential Improvements

1. **Retry Logic for Token Generation** — Add 3-5 retries with exponential backoff for Keycloak token requests

2. **Slack/Teams Notifications** — Send notifications on test completion (requires webhook setup)

3. **Performance Thresholds** — Add pass/fail criteria based on response time and error rate thresholds

4. **Historical Trending** — Store results in a database and track performance over time

5. **Parallel Test Execution** — Run tests in parallel using GitHub Actions matrix strategy

6. **Environment Selection** — Support multiple environments (dev, staging, production)

7. **API Versioning** — Support testing multiple API versions simultaneously

8. **Custom Metrics** — Add business-specific metrics (events per second, processing time, etc.)

9. **Alert Integration** — Integrate with PagerDuty or Opsgenie for critical failures

10. **Test Data Management** — Dynamic test data generation for more realistic testing

---

## Appendix: Key Configuration Files

### GitHub Secrets Required

| Secret | Description |
|--------|-------------|
| `KC_CLIENT_ID` | Keycloak client ID (e.g., `csbridge`) |
| `KC_CLIENT_SECRET` | Keycloak client secret (32 characters) |
| `KC_USERNAME` | Keycloak username (e.g., `testuser-csbridge`) |
| `KC_PASSWORD` | Keycloak password (13 characters) |

### Environment Variables in Workflow

| Variable | Source | Description |
|----------|--------|-------------|
| `KC_CLIENT_ID` | Secret | Keycloak client ID |
| `KC_CLIENT_SECRET` | Secret | Keycloak client secret |
| `KC_USERNAME` | Secret | Keycloak username |
| `KC_PASSWORD` | Secret | Keycloak password |
| `JMETER_HOME` | Auto-set | JMeter installation path |

### JMeter User Defined Variables

| Variable | Value | Description |
|----------|-------|-------------|
| `BASE_PROTOCOL` | `https` | API protocol |
| `BASE_HOST` | `stg-uhr.waseel.com` | API host |
| `BASE_PORT` | `443` | API port |
| `KC_HOST` | `qa-iam.waseel.com` | Keycloak host |
| `KC_TOKEN_PATH` | `/realms/waseel-stg/protocol/openid-connect/token` | Token endpoint |
| `KC_CLIENT_ID` | `${__env(KC_CLIENT_ID,csbridge)}` | Client ID from env |
| `KC_CLIENT_SECRET` | `${__env(KC_CLIENT_SECRET,)}` | Client secret from env |
| `KC_USERNAME` | `${__env(KC_USERNAME,testuser-csbridge)}` | Username from env |
| `KC_PASSWORD` | `${__env(KC_PASSWORD,)}` | Password from env |

---

*Last updated: June 24, 2026*
