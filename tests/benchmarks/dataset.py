"""Benchmark dataset loader for accuracy validation.

Manages loading ground truth data and test documents for benchmarking.
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from loguru import logger


@dataclass
class GroundTruth:
    """Ground truth data for a single document."""
    file_id: str
    doc_type: str  # "invoice", "research_paper", "financial", etc.
    text: str  # Expected extracted text
    bounding_boxes: List[Dict[str, Any]]  # List of {text, box: [x1, y1, x2, y2]}
    tables: Optional[List[Dict[str, Any]]] = None  # Table structures
    metadata: Optional[Dict[str, Any]] = None  # Additional info
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GroundTruth':
        """Create GroundTruth from dictionary."""
        return cls(
            file_id=data["file_id"],
            doc_type=data.get("doc_type", "unknown"),
            text=data.get("text", ""),
            bounding_boxes=data.get("bounding_boxes", []),
            tables=data.get("tables"),
            metadata=data.get("metadata")
        )


@dataclass
class TestCase:
    """A single test case with PDF and ground truth."""
    pdf_path: Path
    ground_truth: GroundTruth
    
    @property
    def name(self) -> str:
        """Get test case name."""
        return self.pdf_path.stem
    
    @property
    def doc_type(self) -> str:
        """Get document type."""
        return self.ground_truth.doc_type


class BenchmarkDataset:
    """Manager for benchmark dataset with ground truth.
    
    Expected directory structure:
        tests/data/ground_truth/
            dataset_manifest.json    # List of test files
            invoice_001.pdf
            invoice_001.json         # Ground truth
            research_001.pdf
            research_001.json
            ...
    
    Usage:
        dataset = BenchmarkDataset()
        test_cases = dataset.load_test_cases()
        
        for case in test_cases:
            result = process_pdf(case.pdf_path)
            compare_with_ground_truth(result, case.ground_truth)
    """
    
    def __init__(self, data_dir: str = "tests/data/ground_truth"):
        """Initialize dataset loader.
        
        Args:
            data_dir: Path to ground truth data directory
        """
        self.data_dir = Path(data_dir)
        self.manifest_path = self.data_dir / "dataset_manifest.json"
        
        logger.debug(f"BenchmarkDataset initialized: {self.data_dir}")
    
    def load_test_cases(self, doc_types: Optional[List[str]] = None) -> List[TestCase]:
        """Load all test cases from dataset.
        
        Args:
            doc_types: Optional list of document types to filter
                       (e.g., ["invoice", "research_paper"])
        
        Returns:
            List of TestCase objects
        """
        test_cases = []
        
        # Check if manifest exists
        if self.manifest_path.exists():
            test_cases = self._load_from_manifest(doc_types)
        else:
            logger.warning(f"No manifest found at {self.manifest_path}, scanning directory...")
            test_cases = self._scan_directory(doc_types)
        
        logger.info(f"Loaded {len(test_cases)} test case(s)")
        return test_cases
    
    def _load_from_manifest(self, doc_types: Optional[List[str]]) -> List[TestCase]:
        """Load test cases from manifest file.
        
        Args:
            doc_types: Optional document type filter
            
        Returns:
            List of TestCase objects
        """
        test_cases = []
        
        try:
            with open(self.manifest_path, 'r', encoding='utf-8') as f:
                manifest = json.load(f)
            
            files = manifest.get("files", [])
            
            for file_entry in files:
                file_id = file_entry.get("file_id")
                doc_type = file_entry.get("type", "unknown")
                
                # Filter by doc type if specified
                if doc_types and doc_type not in doc_types:
                    continue
                
                # Load test case
                test_case = self._load_test_case(file_id, doc_type)
                
                if test_case:
                    test_cases.append(test_case)
        
        except Exception as e:
            logger.error(f"Failed to load manifest: {e}")
        
        return test_cases
    
    def _scan_directory(self, doc_types: Optional[List[str]]) -> List[TestCase]:
        """Scan directory for PDF and JSON pairs.
        
        Args:
            doc_types: Optional document type filter
            
        Returns:
            List of TestCase objects
        """
        test_cases = []
        
        # Find all PDF files
        pdf_files = list(self.data_dir.glob("*.pdf"))
        
        for pdf_path in pdf_files:
            file_id = pdf_path.stem
            json_path = pdf_path.with_suffix(".json")
            
            # Check if corresponding JSON exists
            if not json_path.exists():
                logger.warning(f"No ground truth found for {pdf_path.name}")
                continue
            
            # Load ground truth
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    gt_data = json.load(f)
                
                ground_truth = GroundTruth.from_dict(gt_data)
                
                # Filter by doc type
                if doc_types and ground_truth.doc_type not in doc_types:
                    continue
                
                test_case = TestCase(
                    pdf_path=pdf_path,
                    ground_truth=ground_truth
                )
                
                test_cases.append(test_case)
            
            except Exception as e:
                logger.error(f"Failed to load {json_path.name}: {e}")
        
        return test_cases
    
    def _load_test_case(self, file_id: str, doc_type: str) -> Optional[TestCase]:
        """Load a single test case.
        
        Args:
            file_id: File identifier (without extension)
            doc_type: Document type
            
        Returns:
            TestCase or None if failed
        """
        pdf_path = self.data_dir / f"{file_id}.pdf"
        json_path = self.data_dir / f"{file_id}.json"
        
        # Check if files exist
        if not pdf_path.exists():
            logger.warning(f"PDF not found: {pdf_path}")
            return None
        
        if not json_path.exists():
            logger.warning(f"Ground truth not found: {json_path}")
            return None
        
        # Load ground truth
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                gt_data = json.load(f)
            
            ground_truth = GroundTruth.from_dict(gt_data)
            
            return TestCase(
                pdf_path=pdf_path,
                ground_truth=ground_truth
            )
        
        except Exception as e:
            logger.error(f"Failed to load test case {file_id}: {e}")
            return None
    
    def create_sample_manifest(self) -> bool:
        """Create a sample manifest file for reference.
        
        Returns:
            True if created successfully
        """
        sample_manifest = {
            "version": "1.0",
            "description": "Benchmark dataset for accuracy validation",
            "files": [
                {
                    "file_id": "invoice_001",
                    "type": "invoice",
                    "description": "Sample invoice document"
                },
                {
                    "file_id": "research_001",
                    "type": "research_paper",
                    "description": "Sample research paper"
                },
                {
                    "file_id": "financial_001",
                    "type": "financial",
                    "description": "Sample financial document"
                }
            ]
        }
        
        try:
            # Ensure directory exists
            self.data_dir.mkdir(parents=True, exist_ok=True)
            
            with open(self.manifest_path, 'w', encoding='utf-8') as f:
                json.dump(sample_manifest, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Sample manifest created: {self.manifest_path}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to create sample manifest: {e}")
            return False
    
    def create_sample_ground_truth(self, file_id: str, doc_type: str) -> bool:
        """Create a sample ground truth JSON file.
        
        Args:
            file_id: File identifier
            doc_type: Document type
            
        Returns:
            True if created successfully
        """
        sample_gt = {
            "file_id": file_id,
            "doc_type": doc_type,
            "text": "Sample extracted text from the document.",
            "bounding_boxes": [
                {
                    "text": "Sample text",
                    "box": [100, 100, 300, 150],
                    "confidence": 0.95
                },
                {
                    "text": "More text",
                    "box": [100, 200, 400, 250],
                    "confidence": 0.92
                }
            ],
            "tables": [
                {
                    "rows": 5,
                    "cols": 3,
                    "cells": ["Header1", "Header2", "Header3", "Data1", "Data2"],
                    "bbox": [50, 300, 500, 500]
                }
            ],
            "metadata": {
                "page_count": 1,
                "creation_date": "2026-01-15"
            }
        }
        
        try:
            json_path = self.data_dir / f"{file_id}.json"
            
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(sample_gt, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Sample ground truth created: {json_path}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to create sample ground truth: {e}")
            return False
    
    def get_dataset_stats(self) -> Dict[str, Any]:
        """Get statistics about the dataset.
        
        Returns:
            Dictionary with dataset statistics
        """
        test_cases = self.load_test_cases()
        
        # Count by document type
        type_counts = {}
        for case in test_cases:
            doc_type = case.doc_type
            type_counts[doc_type] = type_counts.get(doc_type, 0) + 1
        
        return {
            "total_cases": len(test_cases),
            "type_distribution": type_counts,
            "data_dir": str(self.data_dir),
            "has_manifest": self.manifest_path.exists()
        }
