#!/usr/bin/env python3
"""
Credential Scanner Script
=========================
Scans directories for hardcoded credentials in scripts and configuration files.

Usage:
    python3 creds_scan.py --paths /path1 /path2 --output results.json --config config.json

Features:
    - Scans multiple file types (configurable via scan_config.yml)
    - Detects common credential patterns
    - Outputs results in JSON format for Ansible consumption
    - Supports configuration from Ansible scan_config.yml
"""

import os
import re
import json
import argparse
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional


# =============================================================================
# CREDENTIAL PATTERNS
# =============================================================================
CREDENTIAL_PATTERNS = [
    # Password patterns
    {
        'name': 'password_assignment',
        'type': 'Password',
        'pattern': r'(?i)(password|passwd|pwd)\s*[=:]\s*["\']?[^\s"\']{4,}["\']?',
        'severity': 'HIGH'
    },
    {
        'name': 'password_variable',
        'type': 'Password Variable',
        'pattern': r'(?i)(password|passwd|pwd)_?\w*\s*[=:]\s*["\'][^"\']+["\']',
        'severity': 'HIGH'
    },
    # API Keys
    {
        'name': 'api_key',
        'type': 'API Key',
        'pattern': r'(?i)(api[_-]?key|apikey)\s*[=:]\s*["\']?[a-zA-Z0-9_\-]{16,}["\']?',
        'severity': 'HIGH'
    },
    # Secret patterns
    {
        'name': 'secret',
        'type': 'Secret',
        'pattern': r'(?i)(secret|secret[_-]?key)\s*[=:]\s*["\']?[^\s"\']{8,}["\']?',
        'severity': 'HIGH'
    },
    # Token patterns
    {
        'name': 'token',
        'type': 'Token',
        'pattern': r'(?i)(auth[_-]?token|access[_-]?token|bearer[_-]?token|token)\s*[=:]\s*["\']?[a-zA-Z0-9_\-\.]{20,}["\']?',
        'severity': 'HIGH'
    },
    # Private keys
    {
        'name': 'private_key',
        'type': 'Private Key',
        'pattern': r'(?i)(private[_-]?key|priv[_-]?key)\s*[=:]\s*["\']?[^\s"\']+["\']?',
        'severity': 'CRITICAL'
    },
    {
        'name': 'rsa_private_key',
        'type': 'RSA Private Key',
        'pattern': r'-----BEGIN (RSA )?PRIVATE KEY-----',
        'severity': 'CRITICAL'
    },
    # Database connection strings
    {
        'name': 'db_connection',
        'type': 'Database Connection',
        'pattern': r'(?i)(mysql|postgresql|postgres|mongodb|redis):\/\/[^\s]+:[^\s]+@[^\s]+',
        'severity': 'HIGH'
    },
    # AWS patterns
    {
        'name': 'aws_access_key',
        'type': 'AWS Access Key',
        'pattern': r'(?i)aws[_-]?access[_-]?key[_-]?id\s*[=:]\s*["\']?[A-Z0-9]{20}["\']?',
        'severity': 'HIGH'
    },
    {
        'name': 'aws_secret_key',
        'type': 'AWS Secret Key',
        'pattern': r'(?i)aws[_-]?secret[_-]?access[_-]?key\s*[=:]\s*["\']?[A-Za-z0-9/+=]{40}["\']?',
        'severity': 'CRITICAL'
    },
    # Generic credential patterns
    {
        'name': 'credentials',
        'type': 'Credentials',
        'pattern': r'(?i)credentials?\s*[=:]\s*["\'][^"\']+["\']',
        'severity': 'MEDIUM'
    },
    # Hardcoded usernames with passwords
    {
        'name': 'user_pass_combo',
        'type': 'Username/Password Combo',
        'pattern': r'(?i)(username|user)\s*[=:]\s*["\']?\w+["\']?\s*[,;]?\s*(password|passwd|pwd)\s*[=:]\s*["\']?[^\s"\']+["\']?',
        'severity': 'HIGH'
    },
]

# Default file extensions to scan (used if not provided via config)
DEFAULT_EXTENSIONS = [
    '.py', '.sh', '.bash', '.zsh', '.ksh',
    '.yml', '.yaml', '.json', '.xml',
    '.conf', '.cfg', '.ini', '.config',
    '.properties', '.env', '.envrc',
    '.sql', '.rb', '.pl', '.php',
    '.js', '.ts', '.java', '.go',
    '.tf', '.tfvars',
]

# Default exclude patterns (used if not provided via config)
DEFAULT_EXCLUDE_PATTERNS = [
    '__pycache__',
    '.git',
    'node_modules',
    '.venv',
    'venv',
    '.tox',
    '*.pyc',
    '*.log',
    '.idea',
    '.vscode',
]

# Default max file size in KB
DEFAULT_MAX_FILE_SIZE_KB = 1024

# Default recursive scan setting
DEFAULT_RECURSIVE_SCAN = True


def parse_extensions_from_config(config_extensions: List[str]) -> List[str]:
    """
    Convert config file extensions (e.g., "*.py") to script format (e.g., ".py")
    """
    parsed = []
    for ext in config_extensions:
        # Remove leading * if present (e.g., "*.py" -> ".py")
        if ext.startswith('*.'):
            parsed.append(ext[1:])  # "*.py" -> ".py"
        elif ext.startswith('.'):
            parsed.append(ext)  # ".py" -> ".py"
        else:
            parsed.append('.' + ext)  # "py" -> ".py"
    return parsed


def parse_exclude_from_config(config_exclude: List[str]) -> List[str]:
    """
    Convert config exclude patterns for use in script
    """
    parsed = []
    for pattern in config_exclude:
        # Remove leading * if it's a glob pattern like "*.log"
        if pattern.startswith('*.'):
            parsed.append(pattern)  # Keep as-is for extension matching
        else:
            parsed.append(pattern)
    return parsed


class CredentialScanner:
    """Scanner for detecting hardcoded credentials in files."""
    
    def __init__(
        self,
        extensions: Optional[List[str]] = None,
        exclude_patterns: Optional[List[str]] = None,
        max_file_size_kb: int = DEFAULT_MAX_FILE_SIZE_KB,
        recursive_scan: bool = DEFAULT_RECURSIVE_SCAN,
        custom_patterns: Optional[List[Dict]] = None
    ):
        self.extensions = extensions or DEFAULT_EXTENSIONS
        self.exclude_patterns = exclude_patterns or DEFAULT_EXCLUDE_PATTERNS
        self.max_file_size_kb = max_file_size_kb
        self.max_file_size_bytes = max_file_size_kb * 1024
        self.recursive_scan = recursive_scan
        self.patterns = CREDENTIAL_PATTERNS.copy()
        
        if custom_patterns:
            self.patterns.extend(custom_patterns)
        
        # Compile patterns for efficiency
        self.compiled_patterns = [
            {
                **pattern,
                'compiled': re.compile(pattern['pattern'])
            }
            for pattern in self.patterns
        ]
        
        # Store config for reporting
        self.config_info = {
            'file_extensions': self.extensions,
            'exclude_patterns': self.exclude_patterns,
            'max_file_size_kb': self.max_file_size_kb,
            'recursive_scan': self.recursive_scan
        }
    
    def get_patterns_checked(self) -> List[str]:
        """Return list of pattern names being checked."""
        return [p['name'] for p in self.patterns]
    
    def get_patterns_display(self) -> List[Dict]:
        """Return patterns with their regex for display."""
        return [{'name': p['name'], 'type': p['type'], 'pattern': p['pattern']} for p in self.patterns]
    
    def should_exclude(self, path: Path) -> bool:
        """Check if path should be excluded from scanning."""
        path_str = str(path)
        path_name = path.name
        
        for pattern in self.exclude_patterns:
            # Check if pattern is in path string
            if pattern in path_str:
                return True
            # Check glob-style extension patterns (*.log)
            if pattern.startswith('*.'):
                ext = pattern[1:]  # "*.log" -> ".log"
                if path_name.endswith(ext):
                    return True
        return False
    
    def should_scan_file(self, file_path: Path) -> bool:
        """Check if file should be scanned based on extension and exclusions."""
        if self.should_exclude(file_path):
            return False
        
        # Check file size
        try:
            if file_path.stat().st_size > self.max_file_size_bytes:
                return False
        except OSError:
            return False
        
        return file_path.suffix.lower() in self.extensions
    
    def scan_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """Scan a single file for credentials."""
        findings = []
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            for line_num, line in enumerate(lines, 1):
                for pattern in self.compiled_patterns:
                    matches = pattern['compiled'].findall(line)
                    if matches:
                        findings.append({
                            'file': str(file_path),
                            'line': line_num,
                            'type': pattern['type'],
                            'severity': pattern['severity'],
                            'pattern': pattern['name'],
                            'match': str(matches[0]) if matches else '',
                            'raw_line': line.strip()[:200]  # Truncate long lines
                        })
        
        except Exception as e:
            findings.append({
                'file': str(file_path),
                'line': 0,
                'type': 'Error',
                'severity': 'INFO',
                'pattern': 'read_error',
                'match': str(e),
                'raw_line': f'Error reading file: {e}'
            })
        
        return findings
    
    def scan_directory(self, directory: str) -> Dict[str, Any]:
        """Scan a directory for credentials."""
        dir_path = Path(directory)
        
        if not dir_path.exists():
            return {
                'path': directory,
                'status': 'error',
                'error': f'Directory does not exist: {directory}',
                'findings': [],
                'scanned_files': [],
                'scanned_files_count': 0
            }
        
        all_findings = []
        scanned_files = []
        
        if dir_path.is_file():
            # Single file scan
            if self.should_scan_file(dir_path):
                all_findings.extend(self.scan_file(dir_path))
                scanned_files.append(str(dir_path))
        else:
            # Directory scan
            if self.recursive_scan:
                # Recursive scan
                for root, dirs, files in os.walk(directory):
                    # Filter excluded directories
                    dirs[:] = [d for d in dirs if not self.should_exclude(Path(root) / d)]
                    
                    for file in files:
                        file_path = Path(root) / file
                        if self.should_scan_file(file_path):
                            findings = self.scan_file(file_path)
                            all_findings.extend(findings)
                            scanned_files.append(str(file_path))
            else:
                # Non-recursive scan (only top-level files)
                for file in os.listdir(directory):
                    file_path = dir_path / file
                    if file_path.is_file() and self.should_scan_file(file_path):
                        findings = self.scan_file(file_path)
                        all_findings.extend(findings)
                        scanned_files.append(str(file_path))
        
        return {
            'path': directory,
            'status': 'completed',
            'findings': all_findings,
            'scanned_files': scanned_files,
            'scanned_files_count': len(scanned_files),
            'findings_count': len(all_findings)
        }
    
    def scan_multiple_paths(self, paths: List[str]) -> Dict[str, Any]:
        """Scan multiple paths and aggregate results."""
        all_results = []
        all_findings = []
        all_scanned_files = []
        patterns_found = set()
        
        for path in paths:
            result = self.scan_directory(path)
            all_results.append(result)
            all_findings.extend(result['findings'])
            all_scanned_files.extend(result['scanned_files'])
            
            # Track which patterns were found
            for finding in result['findings']:
                patterns_found.add(finding['pattern'])
        
        # Build hardcoded information structure
        hardcoded_info = []
        files_with_findings = {}
        
        for finding in all_findings:
            file_path = finding['file']
            if file_path not in files_with_findings:
                files_with_findings[file_path] = []
            files_with_findings[file_path].append({
                'line': finding['line'],
                'type': finding['type'],
                'value': finding['raw_line'],
                'pattern': finding['pattern'],
                'severity': finding['severity']
            })
        
        for file_path, findings_list in files_with_findings.items():
            hardcoded_info.append({
                'file': file_path,
                'findings': findings_list
            })
        
        return {
            'scan_timestamp': datetime.now().isoformat(),
            'scan_config': self.config_info,
            'paths_scanned': paths,
            'scanned_files': all_scanned_files,
            'scanned_files_count': len(all_scanned_files),
            'patterns_checked': self.get_patterns_checked(),
            'patterns_found': list(patterns_found),
            'total_findings': len(all_findings),
            'findings_by_severity': self._group_by_severity(all_findings),
            'hardcoded_info': hardcoded_info,
            'path_results': all_results
        }
    
    def _group_by_severity(self, findings: List[Dict]) -> Dict[str, int]:
        """Group findings by severity level."""
        severity_counts = {'CRITICAL': 0, 'HIGH': 0, 'MEDIUM': 0, 'LOW': 0, 'INFO': 0}
        for finding in findings:
            severity = finding.get('severity', 'INFO')
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
        return severity_counts


def load_config_from_json(config_path: str) -> Dict[str, Any]:
    """Load scan configuration from JSON file."""
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: Could not load config file {config_path}: {e}")
        return {}


def main():
    """Main entry point for the credential scanner."""
    parser = argparse.ArgumentParser(
        description='Scan directories for hardcoded credentials',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--paths', '-p',
        nargs='+',
        required=True,
        help='Paths to scan (files or directories)'
    )
    
    parser.add_argument(
        '--output', '-o',
        help='Output file path (prints to stdout if not specified)'
    )
    
    parser.add_argument(
        '--config', '-c',
        help='Path to JSON config file with scan settings (from scan_config.yml)'
    )
    
    parser.add_argument(
        '--extensions', '-e',
        nargs='+',
        help='File extensions to scan (e.g., .py .sh .yml) - overrides config'
    )
    
    parser.add_argument(
        '--exclude', '-x',
        nargs='+',
        help='Patterns to exclude (e.g., __pycache__ .git) - overrides config'
    )
    
    parser.add_argument(
        '--max-file-size', '-m',
        type=int,
        help='Maximum file size in KB to scan - overrides config'
    )
    
    parser.add_argument(
        '--no-recursive',
        action='store_true',
        help='Disable recursive directory scanning'
    )
    
    args = parser.parse_args()
    
    # Initialize settings from defaults
    extensions = None
    exclude_patterns = None
    max_file_size_kb = DEFAULT_MAX_FILE_SIZE_KB
    recursive_scan = DEFAULT_RECURSIVE_SCAN
    
    # Load config file if provided
    if args.config:
        config = load_config_from_json(args.config)
        if 'file_extensions' in config:
            extensions = parse_extensions_from_config(config['file_extensions'])
        if 'exclude_patterns' in config:
            exclude_patterns = parse_exclude_from_config(config['exclude_patterns'])
        if 'max_file_size_kb' in config:
            max_file_size_kb = config['max_file_size_kb']
        if 'recursive_scan' in config:
            recursive_scan = config['recursive_scan']
    
    # Command-line arguments override config
    if args.extensions:
        extensions = args.extensions
    if args.exclude:
        exclude_patterns = args.exclude
    if args.max_file_size:
        max_file_size_kb = args.max_file_size
    if args.no_recursive:
        recursive_scan = False
    
    # Initialize scanner with settings
    scanner = CredentialScanner(
        extensions=extensions,
        exclude_patterns=exclude_patterns,
        max_file_size_kb=max_file_size_kb,
        recursive_scan=recursive_scan
    )
    
    # Perform scan on all paths
    results = scanner.scan_multiple_paths(args.paths)
    
    # Format output as JSON
    output = json.dumps(results, indent=2, default=str)
    
    # Write or print output
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            f.write(output)
        print(f"Results saved to: {args.output}")
    else:
        print(output)
    
    # Exit with appropriate code (0 = no findings, 1 = findings detected)
    exit(1 if results['total_findings'] > 0 else 0)


if __name__ == '__main__':
    main()
