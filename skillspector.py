For your Tachyon SDK 3.0 skill-registration workflow, I would turn your existing graph.invoke() logic into a reusable security-validation service.

The important improvement is that a SAFE recommendation alone is not sufficient for production approval. You also need to verify that the scan completed, required analyzers were available, the result is valid, and the skill hasn’t changed between scanning and registration.

NVIDIA’s SkillSpector exposes the fields needed for much of this, including risk_score, risk_severity, risk_recommendation, filtered_findings, and scan-completeness information. GitHub +2

1. Recommended validation policy

Condition	Registration decision
SAFE, complete scan, no blocking findings	Approve
CAUTION	Manual review
DO_NOT_INSTALL	Reject
Missing or malformed risk score	Reject
Scanner exception or timeout	Reject
Incomplete scan	Reject
Required LLM analysis unavailable	Reject
Skill files modified after validation	Require rescan
Unexpected scanner result	Reject

I would also distinguish REJECTED from ERROR: a malicious skill should be rejected, while a scanner infrastructure failure should be reported as a validation error. Neither should result in registration.

The implementation below uses your existing Python API rather than introducing a CLI dependency.

2. Production-oriented implementation

This version includes configurable policies, structured responses, logging, input validation, timeout handling, scan-completeness checks, YARA-related failure handling, file fingerprinting, and cleanup of temporary scanner resources.

# skill_validator.py
from __future__ import annotations
import hashlib
import logging
import multiprocessing as mp
import os
import queue
import shutil
import stat
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any
logger = logging.getLogger(__name__)
class Decision(str, Enum):
    APPROVED = "APPROVED"
    REVIEW = "REVIEW"
    REJECTED = "REJECTED"
    ERROR = "ERROR"
@dataclass(frozen=True)
class ValidationPolicy:
    use_llm: bool = False
    timeout_seconds: int = 120
    max_files: int = 500
    max_total_bytes: int = 20 * 1024 * 1024
    allow_caution: bool = False
    require_complete: bool = True
    reject_any_finding: bool = False
    # Set True only if the integration explicitly
    # requires LLM-based semantic inspection.
    require_llm: bool = False
@dataclass
class ValidationResult:
    decision: Decision
    approved: bool
    skill_path: str
    risk_score: int | None = None
    severity: str | None = None
    recommendation: str | None = None
    findings: list[dict[str, Any]] = field(
        default_factory=list
    )
    reasons: list[str] = field(default_factory=list)
    fingerprint: str | None = None
    scanner_version: str | None = None
    scan_complete: bool = False
class ValidationError(Exception):
    pass
def fingerprint_directory(
    root: Path,
    policy: ValidationPolicy,
) -> str:
    """Hash names, permissions, and file contents.
    Reject symlinks and non-regular filesystem objects.
    """
    digest = hashlib.sha256()
    count = 0
    total_bytes = 0
    for base, dirs, files in os.walk(
        root, followlinks=False
    ):
        base_path = Path(base)
        for name in sorted(dirs + files):
            entry = base_path / name
            info = entry.lstat()
            if stat.S_ISLNK(info.st_mode):
                raise ValidationError(
                    f"Symlink not allowed: {entry}"
                )
            if not (
                stat.S_ISREG(info.st_mode)
                or stat.S_ISDIR(info.st_mode)
            ):
                raise ValidationError(
                    f"Unsupported file type: {entry}"
                )
        dirs.sort()
        files.sort()
        for name in files:
            path = base_path / name
            relative = path.relative_to(root).as_posix()
            info = path.lstat()
            count += 1
            total_bytes += info.st_size
            if count > policy.max_files:
                raise ValidationError(
                    "Skill exceeds file-count limit"
                )
            if total_bytes > policy.max_total_bytes:
                raise ValidationError(
                    "Skill exceeds size limit"
                )
            digest.update(relative.encode("utf-8"))
            digest.update(b"\0")
            digest.update(str(info.st_mode & 0o777).encode())
            digest.update(b"\0")
            with path.open("rb") as handle:
                while chunk := handle.read(1024 * 1024):
                    digest.update(chunk)
    return digest.hexdigest()
def _scan_worker(
    skill_path: str,
    use_llm: bool,
    output: mp.Queue,
) -> None:
    """Run scanner in a separate process."""
    result = None
    try:
        from skillspector import graph
        result = graph.invoke({
            "input_path": skill_path,
            "output_format": "json",
            "use_llm": use_llm,
        })
        if not isinstance(result, dict):
            raise ValueError(
                "SkillSpector returned a non-dict result"
            )
        # Only return fields needed by the policy gate.
        payload = {
            "risk_score": result.get("risk_score"),
            "risk_severity": result.get("risk_severity"),
            "risk_recommendation":
                result.get("risk_recommendation"),
            "filtered_findings":
                result.get("filtered_findings"),
            "analysis_completeness":
                result.get("analysis_completeness"),
            "execution_successful":
                result.get("execution_successful"),
            "metadata": result.get("metadata"),
        }
        output.put(("OK", payload))
    except Exception as exc:
        output.put((
            "ERROR",
            {
                "type": type(exc).__name__,
                "message": str(exc)[:1000],
            },
        ))
    finally:
        if isinstance(result, dict):
            temp_dir = result.get("temp_dir_for_cleanup")
            if isinstance(temp_dir, str) and temp_dir:
                # For this local-directory-only integration,
                # no temporary input should be created.
                # Do not delete arbitrary paths returned
                # by a scanner without verifying ownership.
                logger.warning(
                    "Scanner reported temporary path: %s",
                    temp_dir,
                )
class SkillValidator:
    def __init__(
        self,
        policy: ValidationPolicy | None = None,
    ):
        self.policy = policy or ValidationPolicy()
        if self.policy.require_llm and not self.policy.use_llm:
            raise ValueError(
                "require_llm requires use_llm=True"
            )
    def validate(self, skill_path: str) -> ValidationResult:
        path = Path(skill_path).absolute()
        def failure(reason: str) -> ValidationResult:
            return ValidationResult(
                decision=Decision.ERROR,
                approved=False,
                skill_path=str(path),
                reasons=[reason],
            )
        if not path.is_dir() or path.is_symlink():
            return failure("Invalid skill directory")
        if not (path / "SKILL.md").is_file():
            return failure("SKILL.md is missing")
        try:
            before = fingerprint_directory(
                path, self.policy
            )
        except (OSError, ValidationError) as exc:
            return failure(str(exc))
        # spawn is compatible with macOS and avoids
        # inheriting an initialized scanner runtime.
        ctx = mp.get_context("spawn")
        output = ctx.Queue(maxsize=1)
        process = ctx.Process(
            target=_scan_worker,
            args=(
                str(path),
                self.policy.use_llm,
                output,
            ),
        )
        try:
            process.start()
            process.join(self.policy.timeout_seconds)
            if process.is_alive():
                process.terminate()
                process.join(5)
                if process.is_alive():
                    process.kill()
                    process.join()
                return failure("Skill scan timed out")
            try:
                status, data = output.get(timeout=2)
            except queue.Empty:
                return failure(
                    "Scanner exited without a result"
                )
            if status != "OK":
                logger.error(
                    "Skill scanner error: %s",
                    data,
                )
                return failure(
                    "SkillSpector execution failed: "
                    + data.get("type", "Unknown")
                )
            try:
                after = fingerprint_directory(
                    path, self.policy
                )
            except (OSError, ValidationError) as exc:
                return failure(str(exc))
            if before != after:
                return failure(
                    "Skill changed during validation"
                )
            return self._evaluate(
                str(path), data, after
            )
        except Exception:
            logger.exception("Unexpected validation failure")
            return failure("Internal validation failure")
        finally:
            if process.is_alive():
                process.terminate()
                process.join()
            output.close()
            output.join_thread()
    def _evaluate(
        self,
        path: str,
        data: dict[str, Any],
        fingerprint: str,
    ) -> ValidationResult:
        reasons: list[str] = []
        score = data.get("risk_score")
        severity = data.get("risk_severity")
        recommendation = data.get("risk_recommendation")
        findings = data.get("filtered_findings")
        metadata = data.get("metadata")
        if (
            type(score) is not int
            or not 0 <= score <= 100
            or recommendation not in (
                "SAFE", "CAUTION", "DO_NOT_INSTALL"
            )
            or severity not in (
                "LOW", "MEDIUM", "HIGH", "CRITICAL"
            )
            or not isinstance(findings, list)
            or not all(
                isinstance(f, dict) for f in findings
            )
        ):
            return ValidationResult(
                decision=Decision.ERROR,
                approved=False,
                skill_path=path,
                reasons=["Invalid scanner result schema"],
            )
        expected = {
            "LOW": "SAFE",
            "MEDIUM": "CAUTION",
            "HIGH": "DO_NOT_INSTALL",
            "CRITICAL": "DO_NOT_INSTALL",
        }
        if expected[severity] != recommendation:
            return ValidationResult(
                decision=Decision.ERROR,
                approved=False,
                skill_path=path,
                reasons=["Inconsistent risk classification"],
            )
        completeness = data.get("analysis_completeness")
        # Strict policy: missing completeness evidence
        # is not interpreted as a complete scan.
        complete = (
            isinstance(completeness, dict)
            and completeness.get("is_complete") is True
        )
        if data.get("execution_successful") is False:
            reasons.append("Scanner execution unsuccessful")
        if self.policy.require_complete and not complete:
            reasons.append("Scan completeness not confirmed")
        if self.policy.require_llm:
            if not isinstance(metadata, dict):
                reasons.append("LLM metadata missing")
            elif (
                metadata.get("llm_requested") is not True
                or metadata.get("llm_available") is not True
                or metadata.get("llm_error")
            ):
                reasons.append("Required LLM scan unavailable")
        if recommendation == "DO_NOT_INSTALL":
            reasons.append("High or critical security risk")
        elif recommendation == "CAUTION":
            if not self.policy.allow_caution:
                reasons.append("Manual review required")
        if self.policy.reject_any_finding and findings:
            reasons.append("Active security findings present")
        if (
            data.get("execution_successful") is False
            or (self.policy.require_complete and not complete)
            or (
                self.policy.require_llm
                and (
                    not isinstance(metadata, dict)
                    or metadata.get("llm_requested") is not True
                    or metadata.get("llm_available") is not True
                    or bool(metadata.get("llm_error"))
                )
            )
        ):
            decision = Decision.ERROR
        elif recommendation == "DO_NOT_INSTALL":
            decision = Decision.REJECTED
        elif self.policy.reject_any_finding and findings:
            decision = Decision.REJECTED
        elif recommendation == "CAUTION" and (
            not self.policy.allow_caution
        ):
            decision = Decision.REVIEW
        else:
            decision = Decision.APPROVED
        return ValidationResult(
            decision=decision,
            approved=decision == Decision.APPROVED,
            skill_path=path,
            risk_score=score,
            severity=severity,
            recommendation=recommendation,
            findings=findings,
            reasons=reasons,
            fingerprint=fingerprint,
            scanner_version=(
                metadata.get("skillspector_version")
                if isinstance(metadata, dict)
                else None
            ),
            scan_complete=complete,
        )

This is a strong application-level starting point, but two deployment limitations are important: a worker process is not a security sandbox, and the fingerprint check does not eliminate the time-of-check/time-of-use race if another process can modify the directory after validation. For a security boundary, run scanning in an isolated container or job, and register an immutable artifact identified by its digest.

Also, the code deliberately fails closed if your installed SkillSpector version does not return analysis_completeness. That is preferable to assuming success, but you’ll need to verify that field against your installed version.

3. How to call it from your existing code

Create a separate entry point:

# main.py
from dataclasses import asdict
import json
from skill_validator import (
    SkillValidator,
    ValidationPolicy,
)
def main():
    validator = SkillValidator(
        ValidationPolicy(
            use_llm=False,
            timeout_seconds=120,
            max_files=500,
            max_total_bytes=20 * 1024 * 1024,
            allow_caution=False,
            require_complete=True,
            reject_any_finding=False,
        )
    )
    result = validator.validate(
        "/path/to/my-skill"
    )
    print(json.dumps(
        asdict(result),
        indent=2,
        default=str,
    ))
    if result.approved:
        print("Skill approved for registration")
    else:
        print(
            "Skill registration blocked:",
            result.decision.value,
        )
if __name__ == "__main__":
    main()

On macOS, the if __name__ == "__main__" guard is important because the implementation uses Python’s spawn multiprocessing mode.

4. Integrating with your skill registry

I recommend keeping validation and registration separate:

def register_skill(skill_path, registry, validator):
    validation = validator.validate(skill_path)
    if not validation.approved:
        return {
            "registered": False,
            "decision": validation.decision.value,
            "reasons": validation.reasons,
            "findings": validation.findings,
        }
    # Production requirement:
    # Copy the validated files to immutable storage,
    # verify the digest, and register that artifact.
    artifact = registry.stage_immutable(skill_path)
    if artifact.sha256 != validation.fingerprint:
        # Both systems must use the same canonical
        # directory fingerprint algorithm.
        raise ValueError(
            "Skill artifact digest mismatch"
        )
    registry.register(
        artifact=artifact,
        security_metadata={
            "risk_score": validation.risk_score,
            "severity": validation.severity,
            "scanner_version":
                validation.scanner_version,
            "fingerprint": validation.fingerprint,
        },
    )
    return {
        "registered": True,
        "decision": "APPROVED",
    }

Here, registry.stage_immutable() and registry.register() are interfaces for your own registry, not existing SkillSpector methods. The staging operation must use the same fingerprint algorithm and prevent modification after validation.

5. Additional safeguards I’d add before enterprise deployment

Area	Recommendation
Security	Run SkillSpector in an isolated worker with restricted filesystem access, network egress and privileges
Reliability	Enforce scanner timeout and resource limits externally
Audit	Persist scan findings, scanner version, policy version and artifact digest
Performance	Cache successful scans by artifact digest and scanner/policy versions
Governance	Require approval for CAUTION; never automatically register DO_NOT_INSTALL
Coverage	Verify analyzer execution and completeness, not just the risk score
Lifecycle	Rescan whenever a skill changes or relevant detection rules are updated

NVIDIA also documents a broader trust pipeline through SkillEvaluator, which includes schema validation, deduplication and evaluation of whether a skill actually improves agent behavior. That is worth considering if your SDK will maintain a central enterprise skill catalog. NVIDIA Skill Documentation

One architectural recommendation for Tachyon SDK 3.0: Put this validation service in the skill registration layer, independently of your ADK and LangGraph adapters. Both frameworks should consume only approved, versioned skills from the same registry. That prevents either adapter from bypassing your security gate.

For your initial implementation, use_llm=False is a sensible deterministic baseline. Later, you can enable LLM-based semantic scanning for higher-risk skills, while retaining static analysis and explicit approval policies.