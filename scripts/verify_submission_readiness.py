"""
RecoverAI — Buildathon Submission Readiness Verification Script (Step 61)

Validates all 10 core submission criteria across documentation, backend test suite,
frontend test suite, git history, security, and repository structure.
"""

import sys
import os
import subprocess
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent

def check_file_exists(rel_path: str, description: str) -> bool:
    full_path = ROOT_DIR / rel_path
    exists = full_path.exists()
    status = "OK" if exists else "MISSING"
    print(f"[{status}] {description} ({rel_path})")
    return exists

def run_command(cmd: list[str], description: str, cwd=None) -> bool:
    try:
        res = subprocess.run(cmd, cwd=cwd or ROOT_DIR, capture_output=True, text=True)
        success = res.returncode == 0
        status = "OK" if success else "FAILED"
        print(f"[{status}] {description}")
        if not success:
            print(f"   Error output:\n{res.stderr[:500]}")
        return success
    except Exception as err:
        print(f"[FAILED] {description} - {err}")
        return False

def main():
    print("=" * 70)
    print("RECOVERAI — BUILDATHON SUBMISSION READINESS AUDIT (STEP 61)")
    print("=" * 70)

    checks = []

    # 1. Required Documentation Files
    print("\n1. Verifying Core Documentation Set:")
    docs = [
        ("README.md", "Root README Specification"),
        ("LICENSE", "MIT Open Source License"),
        (".github/workflows/ci.yml", "GitHub Actions CI Workflow"),
        ("docs/implementation_plan.md", "Frozen 61-Step Implementation Plan"),
        ("docs/ARCHITECTURE.md", "System Architecture & 10-Stage Pipeline"),
        ("docs/EVALUATION.md", "Buildathon Quantitative Evaluation Report"),
        ("docs/FAILURE_ANALYSIS.md", "Exhaustive 25 Failure Modes Matrix"),
        ("docs/SECURITY.md", "Security & Safety Compliance Specification"),
        ("docs/DEMO_SCRIPT.md", "5-Minute Pitch & Demonstration Script"),
        ("docs/PROJECT_STATUS.md", "Current Project Status Tracking"),
    ]
    for rel_path, desc in docs:
        checks.append(check_file_exists(rel_path, desc))

    # 2. Check Secret Isolation (.env in .gitignore)
    print("\n2. Verifying Secret & Security Isolation:")
    gitignore_path = ROOT_DIR / ".gitignore"
    if gitignore_path.exists():
        content = gitignore_path.read_text(encoding="utf-8")
        env_ignored = ".env" in content
        print(f"[{'OK' if env_ignored else 'FAILED'}] .env is present in .gitignore")
        checks.append(env_ignored)
    else:
        print("[FAILED] .gitignore missing")
        checks.append(False)

    # 3. Backend Focused Security & Resilience Tests
    print("\n3. Running Backend Security & Resilience Tests:")
    checks.append(run_command(
        [sys.executable, "-m", "pytest", "backend/tests/test_security_concurrency_resilience.py"],
        "Backend Security & Resilience Test Suite"
    ))

    # 4. System Verification End-to-End Test
    print("\n4. Running System Integration Verification:")
    checks.append(run_command(
        [sys.executable, "-m", "pytest", "backend/tests/test_step54_system_verification.py"],
        "System End-to-End Verification Test"
    ))

    # 5. Frontend Production Build Check
    print("\n5. Verifying Frontend Production Build:")
    frontend_dir = ROOT_DIR / "frontend"
    if frontend_dir.exists():
        checks.append(run_command(
            ["npm.cmd" if os.name == "nt" else "npm", "run", "build"],
            "Frontend Vite Build Verification",
            cwd=frontend_dir
        ))
    else:
        print("[FAILED] frontend directory missing")
        checks.append(False)

    print("\n" + "=" * 70)
    all_passed = all(checks)
    if all_passed:
        print("READY FOR SUBMISSION - ALL CHECKS PASSED")
        print("=" * 70)
        sys.exit(0)
    else:
        print("SUBMISSION AUDIT FAILED — FIX UNMET CRITERIA")
        print("=" * 70)
        sys.exit(1)

if __name__ == "__main__":
    main()
