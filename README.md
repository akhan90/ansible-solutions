# Credential Scan Automation

Automated solution for scanning directory paths for hardcoded credentials across multiple servers, organized by teams.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Directory Structure](#directory-structure)
- [Configuration](#configuration)
- [Execution Scenarios](#execution-scenarios)
- [Roles Description](#roles-description)
- [Ansible Tower Setup](#ansible-tower-setup)
- [Execution Flows](#execution-flows)
- [Output Reports](#output-reports)
- [Troubleshooting](#troubleshooting)

---

## Overview

This solution provides:

- **Automated credential scanning** across multiple servers
- **Team-based organization** - each team receives their own report
- **Parallel execution** - servers within a team are scanned simultaneously
- **Comprehensive reporting** - HTML and CSV reports for each team
- **Email notifications** - Automatic delivery via SMTP or mailx

### Credential Patterns Detected

| Pattern Type | Severity | Example |
|-------------|----------|---------|
| Password Assignment | HIGH | `password = "secret123"` |
| API Keys | HIGH | `api_key = "abc123xyz..."` |
| AWS Access Keys | HIGH | `aws_access_key_id = "AKIA..."` |
| AWS Secret Keys | CRITICAL | `aws_secret_access_key = "..."` |
| Private Keys | CRITICAL | `-----BEGIN RSA PRIVATE KEY-----` |
| Database Connections | HIGH | `mysql://user:pass@host/db` |
| Tokens | HIGH | `auth_token = "eyJ..."` |
| Secrets | HIGH | `secret_key = "..."` |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           ANSIBLE TOWER                                     │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │
│  │   Job Template  │  │   Job Template  │  │    Inventory    │             │
│  │   Single Team   │  │   All Teams     │  │    (Servers)    │             │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘             │
└───────────┼─────────────────────┼─────────────────────┼─────────────────────┘
            │                     │                     │
            ▼                     ▼                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            GIT REPOSITORY                                   │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │  scan/                                                                │  │
│  │  ├── scan_config.yml          # Target configuration                  │  │
│  │  ├── playbooks/               # Execution playbooks                   │  │
│  │  │   ├── execute_for_team.yml                                        │  │
│  │  │   ├── execute_all_teams.yml                                       │  │
│  │  │   ├── process_team_scan.yml                                       │  │
│  │  │   └── scan_single_host.yml                                        │  │
│  │  ├── roles/                   # Ansible roles                         │  │
│  │  │   ├── host_map/                                                   │  │
│  │  │   ├── scan/                                                       │  │
│  │  │   ├── report/                                                     │  │
│  │  │   └── email/                                                      │  │
│  │  └── reports/                 # Generated reports (output)            │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          TARGET SERVERS                                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │ app-server  │  │ app-server  │  │ infra-srv   │  │ db-server   │        │
│  │    -01      │  │    -02      │  │    -01      │  │    -01      │        │
│  │             │  │             │  │             │  │             │        │
│  │ Team: App   │  │ Team: App   │  │ Team:DevOps │  │ Team: DBA   │        │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘        │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Directory Structure

```
scan/
├── scan_config.yml                 # Main configuration file
├── README.md                       # This file
│
├── playbooks/
│   ├── execute_for_team.yml        # Execute scan for a single team
│   ├── execute_all_teams.yml       # Execute scan for all teams
│   ├── process_team_scan.yml       # Included: process one team
│   └── scan_single_host.yml        # Included: scan one host
│
├── roles/
│   ├── host_map/                   # Team-based host mapping
│   │   ├── tasks/main.yml
│   │   └── defaults/main.yml
│   │
│   ├── scan/                       # Credential scanning
│   │   ├── tasks/main.yml
│   │   ├── defaults/main.yml
│   │   └── files/creds_scan.py     # Python scan script
│   │
│   ├── report/                     # Report generation
│   │   ├── tasks/main.yml
│   │   ├── defaults/main.yml
│   │   └── templates/
│   │       ├── report.html.j2      # HTML report template
│   │       └── report.csv.j2       # CSV report template
│   │
│   └── email/                      # Email notification
│       ├── tasks/main.yml
│       ├── defaults/main.yml
│       └── templates/
│           ├── email_body.html.j2  # HTML email (SMTP)
│           └── email_body.txt.j2   # Plain text (mailx)
│
└── reports/                        # Generated reports (output)
    └── Cred_ScanReport_<Team>_<Date>.html/.csv
```

---

## Configuration

### scan_config.yml

The main configuration file that defines:
- **scan_targets**: List of servers to scan with their configurations
- **global_settings**: Default scan settings (extensions, excludes, etc.)

```yaml
scan_targets:
  - hostname: app-server-01.example.com    # Must match Tower inventory
    automation_user: svc_app_auto          # User to become on target
    team_name: Application Team            # Team grouping
    team_email: app-team@example.com       # Report recipient
    scan_paths:                            # Directories to scan
      - /opt/applications/config
      - /opt/applications/scripts

global_settings:
  file_extensions:
    - "*.py"
    - "*.sh"
    - "*.yml"
    - "*.json"
    - "*.conf"
    - "*.env"
  exclude_patterns:
    - "*.log"
    - ".git"
    - "__pycache__"
  max_file_size_kb: 1024
  recursive_scan: true
```

---

## Execution Scenarios

### Scenario 1: Single Team Execution

**Playbook**: `execute_for_team.yml`

**Required Variables**:
```yaml
execute_for_team: true
team_name: "Application Team"
```

**Optional Variables**:
```yaml
smtp_host: "smtp.company.com"
smtp_port: 587
smtp_username: "user@company.com"
smtp_password: "{{ vault_smtp_password }}"
smtp_use_tls: true
```

### Scenario 2: All Teams Execution

**Playbook**: `execute_all_teams.yml`

**Required Variables**:
```yaml
scan_all_teams: true
```

**Validation**: `execute_for_team` and `team_name` must NOT be set.

---

## Roles Description

### 1. host_map Role

Maps inventory hosts against scan_config.yml, grouped by team.

**Output Variables**:
- `team_mappings`: List of teams with their host configurations
- `host_config`: Per-host configuration facts

### 2. scan Role

Executes the Python credential scanner on target hosts.

**Input Variables**:
| Variable | Required | Description |
|----------|----------|-------------|
| `scan_hostname` | Yes | Target hostname |
| `scan_automation_user` | Yes | User to become on target |
| `scan_paths` | Yes | List of paths to scan |
| `scan_global_settings` | No | Global settings from config |

**Output Variable**: `server_scan_result`

### 3. report Role

Generates HTML and CSV reports for a team.

**Input Variables**:
| Variable | Required | Description |
|----------|----------|-------------|
| `report_team_name` | Yes | Team name |
| `report_team_email` | Yes | Team email |
| `report_scan_results` | Yes | List of scan results |

**Output Variable**: `team_report_output`

### 4. email Role

Sends reports via SMTP or mailx.

**Input Variables**:
| Variable | Required | Description |
|----------|----------|-------------|
| `email_to` | Yes | Recipient email |
| `email_team_name` | Yes | Team name for subject |
| `email_report_html_path` | Yes | Path to HTML report |
| `email_report_csv_path` | Yes | Path to CSV report |
| `email_report_summary` | Yes | Report summary object |
| `smtp_host` | No | SMTP server (uses mailx if not set) |

**Output Variable**: `email_result`

---

## Ansible Tower Setup

### Job Template: Single Team Scan

| Setting | Value |
|---------|-------|
| **Name** | Credential Scan - Single Team |
| **Job Type** | Run |
| **Inventory** | Your Server Inventory |
| **Project** | Your Git Project |
| **Playbook** | `playbooks/execute_for_team.yml` |
| **Credentials** | Machine Credential |
| **Extra Variables** | Prompt on launch ✓ |

**Extra Variables Template**:
```yaml
execute_for_team: true
team_name: ""  # Prompt user to fill
```

### Job Template: All Teams Scan

| Setting | Value |
|---------|-------|
| **Name** | Credential Scan - All Teams |
| **Job Type** | Run |
| **Inventory** | Your Server Inventory |
| **Project** | Your Git Project |
| **Playbook** | `playbooks/execute_all_teams.yml` |
| **Credentials** | Machine Credential |
| **Extra Variables** | |

**Extra Variables**:
```yaml
scan_all_teams: true
```

---

## Execution Flows

### Flow 1: Single Team Execution

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    SINGLE TEAM EXECUTION FLOW                               │
└─────────────────────────────────────────────────────────────────────────────┘

     Ansible Tower
          │
          │  Trigger with:
          │  - execute_for_team: true
          │  - team_name: "Application Team"
          │
          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ PLAY 1: Initialize (localhost)                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│  ✓ Validate execute_for_team = true                                         │
│  ✓ Validate team_name provided                                              │
│  ✓ Load scan_config.yml                                                     │
│  ✓ Validate team exists in config                                           │
│  ✓ Extract team hosts and settings                                          │
│  ✓ Set facts for subsequent plays                                           │
└─────────────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ PLAY 2: Execute Scans (PARALLEL - strategy: free)                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │
│  │ app-server-01   │  │ app-server-02   │  │ app-server-03   │             │
│  ├─────────────────┤  ├─────────────────┤  ├─────────────────┤             │
│  │ 1. Deploy       │  │ 1. Deploy       │  │ 1. Deploy       │             │
│  │    script       │  │    script       │  │    script       │             │
│  │ 2. Run scan     │  │ 2. Run scan     │  │ 2. Run scan     │  PARALLEL   │
│  │ 3. Collect      │  │ 3. Collect      │  │ 3. Collect      │             │
│  │    results      │  │    results      │  │    results      │             │
│  │ 4. Cleanup      │  │ 4. Cleanup      │  │ 4. Cleanup      │             │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘             │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
          │
          ▼ (Wait for all to complete)
┌─────────────────────────────────────────────────────────────────────────────┐
│ PLAY 3: Collect & Report (localhost)                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│  ✓ Collect scan results from all hosts                                      │
│  ✓ Generate HTML report                                                     │
│  ✓ Generate CSV report                                                      │
│  ✓ Send email to team                                                       │
│  ✓ Display final summary                                                    │
└─────────────────────────────────────────────────────────────────────────────┘
          │
          ▼
     ┌─────────────────────────────────────────┐
     │              COMPLETE                   │
     │                                         │
     │  📄 HTML Report Generated               │
     │  📊 CSV Report Generated                │
     │  📧 Email Sent to Team                  │
     └─────────────────────────────────────────┘
```

### Flow 2: All Teams Execution

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ALL TEAMS EXECUTION FLOW                                 │
└─────────────────────────────────────────────────────────────────────────────┘

     Ansible Tower
          │
          │  Trigger with:
          │  - scan_all_teams: true
          │
          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ PLAY 1: Initialize (localhost)                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│  ✓ Validate scan_all_teams = true                                           │
│  ✓ Ensure execute_for_team is NOT set                                       │
│  ✓ Load scan_config.yml                                                     │
│  ✓ Extract all unique teams                                                 │
│  ✓ Build team mappings                                                      │
└─────────────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ PLAY 2: Process Teams (SEQUENTIAL)                                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │ TEAM 1: Application Team                                              │  │
│  │  ├── Scan app-server-01 ──┐                                           │  │
│  │  ├── Scan app-server-02 ──┼──► Collect ──► Report ──► Email           │  │
│  │  └────────────────────────┘                                           │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                              │                                              │
│                              ▼                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │ TEAM 2: DevOps Team                                                   │  │
│  │  ├── Scan infra-server-01 ┐                                           │  │
│  │  ├── Scan infra-server-02 ┼──► Collect ──► Report ──► Email           │  │
│  │  └────────────────────────┘                                           │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                              │                                              │
│                              ▼                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │ TEAM 3: Database Team                                                 │  │
│  │  └── Scan db-server-01 ───┴──► Collect ──► Report ──► Email           │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                              │                                              │
│                              ▼                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │ TEAM 4: Security Team                                                 │  │
│  │  └── Scan security-srv-01 ┴──► Collect ──► Report ──► Email           │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ PLAY 3: Final Summary (localhost)                                           │
├─────────────────────────────────────────────────────────────────────────────┤
│  ✓ Calculate overall statistics                                             │
│  ✓ Display per-team results                                                 │
│  ✓ Report total findings across all teams                                   │
└─────────────────────────────────────────────────────────────────────────────┘
          │
          ▼
     ┌─────────────────────────────────────────┐
     │              COMPLETE                   │
     │                                         │
     │  📄 4 HTML Reports Generated            │
     │  📊 4 CSV Reports Generated             │
     │  📧 4 Emails Sent (one per team)        │
     │                                         │
     │  Total Teams: 4                         │
     │  Total Findings: 15                     │
     └─────────────────────────────────────────┘
```

### Scan Role Internal Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SCAN ROLE FLOW                                      │
└─────────────────────────────────────────────────────────────────────────────┘

     Input:
     - scan_hostname
     - scan_automation_user
     - scan_paths
     - scan_global_settings
          │
          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 1. Deploy creds_scan.py to target                                           │
│    └── /tmp/creds_scan.py                                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│ 2. Deploy config JSON (if global_settings provided)                         │
│    └── /tmp/creds_scan_config_<hostname>.json                               │
├─────────────────────────────────────────────────────────────────────────────┤
│ 3. Check which scan paths exist                                             │
│    ├── existing_scan_paths: paths found                                     │
│    └── missing_scan_paths: paths not found                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│ 4. Execute scan (become: automation_user)                                   │
│    └── python3 creds_scan.py --paths /path1 /path2 --config config.json    │
├─────────────────────────────────────────────────────────────────────────────┤
│ 5. Fetch results JSON                                                       │
│    └── /tmp/creds_scan_results_<hostname>.json                              │
├─────────────────────────────────────────────────────────────────────────────┤
│ 6. Parse and build server_scan_result                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│ 7. Cleanup: Remove script, config, and results from target                  │
└─────────────────────────────────────────────────────────────────────────────┘
          │
          ▼
     Output: server_scan_result
     - server_name
     - patterns_checked
     - patterns_found
     - file_paths_scanned
     - hardcoded_info
     - findings_by_severity
```

---

## Output Reports

### HTML Report

**Filename**: `Cred_ScanReport_<TeamName>_<YYYYMMDD>.html`

**Contents**:
- Executive summary with statistics
- Severity breakdown (visual bars)
- Types of hardcoded info found
- Per-server expandable details:
  - Files scanned
  - Findings table (file, line, type, severity, value)

### CSV Report

**Filename**: `Cred_ScanReport_<TeamName>_<YYYYMMDD>.csv`

**Columns**:
```
Hostname,Automation_User,Scan_Path,File_With_Hardcoded_Info,Line_Number,Finding_Type,Severity,Hardcoded_Information
```

---

## Troubleshooting

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| "Host not found in inventory" | Hostname in scan_config.yml doesn't match Tower inventory | Ensure exact hostname match |
| "Failed to deploy scan script" | Permission issues on target | Verify automation_user has write access to /tmp |
| "Email not sent" | SMTP config missing and mailx not installed | Install mailx or configure SMTP |
| "Team not found in configuration" | team_name doesn't match scan_config.yml | Check exact team name spelling |

### Debug Mode

Run with verbose output:
```bash
ansible-playbook playbooks/execute_for_team.yml -e "execute_for_team=true team_name='Application Team'" -vvv
```

### Verify Configuration

Check scan_config.yml syntax:
```bash
ansible-playbook --syntax-check playbooks/execute_for_team.yml
```

---

## Requirements

### Ansible Tower / AWX
- Version 3.8+ recommended
- Inventory containing all target servers
- Machine credentials for target servers

### Target Servers
- Python 3.6+ installed
- Automation user with:
  - Read access to scan paths
  - Write access to /tmp

### Control Node
- `community.general` collection (for mail module)
- mailx (if not using SMTP)

### Install Dependencies
```bash
ansible-galaxy collection install community.general
```

---

## Local Testing

### Quick Start

1. **Use the local test configuration**:
   ```bash
   cp scan_config_local.yml scan_config.yml
   ```

2. **Run a single team scan**:
   ```bash
   ansible-playbook -i inventory/hosts.yml playbooks/site.yml \
     -e "execute_for_team=true" \
     -e "team_name='Application Team'"
   ```

3. **Run all teams scan**:
   ```bash
   ansible-playbook -i inventory/hosts.yml playbooks/site.yml \
     -e "scan_all_teams=true"
   ```

### Test Data

The `test_data/` directory contains sample files with intentional hardcoded credentials:

| File | Credentials | Expected Findings |
|------|-------------|-------------------|
| `app_config/database.yml` | Passwords, API keys, tokens | 4-5 |
| `app_scripts/deploy.sh` | AWS keys, passwords, tokens | 5-6 |
| `app_scripts/config.py` | Multiple API keys, JWT secret, private key | 7-8 |
| `devops_scripts/jenkins_deploy.sh` | Jenkins token, Docker password, K8s token | 4-5 |
| `app_config/clean_config.yml` | None (uses vault/env vars) | 0 |

### Local Inventory Structure

```
inventory/
├── hosts.yml              # Main inventory file
└── group_vars/
    └── all.yml            # Global variables
```

### Entry Point Playbook

Use `site.yml` as the single entry point:

```bash
# Shows help if no mode specified
ansible-playbook playbooks/site.yml

# Single team mode
ansible-playbook playbooks/site.yml -e "execute_for_team=true team_name='DevOps Team'"

# All teams mode
ansible-playbook playbooks/site.yml -e "scan_all_teams=true"
```

### Directory Structure (Updated)

```
scan/
├── ansible.cfg                 # Ansible configuration
├── scan_config.yml             # Production configuration
├── scan_config_local.yml       # Local testing configuration
├── README.md
│
├── inventory/                  # Local test inventory
│   ├── hosts.yml
│   └── group_vars/
│       └── all.yml
│
├── playbooks/
│   ├── site.yml                # ← MAIN ENTRY POINT
│   ├── execute_for_team.yml
│   ├── execute_all_teams.yml
│   ├── process_team_scan.yml
│   └── scan_single_host.yml
│
├── roles/
│   ├── host_map/
│   ├── scan/
│   ├── report/
│   └── email/
│
├── test_data/                  # Test files with fake credentials
│   ├── app_config/
│   ├── app_scripts/
│   └── devops_scripts/
│
└── reports/                    # Generated reports
```

---

## License

Internal Use Only

## Author

Ansible Automation Team

