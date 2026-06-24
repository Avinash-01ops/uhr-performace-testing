# UHR ADT Events — Performance Testing Pipeline

## 📋 Table of Contents

- [Overview](#overview)
- [What It Does](#what-it-does)
- [Architecture](#architecture)
- [Test Plans](#test-plans)
- [Authentication Flow](#authentication-flow)
- [Pipeline Jobs](#pipeline-jobs)
- [Prerequisites](#prerequisites)
- [Setup & Configuration](#setup--configuration)
- [Running the Pipeline](#running-the-pipeline)
- [Understanding Results](#understanding-results)
- [Project Structure](#project-structure)
- [Troubleshooting](#troubleshooting)

---

## Overview

This project is a **fully automated performance testing pipeline** for the **UHR ADT Events API** — a healthcare system that processes ADT (Admission, Discharge, Transfer) events. The pipeline uses **Apache JMeter** to simulate real-world traffic and measures system performance under various load conditions.

The pipeline runs on **GitHub Actions** and publishes results to **GitHub Pages** as a polished HTML dashboard.

### Key Technologies

| Component | Technology |
|-----------|-----------|
| Load Testing | Apache JMeter 5.6.3 |
| CI/CD | GitHub Actions |
| Authentication | Keycloak (OpenID Connect) |
| Dashboard | Python (custom HTML generator) |
| Hosting | GitHub Pages |
| Language | Java 11 (for JMeter runtime) |

---

## What It Does

### Performance Testing Scenarios

The pipeline runs **4 sequential test scenarios**, each designed to validate a different aspect of system performance:

| Test | Virtual Users | Duration | Purpose |
|------|:---:|----------|---------|
| 🔵 **Smoke Test** | 2 | 60 seconds | Quick sanity check — validates basic connectivity and authentication |
| 🟡 **Load Test** | 50 | 10 minutes | Simulates normal production traffic volume |
| 🟠 **Stress Test** | 150 | 5 minutes | Pushes the system beyond normal load to find the breaking point |
| 🔴 **Spike Test** | 200 | 2 minutes | Simulates a sudden burst of traffic — measures system recovery |

### What Gets Measured

- **Total Requests** — Number of API calls made during the test
- **Error Rate** — Percentage of failed requests
- **Average Response Time** — Mean latency in milliseconds
- **P90 Response Time** — 90th percentile latency (90% of requests are faster than this)
- **Throughput** — Requests per second

### What Gets Produced

1. **Raw JMeter Results** (CSV + HTML reports) — downloadable as artifacts
2. **Unified HTML Dashboard** — published to GitHub Pages with summary of all tests
3. **Per-test JMeter Reports** — detailed breakdowns accessible from the dashboard

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     GitHub Actions Workflow                      │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  JOB 1: run-all-tests                                     │   │
│  │                                                            │   │
│  │  1. Checkout code                                          │   │
│  │  2. Set up Java 11                                         │   │
│  │  3. Install JMeter 5.6.3                                   │   │
│  │  4. Validate Keycloak secrets                              │   │
│  │  5. Run Smoke Test  (2 VU,  60s)                          │   │
│  │  6. Run Load Test   (50 VU,  10min)                        │   │
│  │  7. Run Stress Test (150 VU, 5min)                         │   │
│  │  8. Run Spike Test  (200 VU, 2min)                         │   │
│  │  9. Upload results as artifacts                            │   │
│  └───────────────────────┬──────────────────────────────────┘   │
│                          │ depends on                            │
│  ┌───────────────────────▼──────────────────────────────────┐   │
│  │  JOB 2: publish-report                                     │   │
│  │                                                            │   │
│  │  1. Download test results                                  │   │
│  │  2. Parse CSVs & generate dashboard (generate_dashboard.py)│   │
│  │  3. Copy JMeter HTML sub-reports                           │   │
│  │  4. Deploy to GitHub Pages                                 │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                     Test Plan Architecture (per JMX)             │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  User Defined Variables                                    │   │
│  │  • BASE_PROTOCOL=https    • BASE_HOST=stg-uhr.waseel.com  │   │
│  │  • KC_HOST=qa-iam.waseel.com                              │   │
│  │  • KC_TOKEN_PATH=/realms/waseel-stg/protocol/openid-...   │   │
│  │  • KC_CLIENT_ID, KC_CLIENT_SECRET, KC_USERNAME, KC_PASS   │   │
│  └──────────────────────────────────────────────────────────┘   │
│                          │                                        │
│  ┌───────────────────────▼──────────────────────────────────┐   │
│  │  SetupThreadGroup (1 thread, 1 loop)                      │   │
│  │  ┌────────────────────────────────────────────────────┐   │   │
│  │  │  HeaderManager: Content-Type: application/x-www-...│   │   │
│  │  │  HTTP POST → Keycloak Token Endpoint               │   │   │
│  │  │  Body: grant_type=password&client_id=...&...        │   │   │
│  │  │  ResponseAssertion: HTTP 200                        │   │   │
│  │  │  JSONPostProcessor: Extract $.access_token          │   │   │
│  │  │  JSR223PostProcessor: Store as GLOBAL_AUTH_TOKEN    │   │   │
│  │  └────────────────────────────────────────────────────┘   │   │
│  └──────────────────────────────────────────────────────────┘   │
│                          │                                        │
│  ┌───────────────────────▼──────────────────────────────────┐   │
│  │  ThreadGroup (N threads, duration-based)                  │   │
│  │  ┌────────────────────────────────────────────────────┐   │   │
│  │  │  JSR223PreProcessor: Inject Bearer Token            │   │   │
│  │  │  HeaderManager: Authorization: Bearer ${AUTH_TOKEN} │   │   │
│  │  │  HTTP POST → /csbridge-adt/api/submit-adt-request   │   │   │
│  │  │  Body: JSON payload (ADT event data)                │   │   │
│  │  │  ResponseAssertion: HTTP 2xx                         │   │   │
│  │  └────────────────────────────────────────────────────┘   │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Test Plans

Each test plan is a separate JMeter `.jmx` file with a single thread group configured for a specific load profile:

### `test-plan-smoke.jmx`
- **2 Virtual Users**, **60 seconds** duration
- **Purpose**: Quick validation that the system is reachable and responding
- **Ramp-up**: 10 seconds
- **Use case**: Run first to verify basic connectivity before heavier tests

### `test-plan-load.jmx`
- **50 Virtual Users**, **10 minutes** duration
- **Purpose**: Simulate normal production traffic
- **Ramp-up**: 120 seconds (gradual increase)
- **Use case**: Measure system behavior under expected daily load

### `test-plan-stress.jmx`
- **150 Virtual Users**, **5 minutes** duration
- **Purpose**: Find the system's breaking point
- **Ramp-up**: 180 seconds (gradual increase to avoid thundering herd)
- **Use case**: Identify performance degradation and maximum capacity

### `test-plan-spike.jmx`
- **200 Virtual Users**, **2 minutes** duration
- **Purpose**: Simulate sudden traffic burst (e.g., flash sale, emergency)
- **Ramp-up**: 10 seconds (sudden spike)
- **Use case**: Test system recovery and resilience under extreme load

### Reference File: `UHR_ADT Events_Performance Testing-.jmx`
- Contains **all 4 thread groups** in a single file (for local JMeter GUI use)
- Only the Smoke Test thread group is enabled by default
- Used as the **source of truth** for the individual test plan files

---

## Authentication Flow

The pipeline uses **Keycloak** (OpenID Connect) for authentication. Here's how it works:

### Token Generation Flow

```
┌──────────┐     POST /realms/waseel-stg/protocol/openid-connect/token
│  JMeter  │ ──────────────────────────────────────────────────────────►
│  Setup   │     Body: grant_type=password&client_id=csbridge&...
│  Thread  │     Headers: Content-Type: application/x-www-form-urlencoded
│  Group   │
│          │ ◄──────────────────────────────────────────────────────────
│          │     Response: 200 OK
│          │     Body: {"access_token":"eyJ...","expires_in":3600,...}
│          │
│          │  ┌─────────────────────────────────────────────────────┐
│          │  │ JSONPostProcessor extracts $.access_token            │
│          │  │ JSR223PostProcessor stores as GLOBAL_AUTH_TOKEN      │
│          │  └─────────────────────────────────────────────────────┘
└──────────┘
          │
          ▼
┌──────────┐     JSR223PreProcessor reads GLOBAL_AUTH_TOKEN
│  Main    │     Sets AUTH_TOKEN variable
│  Thread  │
│  Group   │     HeaderManager adds: Authorization: Bearer ${AUTH_TOKEN}
│          │
│          │     POST /csbridge-adt/api/submit-adt-request
│          │ ─────────────────────────────────────────────────────────►
│          │     Headers: Authorization: Bearer eyJ...
│          │     Body: {"eventId":"...","eventType":"A01",...}
└──────────┘
```

### Token Details
- **Token Type**: Bearer token (JWT)
- **Validity**: 3600 seconds (1 hour)
- **Grant Type**: Password (Resource Owner Password Credentials)
- **Scope**: Realm `waseel-stg`, Client `csbridge`

### Keycloak Configuration

| Setting | Value |
|---------|-------|
| Host | `qa-iam.waseel.com` |
| Realm | `waseel-stg` |
| Token Path | `/realms/waseel-stg/protocol/openid-connect/token` |
| Client ID | `csbridge` |
| Grant Type | `password` |

---

## Pipeline Jobs

### Job 1: `run-all-tests`

Runs all 4 performance tests sequentially on a single runner.

**Steps:**
1. **Checkout repository** — Gets the latest code
2. **Set up Java 11** — Required runtime for JMeter
3. **Install JMeter 5.6.3** — Downloads and extracts from Apache archive
4. **Create results directories** — `results/{smoke,load,stress,spike}/`
5. **Validate Keycloak secrets** — Ensures all 4 secrets are configured
6. **Run tests** — Smoke → Load → Stress → Spike (each with `continue-on-error`)
7. **Upload artifacts** — Results CSVs, HTML reports, and jmeter.log

**Environment Variables:**
- `KC_CLIENT_ID` — From GitHub Secrets
- `KC_CLIENT_SECRET` — From GitHub Secrets
- `KC_USERNAME` — From GitHub Secrets
- `KC_PASSWORD` — From GitHub Secrets
- `JMETER_HOME` — Auto-set to workspace path

### Job 2: `publish-report`

Generates and publishes the HTML dashboard to GitHub Pages.

**Steps:**
1. **Checkout repository** — Gets the latest code
2. **Download test results** — From artifacts uploaded in Job 1
3. **Generate dashboard** — Runs `scripts/generate_dashboard.py`
4. **Copy sub-reports** — JMeter HTML reports for each test
5. **Setup GitHub Pages** — Configures Pages environment
6. **Upload to GitHub Pages** — Deploys the `public/` folder
7. **Deploy** — Makes the dashboard publicly accessible

---

## Prerequisites

### GitHub Repository Secrets

The following secrets must be configured in **Settings → Secrets and variables → Actions**:

| Secret | Description | Example |
|--------|-------------|---------|
| `KC_CLIENT_ID` | Keycloak client ID | `csbridge` |
| `KC_CLIENT_SECRET` | Keycloak client secret | `sCo...` (32 chars) |
| `KC_USERNAME` | Keycloak username | `testuser-csbridge` |
| `KC_PASSWORD` | Keycloak password | `Csb...` (13 chars) |

### GitHub Pages

GitHub Pages must be enabled:
1. Go to **Settings → Pages**
2. Source: **GitHub Actions**

### Required Permissions

The workflow requires these permissions:
- `contents: read` — Checkout repository
- `pages: write` — Deploy to GitHub Pages
- `id-token: write` — OIDC token for Pages deployment
- `pull-requests: write` — PR comments (if applicable)

---

## Setup & Configuration

### Initial Setup

1. **Fork/clone this repository**

2. **Configure GitHub Secrets:**
   ```
   Settings → Secrets and variables → Actions → New repository secret
   ```
   Add all 4 Keycloak secrets listed above.

3. **Enable GitHub Pages:**
   ```
   Settings → Pages → Source: GitHub Actions
   ```

4. **Push to main branch** — The pipeline triggers automatically on push.

### Running Locally with JMeter GUI

1. Open any `.jmx` file in **JMeter GUI**
2. Set environment variables in your shell:
   ```bash
   export KC_CLIENT_ID="csbridge"
   export KC_CLIENT_SECRET="your-secret"
   export KC_USERNAME="testuser-csbridge"
   export KC_PASSWORD="your-password"
   ```
3. Create a `results/` folder next to the JMX file
4. Run the test

### Generating HTML Report Locally

After running tests, generate the JMeter HTML report:
```bash
jmeter -g results/smoke/results.csv -o results/smoke/html_report/
```

---

## Running the Pipeline

### Automatic Triggers

The pipeline runs automatically on:
- **Push** to any branch
- **Pull request** creation/update
- **Manual trigger** via `workflow_dispatch`

### Manual Trigger

1. Go to **Actions** tab in GitHub
2. Select **Performance Tests** workflow
3. Click **Run workflow**
4. Select branch → Click **Run workflow**

### Expected Duration

| Phase | Duration |
|-------|----------|
| Setup (Java + JMeter) | ~2 minutes |
| Smoke Test | ~1 minute |
| Load Test | ~10 minutes |
| Stress Test | ~5 minutes |
| Spike Test | ~2 minutes |
| Dashboard Generation | ~1 minute |
| **Total** | **~20-25 minutes** |

---

## Understanding Results

### Dashboard

After the pipeline completes, the dashboard is available at:
```
https://<username>.github.io/<repository>/
```

The dashboard shows:
- **Overall status** — ALL PASSED (green) or SOME FAILED (red)
- **Per-test cards** with metrics:
  - Total Requests
  - Error Rate (%)
  - Avg Response Time (ms)
  - P90 Response Time (ms)
  - Throughput (requests/s)
  - Error count
- **Links** to full JMeter HTML reports for each test

### JMeter HTML Reports

Each test generates a detailed JMeter report accessible from the dashboard:
- **Statistics table** — Detailed metrics per API endpoint
- **Response time graph** — Visual timeline of response times
- **Throughput graph** — Requests per second over time
- **Error summary** — Breakdown of error types

### Artifacts

Raw results are available as GitHub Actions artifacts:
- `all-test-results` — CSV files and HTML reports for all tests
- `jmeter.log` — JMeter execution log for troubleshooting

### Interpreting Results

| Metric | Good | Warning | Critical |
|--------|------|---------|----------|
| Error Rate | < 1% | 1-5% | > 5% |
| Avg Response | < 500ms | 500-2000ms | > 2000ms |
| P90 Response | < 1000ms | 1000-3000ms | > 3000ms |

---

## Project Structure

```
uhr-performace-testing/
├── .github/
│   └── workflows/
│       └── performance-test.yml      # GitHub Actions workflow
├── scripts/
│   └── generate_dashboard.py          # Dashboard HTML generator
├── test-plan-smoke.jmx                # Smoke test (2 VU, 60s)
├── test-plan-load.jmx                 # Load test (50 VU, 10min)
├── test-plan-stress.jmx               # Stress test (150 VU, 5min)
├── test-plan-spike.jmx                # Spike test (200 VU, 2min)
├── UHR_ADT Events_Performance Testing-.jmx  # Reference file (all 4 tests)
└── README.md                          # This file
```

### File Descriptions

| File | Purpose |
|------|---------|
| `performance-test.yml` | GitHub Actions workflow — orchestrates the entire pipeline |
| `generate_dashboard.py` | Python script that parses JMeter CSVs and generates the HTML dashboard |
| `test-plan-*.jmx` | Individual JMeter test plans, one per test scenario |
| `UHR_ADT Events_Performance Testing-.jmx` | Reference file containing all test scenarios (for local use) |

---

## Troubleshooting

### Common Issues

#### 1. Keycloak Token Generation Fails (HTTP 500)
**Symptom**: All API requests return 401 Unauthorized  
**Cause**: Keycloak server (`qa-iam.waseel.com`) is down or unreachable  
**Solution**: Check Keycloak server status with your infrastructure team

#### 2. Keycloak Returns 400 Bad Request
**Symptom**: Token request fails with "Bad Request"  
**Cause**: Invalid client credentials or client configuration  
**Solution**: Verify `KC_CLIENT_ID`, `KC_CLIENT_SECRET`, `KC_USERNAME`, `KC_PASSWORD` in GitHub Secrets

#### 3. Keycloak Returns 401 Unauthorized
**Symptom**: Token request fails with "Invalid client credentials"  
**Cause**: Wrong client secret or user password  
**Solution**: Regenerate credentials in Keycloak admin console and update GitHub Secrets

#### 4. Tests Run But All Requests Fail
**Symptom**: High error rate (100%) across all tests  
**Cause**: Token not being extracted or injected correctly  
**Solution**: Check jmeter.log artifact for token extraction errors

#### 5. GitHub Pages Dashboard Not Updating
**Symptom**: Dashboard shows old results or 404 error  
**Cause**: Pages deployment failed or artifact upload timed out  
**Solution**: Re-run the workflow; check the publish-report job logs

#### 6. Workflow Fails at Secret Validation
**Symptom**: "Keycloak secret(s) missing!" error  
**Cause**: One or more GitHub Secrets are not configured  
**Solution**: Add all 4 required secrets in Settings → Secrets

### Debugging Tips

1. **Check the `jmeter.log` artifact** — Contains detailed JMeter execution logs
2. **Download `all-test-results` artifact** — Contains raw CSV data for analysis
3. **Run the smoke test locally** — Open `test-plan-smoke.jmx` in JMeter GUI to debug
4. **Test Keycloak manually**:
   ```bash
   curl -X POST \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "grant_type=password&client_id=csbridge&client_secret=SECRET&username=testuser-csbridge&password=PASSWORD" \
     "https://qa-iam.waseel.com/realms/waseel-stg/protocol/openid-connect/token"
   ```

---

## API Under Test

### Endpoint
```
POST https://stg-uhr.waseel.com/csbridge-adt/api/submit-adt-request
```

### Authentication
```
Authorization: Bearer <keycloak-access-token>
Content-Type: application/json
```

### Payload Structure
```json
{
  "eventId": "20250624120000000_1_1",
  "eventType": "A01",
  "uhrRequest": {
    "id": 1,
    "source": "123",
    "visitNumber": "202510300001",
    "provider": { "providerID": "15000000112233", ... },
    "caseInfo": { "visitType": "INPATIENT", ... },
    "patient": { "id": "NB123456", ... },
    "careTeam": [ { "id": "DR001", ... } ]
  }
}
```
