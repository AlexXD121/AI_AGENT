"""Validation Agent for cross-modal conflict detection.

This agent detects discrepancies between OCR text extraction and 
vision model analysis, particularly for numeric values in tables and charts.

Requirements: 11.1 (Conflict Detection), 11.2 (Normalization), 11.3 (Threshold-based Detection)
"""

import re
from typing import List, Dict, Any, Optional
from loguru import logger

from local_body.agents.base import BaseAgent
from local_body.core.datamodels import Document, Region, Conflict, ConflictType, RegionType


class ValidationAgent(BaseAgent):
    """Agent for detecting conflicts between OCR and vision extraction."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(agent_type="validation", config=config)
        
        self.conflict_threshold = self.get_config("conflict_threshold", 0.15)
        logger.info(f"ValidationAgent initialized (threshold: {self.conflict_threshold})")
    
    def process(self, document: Document) -> Document:
        """Process document for validation (not used directly, use validate instead).
        
        Args:
            document: Document to validate
            
        Returns:
            Unchanged document (validation results are returned separately)
        """
        # ValidationAgent doesn't modify the document, just detects conflicts
        logger.info(f"ValidationAgent process called for document {document.id}")
        return document
    
    @staticmethod
    def extract_numeric_value(text: str) -> Optional[float]:
        """Extract numeric value from text string.
        
        Handles common formats:
        - Currency with multipliers: "$5.2M", "$100M"
        - Percentages: "15%", "0.15"
        - Large numbers: "5.2M", "1.5B", "3.4K

"
        - Comma-separated: "1,234,567"
        
        Args:
            text: Text containing numeric value
            
        Returns:
            Extracted float value or None if not found
        """
        if not text:
            return None
        
        # Handle percentages first
        if '%' in text:
            cleaned = re.sub(r'[$€£¥%]', '', text).strip()
            match = re.search(r'[-+]?\d*\.?\d+', cleaned)
            if match:
                try:
                    return float(match.group()) / 100.0
                except ValueError:
                    pass
        
        # Handle multipliers (K, M, B, T) with optional currency
        multipliers = {
            'K': 1_000,
            'M': 1_000_000,
            'B': 1_000_000_000,
            'T': 1_000_000_000_000
        }
        
        for suffix, multiplier in multipliers.items():
            # Pattern: optional currency, digits with optional comma/dot, then suffix
            pattern = r'[$€£¥]?\s*([-+]?\d+(?:[,\.]\d+)*)\s*' + suffix
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                num_str = match.group(1).replace(',', '')
                try:
                    return float(num_str) * multiplier
                except ValueError:
                    pass
        
        # Remove currency symbols for regular numbers
        cleaned = re.sub(r'[$€£¥]', '', text).strip().replace(',', '')
        
        # Extract first number found
        match = re.search(r'[-+]?\d*\.?\d+', cleaned)
        if match:
            try:
                return float(match.group())
            except ValueError:
                pass
        
        return None
    
    def validate(
        self,
        document: Document,
        vision_results: Optional[Dict[str, Any]] = None
    ) -> List[Conflict]:
        """Detect conflicts between OCR and vision extraction.
        
        Args:
            document: Document with OCR-extracted regions
            vision_results: Dictionary mapping region_id to vision analysis text
            
        Returns:
            List of detected conflicts
        """
        conflicts = []
        
        if not vision_results:
            logger.info("No vision results provided, skipping validation")
            return conflicts
        
        logger.info(f"Validating document {document.id} with {len(vision_results)} vision results")
        
        # Iterate through all regions in document
        for page in document.pages:
            for region in page.regions:
                # Skip if no vision result for this region
                if region.id not in vision_results:
                    continue
                
                # Get OCR text
                ocr_text = None
                if hasattr(region.content, 'text'):
                    ocr_text = region.content.text
                
                if not ocr_text:
                    continue
                
                # Get vision text
                vision_text = vision_results.get(region.id, '')
                if not vision_text:
                    continue
                
                # Extract numeric values
                ocr_value = self.extract_numeric_value(ocr_text)
                vision_value = self.extract_numeric_value(vision_text)
                
                if ocr_value is None or vision_value is None:
                    logger.debug(f"Region {region.id}: No numeric values found")
                    continue
                
                # Calculate discrepancy
                if max(abs(ocr_value), abs(vision_value)) == 0:
                    discrepancy = 0.0
                else:
                    discrepancy = abs(ocr_value - vision_value) / max(abs(ocr_value), abs(vision_value))
                
                # Check against threshold
                if discrepancy > self.conflict_threshold:
                    conflict = Conflict(
                        region_id=region.id,
                        conflict_type=ConflictType.VALUE_MISMATCH,
                        text_value=ocr_value,
                        vision_value=vision_value,
                        discrepancy_percentage=discrepancy,
                        confidence_scores={
                            'text': region.confidence,
                            'vision': 0.8  # Default vision confidence
                        }
                    )
                    
                    # Calculate impact score
                    region_type_str = region.region_type.value if isinstance(region.region_type, RegionType) else str(region.region_type)
                    conflict.update_impact_score(region_type_str)
                    
                    conflicts.append(conflict)
                    logger.warning(
                        f"Conflict detected in region {region.id}: "
                        f"OCR={ocr_value}, Vision={vision_value}, "
                        f"Discrepancy={discrepancy:.2%}"
                    )
                else:
                    logger.debug(
                        f"Region {region.id}: Values match within threshold "
                        f"(OCR={ocr_value}, Vision={vision_value}, Discrepancy={discrepancy:.2%})"
                    )
        
        logger.info(f"Validation complete: {len(conflicts)} conflicts detected")
        return conflicts
