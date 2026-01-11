"""Resolution Agent for intelligent conflict resolution.

This agent applies contextual strategies to automatically resolve conflicts
between OCR and Vision extraction when high confidence decisions can be made.

Requirements: 7.1 (Contextual Resolution), 7.2 (Auto-Resolution Logic)
"""

from typing import List, Dict, Any
from loguru import logger

from local_body.agents.base import BaseAgent
from local_body.core.datamodels import (
    Document, 
    Conflict, 
    ConflictResolution, 
    ResolutionMethod,
    RegionType
)


class ResolutionStrategy:
    """Resolution strategy identifiers."""
    CONFIDENCE_DOMINANCE = "confidence_dominance"
    REGION_BIAS_TABLE = "region_bias_table"
    REGION_BIAS_CHART = "region_bias_chart"
    FORMAT_VALIDATION = "format_validation"
    MANUAL_REVIEW_REQUIRED = "manual_review_required"


class ResolutionAgent(BaseAgent):
    """Agent for automatically resolving conflicts using contextual strategies.
    
    Implements intelligent heuristics to auto-resolve OCR vs Vision conflicts
    when high-confidence decisions can be made, reducing manual review workload.
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(agent_type="resolution", config=config)
        
        # Thresholds for automatic resolution
        self.high_confidence_threshold = self.get_config("high_confidence_threshold", 0.90)
        self.low_confidence_threshold = self.get_config("low_confidence_threshold", 0.60)
        self.reasonable_confidence = self.get_config("reasonable_confidence", 0.80)
        self.massive_discrepancy_threshold = self.get_config("massive_discrepancy", 0.50)
        
        logger.info(
            f"ResolutionAgent initialized (high_conf: {self.high_confidence_threshold}, "
            f"low_conf: {self.low_confidence_threshold})"
        )
    
    def process(self, document: Document) -> Document:
        """Process document (not used directly, use resolve instead).
        
        Args:
            document: Document to process
            
        Returns:
            Unchanged document
        """
        logger.info(f"ResolutionAgent process called for document {document.id}")
        return document
    
    def resolve(
        self, 
        document: Document, 
        conflicts: List[Conflict]
    ) -> List[ConflictResolution]:
        """Resolve conflicts using contextual strategies.
        
        Args:
            document: Document containing the conflicts
            conflicts: List of detected conflicts
            
        Returns:
            List of conflict resolutions
        """
        if not conflicts:
            logger.info("No conflicts to resolve")
            return []
        
        logger.info(f"Resolving {len(conflicts)} conflicts")
        resolutions = []
        
        for conflict in conflicts:
            resolution = self._resolve_single_conflict(document, conflict)
            if resolution:
                resolutions.append(resolution)
                logger.info(
                    f"Conflict {conflict.id[:8]} resolved: "
                    f"strategy={resolution.notes}, "
                    f"value={resolution.chosen_value}, "
                    f"confidence={resolution.confidence:.2f}"
                )
        
        logger.success(f"Resolved {len(resolutions)}/{len(conflicts)} conflicts automatically")
        return resolutions
    
    def _resolve_single_conflict(
        self,
        document: Document, 
        conflict: Conflict
    ) -> ConflictResolution:
        """Apply resolution strategies to a single conflict.
        
        Args:
            document: Document containing the conflict
            conflict: Conflict to resolve
            
        Returns:
            Generated resolution
        """
        # Get confidence scores
        ocr_conf = conflict.confidence_scores.get("text", 0.0)
        vision_conf = conflict.confidence_scores.get("vision", 0.0)
        
        # Get region type (if available)
        region_type = self._get_region_type(document, conflict.region_id)
        
        # Strategy A: Confidence Dominance
        if ocr_conf > self.high_confidence_threshold and vision_conf < self.low_confidence_threshold:
            return self._create_resolution(
                conflict=conflict,
                chosen_value=conflict.text_value,
                strategy=ResolutionStrategy.CONFIDENCE_DOMINANCE,
                confidence=ocr_conf,
                reason="High OCR confidence outweighs uncertain vision"
            )
        
        if vision_conf > self.high_confidence_threshold and ocr_conf < self.low_confidence_threshold:
            return self._create_resolution(
                conflict=conflict,
                chosen_value=conflict.vision_value,
                strategy=ResolutionStrategy.CONFIDENCE_DOMINANCE,
                confidence=vision_conf,
                reason="High Vision confidence outweighs uncertain OCR"
            )
        
        # Check for massive discrepancy FIRST (takes precedence)
        if conflict.discrepancy_percentage > self.massive_discrepancy_threshold:
            reason = f"Massive discrepancy ({conflict.discrepancy_percentage:.0%}) requires human review"
            return self._create_resolution(
                conflict=conflict,
                chosen_value=None,
                strategy=ResolutionStrategy.MANUAL_REVIEW_REQUIRED,
                confidence=0.0,
                reason=reason
            )
        
        # Strategy B: Region Bias (both have reasonable confidence)
        if (ocr_conf > self.reasonable_confidence and 
            vision_conf > self.reasonable_confidence):
            
            if region_type == RegionType.TABLE:
                return self._create_resolution(
                    conflict=conflict,
                    chosen_value=conflict.text_value,
                    strategy=ResolutionStrategy.REGION_BIAS_TABLE,
                    confidence=ocr_conf,
                    reason="TABLE region: OCR preferred for dense text"
                )
            
            if region_type == RegionType.CHART:
                return self._create_resolution(
                    conflict=conflict,
                    chosen_value=conflict.vision_value,
                    strategy=ResolutionStrategy.REGION_BIAS_CHART,
                    confidence=vision_conf,
                    reason="CHART region: Vision preferred for visual data"
                )
        
        # Strategy D: Default (Manual Review)
        # Triggered by: low confidence in both, or no clear winner
        if ocr_conf < self.reasonable_confidence and vision_conf < self.reasonable_confidence:
            reason = "Both confidence scores too low for auto-resolution"
        else:
            reason = "Ambiguous case - no clear resolution strategy applies"
        
        return self._create_resolution(
            conflict=conflict,
            chosen_value=None,  # No automatic choice
            strategy=ResolutionStrategy.MANUAL_REVIEW_REQUIRED,
            confidence=0.0,
            reason=reason
        )
    
    def _get_region_type(self, document: Document, region_id: str) -> RegionType | None:
        """Get the region type for a given region ID.
        
        Args:
            document: Document containing the region
            region_id: ID of the region
            
        Returns:
            RegionType or None if not found
        """
        for page in document.pages:
            for region in page.regions:
                if region.id == region_id:
                    return region.region_type
        return None
    
    def _create_resolution(
        self,
        conflict: Conflict,
        chosen_value: Any,
        strategy: str,
        confidence: float,
        reason: str
    ) -> ConflictResolution:
        """Create a ConflictResolution object.
        
        Args:
            conflict: Original conflict
            chosen_value: Resolved value (or None for manual review)
            strategy: Strategy used
            confidence: Confidence in the resolution
            reason: Human-readable reason
            
        Returns:
            ConflictResolution instance
        """
        # Determine resolution method
        if strategy == ResolutionStrategy.MANUAL_REVIEW_REQUIRED:
            method = ResolutionMethod.MANUAL
        else:
            method = ResolutionMethod.AUTO
        
        return ConflictResolution(
            conflict_id=conflict.id,
            chosen_value=chosen_value,
            resolution_method=method,
            confidence=confidence,
            notes=f"{strategy}: {reason}"
        )
