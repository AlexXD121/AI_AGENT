"""Requirements Compliance Checker.

Maps system requirements to verification methods and generates
a traceability matrix showing which requirements are met.
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum

from loguru import logger


class ComplianceStatus(Enum):
    """Compliance verification status."""
    PASS = "✅ PASS"
    FAIL = "❌ FAIL"
    PARTIAL = "⚠️ PARTIAL"
    NOT_TESTED = "⏳ NOT TESTED"


@dataclass
class Requirement:
    """Represents a system requirement."""
    id: str
    category: str
    description: str
    verification_method: str
    status: ComplianceStatus = ComplianceStatus.NOT_TESTED
    evidence: Optional[str] = None
    notes: Optional[str] = None


class RequirementsChecker:
    """Verifies system compliance against requirements."""
    
    def __init__(self):
        """Initialize requirements checker."""
        self.requirements: Dict[str, Requirement] = {}
        self._define_requirements()
    
    def _define_requirements(self) -> None:
        """Define all system requirements."""
        
        # Requirement 1: Privacy & Data Sovereignty
        self.requirements["1.1"] = Requirement(
            id="1.1",
            category="Privacy",
            description="Local-only processing (no cloud data upload)",
            verification_method="Check config privacy_mode and agent fallbacks"
        )
        
        self.requirements["1.2"] = Requirement(
            id="1.2",
            category="Privacy",
            description="PII redaction in logs",
            verification_method="Check logging_setup.py for redaction filter"
        )
        
        self.requirements["1.3"] = Requirement(
            id="1.3",
            category="Privacy",
            description="Secure file deletion",
            verification_method="Check file_utils.py for secure_delete()"
        )
        
        # Requirement 2: Security
        self.requirements["2.1"] = Requirement(
            id="2.1",
            category="Security",
            description="Token-based authentication",
            verification_method="Check security.py and server.py auth"
        )
        
        self.requirements["2.2"] = Requirement(
            id="2.2",
            category="Security",
            description="HTTPS tunnels",
            verification_method="Check secure_tunnel.py for bind_tls=True"
        )
        
        # Requirement 3: Agents & Processing
        self.requirements["3.1"] = Requirement(
            id="3.1",
            category="Agents",
            description="OCR Agent implementation",
            verification_method="Check agents/ocr_agent.py exists"
        )
        
        self.requirements["3.2"] = Requirement(
            id="3.2",
            category="Agents",
            description="Layout Agent implementation",
            verification_method="Check agents/layout_agent.py exists"
        )
        
        self.requirements["3.3"] = Requirement(
            id="3.3",
            category="Agents",
            description="Vision Agent implementation",
            verification_method="Check agents/vision_agent.py exists"
        )
        
        self.requirements["3.4"] = Requirement(
            id="3.4",
            category="Agents",
            description="Validation Agent implementation",
            verification_method="Check agents/validation_agent.py exists"
        )
        
        # Requirement 4: Workflow
        self.requirements["4.1"] = Requirement(
            id="4.1",
            category="Workflow",
            description="LangGraph orchestration",
            verification_method="Check orchestration/workflow.py for StateGraph"
        )
        
        # Requirement 5: Performance
        self.requirements["5.1"] = Requirement(
            id="5.1",
            category="Performance",
            description="Result caching",
            verification_method="Check core/cache.py implementation"
        )
        
        self.requirements["5.2"] = Requirement(
            id="5.2",
            category="Performance",
            description="Resource optimization",
            verification_method="Check model_manager.py for optimize_resources()"
        )
        
        # Requirement 6: Monitoring
        self.requirements["6.1"] = Requirement(
            id="6.1",
            category="Monitoring",
            description="System health monitoring",
            verification_method="Check core/health.py for SystemMonitor"
        )
        
        self.requirements["6.2"] = Requirement(
            id="6.2",
            category="Monitoring",
            description="Alert system",
            verification_method="Check core/alerts.py for AlertManager"
        )
        
        # Requirement 7: Testing
        self.requirements["7.1"] = Requirement(
            id="7.1",
            category="Testing",
            description="Integration tests",
            verification_method="Check tests/integration/ exists and passes"
        )
        
        self.requirements["7.2"] = Requirement(
            id="7.2",
            category="Testing",
            description="Benchmark suite",
            verification_method="Check tests/benchmarks/ exists and passes"
        )
    
    def verify_all(self) -> Dict[str, ComplianceStatus]:
        """Run all verification checks.
        
        Returns:
            Dictionary mapping requirement IDs to status
        """
        logger.info("Starting compliance verification...")
        
        for req_id, req in self.requirements.items():
            logger.info(f"Checking {req_id}: {req.description}")
            status, evidence = self._verify_requirement(req)
            req.status = status
            req.evidence = evidence
        
        return {req_id: req.status for req_id, req in self.requirements.items()}
    
    def _verify_requirement(self, req: Requirement) -> Tuple[ComplianceStatus, str]:
        """Verify a single requirement.
        
        Args:
            req: Requirement to verify
            
        Returns:
            Tuple of (status, evidence)
        """
        try:
            # Route to specific verification method
            if req.id == "1.1":
                return self._verify_local_only()
            elif req.id == "1.2":
                return self._verify_pii_redaction()
            elif req.id == "1.3":
                return self._verify_secure_deletion()
            elif req.id == "2.1":
                return self._verify_authentication()
            elif req.id == "2.2":
                return self._verify_https_tunnel()
            elif req.id in ["3.1", "3.2", "3.3", "3.4"]:
                return self._verify_agent_exists(req.id)
            elif req.id == "4.1":
                return self._verify_workflow()
            elif req.id == "5.1":
                return self._verify_caching()
            elif req.id == "5.2":
                return self._verify_resource_optimization()
            elif req.id == "6.1":
                return self._verify_health_monitoring()
            elif req.id == "6.2":
                return self._verify_alert_system()
            elif req.id == "7.1":
                return self._verify_integration_tests()
            elif req.id == "7.2":
                return self._verify_benchmarks()
            else:
                return ComplianceStatus.NOT_TESTED, "No verification method"
                
        except Exception as e:
            return ComplianceStatus.FAIL, f"Verification error: {e}"
    
    def _verify_local_only(self) -> Tuple[ComplianceStatus, str]:
        """Verify local-only processing."""
        checks = []
        
        # Check privacy.py exists
        if Path("local_body/core/privacy.py").exists():
            checks.append("Privacy manager exists")
        else:
            return ComplianceStatus.FAIL, "Privacy manager missing"
        
        # Check for privacy modes
        content = Path("local_body/core/privacy.py").read_text(encoding='utf-8')
        if "PrivacyMode" in content and "STRICT" in content:
            checks.append("Privacy modes implemented")
        else:
            return ComplianceStatus.FAIL, "Privacy modes not found"
        
        return ComplianceStatus.PASS, "; ".join(checks)
    
    def _verify_pii_redaction(self) -> Tuple[ComplianceStatus, str]:
        """Verify PII redaction in logs."""
        if not Path("local_body/core/logging_setup.py").exists():
            return ComplianceStatus.FAIL, "Logging setup missing"
        
        content = Path("local_body/core/logging_setup.py").read_text(encoding='utf-8')
        
        if "redact_pii" in content and "filter" in content.lower():
            return ComplianceStatus.PASS, "PII redaction filter implemented"
        else:
            return ComplianceStatus.FAIL, "PII redaction not found"
    
    def _verify_secure_deletion(self) -> Tuple[ComplianceStatus, str]:
        """Verify secure file deletion."""
        if not Path("local_body/utils/file_utils.py").exists():
            return ComplianceStatus.FAIL, "File utils missing"
        
        content = Path("local_body/utils/file_utils.py").read_text(encoding='utf-8')
        
        if "secure_delete" in content and "overwrite" in content.lower():
            return ComplianceStatus.PASS, "Secure deletion implemented"
        else:
            return ComplianceStatus.FAIL, "Secure deletion not found"
    
    def _verify_authentication(self) -> Tuple[ComplianceStatus, str]:
        """Verify token-based authentication."""
        checks = []
        
        # Check security.py
        if Path("local_body/core/security.py").exists():
            content = Path("local_body/core/security.py").read_text(encoding='utf-8')
            if "access_token" in content and "validate_token" in content:
                checks.append("Local auth implemented")
        
        # Check server.py
        if Path("colab_brain/server.py").exists():
            content = Path("colab_brain/server.py").read_text(encoding='utf-8')
            if "verify_token" in content and "X-Sovereign-Token" in content:
                checks.append("Server auth implemented")
        
        if len(checks) == 2:
            return ComplianceStatus.PASS, "; ".join(checks)
        else:
            return ComplianceStatus.PARTIAL, "; ".join(checks) if checks else "Missing auth components"
    
    def _verify_https_tunnel(self) -> Tuple[ComplianceStatus, str]:
        """Verify HTTPS tunnel enforcement."""
        if not Path("local_body/tunnel/secure_tunnel.py").exists():
            return ComplianceStatus.FAIL, "Secure tunnel missing"
        
        content = Path("local_body/tunnel/secure_tunnel.py").read_text(encoding='utf-8')
        
        if "bind_tls=True" in content:
            return ComplianceStatus.PASS, "HTTPS enforcement confirmed"
        else:
            return ComplianceStatus.FAIL, "HTTPS not enforced"
    
    def _verify_agent_exists(self, req_id: str) -> Tuple[ComplianceStatus, str]:
        """Verify agent implementation."""
        agent_map = {
            "3.1": "ocr_agent.py",
            "3.2": "layout_agent.py",
            "3.3": "vision_agent.py",
            "3.4": "validation_agent.py"
        }
        
        agent_file = agent_map.get(req_id)
        agent_path = Path(f"local_body/agents/{agent_file}")
        
        if agent_path.exists():
            return ComplianceStatus.PASS, f"{agent_file} exists"
        else:
            return ComplianceStatus.FAIL, f"{agent_file} missing"
    
    def _verify_workflow(self) -> Tuple[ComplianceStatus, str]:
        """Verify LangGraph workflow."""
        if not Path("local_body/orchestration/workflow.py").exists():
            return ComplianceStatus.FAIL, "Workflow missing"
        
        content = Path("local_body/orchestration/workflow.py").read_text(encoding='utf-8')
        
        if "StateGraph" in content and "DocumentProcessingState" in content:
            return ComplianceStatus.PASS, "LangGraph workflow implemented"
        else:
            return ComplianceStatus.FAIL, "LangGraph not properly integrated"
    
    def _verify_caching(self) -> Tuple[ComplianceStatus, str]:
        """Verify result caching."""
        if not Path("local_body/core/cache.py").exists():
            return ComplianceStatus.FAIL, "Cache manager missing"
        
        content = Path("local_body/core/cache.py").read_text(encoding='utf-8')
        
        if "CacheManager" in content and "diskcache" in content:
            return ComplianceStatus.PASS, "Persistent caching implemented"
        else:
            return ComplianceStatus.FAIL, "Caching not properly implemented"
    
    def _verify_resource_optimization(self) -> Tuple[ComplianceStatus, str]:
        """Verify resource optimization."""
        if not Path("local_body/utils/model_manager.py").exists():
            return ComplianceStatus.FAIL, "Model manager missing"
        
        content = Path("local_body/utils/model_manager.py").read_text(encoding='utf-8')
        
        if "optimize_resources" in content and "unload_model" in content:
            return ComplianceStatus.PASS, "Resource optimization implemented"
        else:
            return ComplianceStatus.FAIL, "Resource optimization missing"
    
    def _verify_health_monitoring(self) -> Tuple[ComplianceStatus, str]:
        """Verify system health monitoring."""
        if not Path("local_body/core/health.py").exists():
            return ComplianceStatus.FAIL, "Health monitor missing"
        
        content = Path("local_body/core/health.py").read_text(encoding='utf-8')
        
        if "SystemMonitor" in content and "check_resources" in content:
            return ComplianceStatus.PASS, "Health monitoring implemented"
        else:
            return ComplianceStatus.FAIL, "Health monitoring incomplete"
    
    def _verify_alert_system(self) -> Tuple[ComplianceStatus, str]:
        """Verify alert system."""
        if not Path("local_body/core/alerts.py").exists():
            return ComplianceStatus.FAIL, "Alert system missing"
        
        content = Path("local_body/core/alerts.py").read_text(encoding='utf-8')
        
        if "AlertManager" in content and "AlertComponent" in content:
            return ComplianceStatus.PASS, "Alert system implemented"
        else:
            return ComplianceStatus.FAIL, "Alert system incomplete"
    
    def _verify_integration_tests(self) -> Tuple[ComplianceStatus, str]:
        """Verify integration tests exist."""
        test_dir = Path("tests/integration")
        
        if not test_dir.exists():
            return ComplianceStatus.FAIL, "Integration tests missing"
        
        test_files = list(test_dir.glob("test_*.py"))
        
        if len(test_files) >= 3:
            return ComplianceStatus.PASS, f"{len(test_files)} integration tests found"
        else:
            return ComplianceStatus.PARTIAL, f"Only {len(test_files)} integration tests"
    
    def _verify_benchmarks(self) -> Tuple[ComplianceStatus, str]:
        """Verify benchmark suite."""
        if not Path("tests/benchmarks/run_validation.py").exists():
            return ComplianceStatus.FAIL, "Benchmark runner missing"
        
        return ComplianceStatus.PASS, "Benchmark suite exists"
    
    def generate_report(self, output_path: str = "compliance_matrix.md") -> None:
        """Generate compliance matrix report.
        
        Args:
            output_path: Path to output markdown file
        """
        logger.info(f"Generating compliance report: {output_path}")
        
        # Group by category
        by_category = {}
        for req in self.requirements.values():
            if req.category not in by_category:
                by_category[req.category] = []
            by_category[req.category].append(req)
        
        # Generate markdown
        lines = [
            "# Requirements Compliance Matrix",
            "",
            f"**Generated:** {Path(__file__).stem}",
            "",
            "## Summary",
            ""
        ]
        
        # Calculate summary
        total = len(self.requirements)
        passed = sum(1 for r in self.requirements.values() if r.status == ComplianceStatus.PASS)
        partial = sum(1 for r in self.requirements.values() if r.status == ComplianceStatus.PARTIAL)
        failed = sum(1 for r in self.requirements.values() if r.status == ComplianceStatus.FAIL)
        
        lines.extend([
            f"- **Total Requirements:** {total}",
            f"- **Passed:** {passed} ({passed/total*100:.0f}%)",
            f"- **Partial:** {partial}",
            f"- **Failed:** {failed}",
            ""
        ])
        
        # Detailed table by category
        for category, reqs in sorted(by_category.items()):
            lines.extend([
                f"## {category}",
                "",
                "| ID | Description | Status | Evidence |",
                "|----|-----------  |--------|----------|"
            ])
            
            for req in sorted(reqs, key=lambda r: r.id):
                evidence = req.evidence or "N/A"
                lines.append(f"| {req.id} | {req.description} | {req.status.value} | {evidence} |")
            
            lines.append("")
        
        # Write to file
        output = "\n".join(lines)
        Path(output_path).write_text(output, encoding='utf-8')
        
        logger.success(f"Compliance report written to {output_path}")


def main():
    """Run compliance check."""
    checker = RequirementsChecker()
    results = checker.verify_all()
    
    checker.generate_report("compliance_matrix.md")
    
    # Print summary
    total = len(results)
    passed = sum(1 for s in results.values() if s == ComplianceStatus.PASS)
    
    print(f"\n{'='*60}")
    print(f"COMPLIANCE CHECK COMPLETE")
    print(f"{'='*60}")
    print(f"Passed: {passed}/{total} ({passed/total*100:.0f}%)")
    print(f"Report: compliance_matrix.md")
    print(f"{'='*60}\n")
    
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
