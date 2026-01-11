"""LangGraph workflow nodes for document processing pipeline.

This module provides async node functions that wrap processing agents
and integrate them into the LangGraph workflow state machine.
"""

from typing import Dict, Any
from loguru import logger

from local_body.agents.layout_agent import LayoutAgent
from local_body.agents.ocr_agent import OCRAgent
from local_body.agents.vision_agent import VisionAgent
from local_body.agents.validation_agent import ValidationAgent
from local_body.orchestration.state import DocumentProcessingState, ProcessingStage
from local_body.core.config_manager import ConfigManager


# Agent singleton cache
_agents: Dict[str, Any] = {}


def _get_agent(agent_type: str, config: Dict[str, Any]):
    """Get or create agent instance (singleton pattern).
    
    Args:
        agent_type: Type of agent ('layout', 'ocr', 'vision', 'validation')
        config: Configuration dict
        
    Returns:
        Agent instance
    """
    if agent_type not in _agents:
        if agent_type == "layout":
            _agents[agent_type] = LayoutAgent(config)
        elif agent_type == "ocr":
            _agents[agent_type] = OCRAgent(config)
        elif agent_type == "vision":
            from local_body.tunnel.secure_tunnel import SecureTunnel
            from local_body.core.config_manager import SystemConfig
            sys_config = SystemConfig()
            tunnel = SecureTunnel(config=sys_config)
            _agents[agent_type] = VisionAgent(config, tunnel)
        elif agent_type == "validation":
            _agents[agent_type] = ValidationAgent(config)
        else:
            raise ValueError(f"Unknown agent type: {agent_type}")
    
    return _agents[agent_type]


# ==================== ASYNC WORKFLOW NODES ====================

async def layout_node(state: DocumentProcessingState) -> Dict[str, Any]:
    """Process document with layout detection (YOLOv8).
    
    Detects regions (text, tables, images, charts) in document pages.
    
    Args:
        state: Current processing state
        
    Returns:
        Partial state update with detected regions
    """
    logger.info(f"Layout node processing document {state['document'].id}")
    
    try:
        # Load config
        config_manager = ConfigManager()
        config = config_manager.load_config()
        
        # Get agent
        agent = _get_agent("layout", config.model_dump())
        
        # FIXED: Direct await instead of asyncio.run()
        document = await agent.process(state['document'])
        
        # Extract all regions from all pages
        all_regions = []
        for page in document.pages:
            all_regions.extend(page.regions)
        
        logger.success(f"Layout detection complete: {len(all_regions)} regions detected")
        
        return {
            'document': document,
            'layout_regions': all_regions,
            'processing_stage': ProcessingStage.LAYOUT
        }
        
    except Exception as e:
        logger.error(f"Layout node failed: {e}", exc_info=True)
        error_msg = f"Layout failed: {str(e)}"
        return {
            'processing_stage': ProcessingStage.FAILED,
            'error_log': [error_msg]
        }


async def ocr_node(state: DocumentProcessingState) -> Dict[str, Any]:
    """Extract text via OCR (PaddleOCR).
    
    Args:
        state: Current processing state
        
    Returns:
        Partial state update with OCR results
    """
    logger.info(f"OCR node processing document {state['document'].id}")
    
    try:
        # Load config
        config_manager = ConfigManager()
        config = config_manager.load_config()
        
        # Get agent
        agent = _get_agent("ocr", config.model_dump())
        
        # FIXED: Direct await instead of asyncio.run()
        document = await agent.process(state['document'])
        
        # Extract OCR results from regions
        ocr_results = {}
        for page_idx, page in enumerate(document.pages):
            for region_idx, region in enumerate(page.regions):
                if hasattr(region.content, 'text') and region.content.text:
                    key = f"page_{page_idx}_region_{region_idx}"
                    ocr_results[key] = region.content.text
        
        logger.success(f"OCR complete: extracted text from {len(ocr_results)} regions")
        
        return {
            'document': document,
            'ocr_results': ocr_results
        }
        
    except Exception as e:
        logger.error(f"OCR node failed: {e}", exc_info=True)
        return {
            'ocr_results': {},
            'error_log': [f"OCR failed: {str(e)}"]
        }


async def vision_node(state: DocumentProcessingState) -> Dict[str, Any]:
    """Analyze images with vision model.
    
    Args:
        state: Current processing state
        
    Returns:
        Partial state update with vision results
    """
    logger.info(f"Vision node processing document {state['document'].id}")
    
    try:
        # Load config
        config_manager = ConfigManager()
        config = config_manager.load_config()
        
        # Get agent
        agent = _get_agent("vision", config.model_dump())
        
        # FIXED: Direct await instead of asyncio.run()
        document = await agent.process(state['document'])
        
        # Extract vision results from page metadata
        vision_results = {}
        for idx, page in enumerate(document.pages):
            if page.metadata and 'vision_summary' in page.metadata:
                vision_results[f"page_{idx}"] = page.metadata['vision_summary']
        
        logger.success(f"Vision analysis complete: analyzed {len(vision_results)} pages")
        
        return {
            'document': document,
            'vision_results': vision_results
        }
        
    except Exception as e:
        logger.error(f"Vision node failed: {e}", exc_info=True)
        return {
            'vision_results': {},
            'error_log': [f"Vision failed: {str(e)}"]
        }


def validation_node(state: DocumentProcessingState) -> Dict[str, Any]:
    """Validate OCR vs Vision results and detect conflicts.
    
    Validation is CPU-bound with no I/O, so remains synchronous.
    
    Args:
        state: Current processing state
        
    Returns:
        Partial state update with conflicts
    """
    logger.info(f"Validation node processing document {state['document'].id}")
    
    try:
        # Load config
        config_manager = ConfigManager()
        config = config_manager.load_config()
        
        # Get agent
        agent = _get_agent("validation", config.model_dump())
        
        # Get vision results (may be empty if vision failed)
        vision_results = state.get('vision_results', {})
        
        if not vision_results:
            logger.warning("No vision results available for validation, skipping conflict detection")
            return {
                'conflicts': [],
                'processing_stage': ProcessingStage.COMPLETE
            }
        
        # Validate and detect conflicts
        conflicts = agent.validate(state['document'], vision_results)
        
        # Determine processing stage based on conflicts
        if not conflicts:
            stage = ProcessingStage.COMPLETE
            logger.success("Validation complete: No conflicts detected")
        else:
            stage = ProcessingStage.CONFLICT
            logger.warning(f"Validation complete: {len(conflicts)} conflicts detected")
        
        return {
            'conflicts': conflicts,
            'processing_stage': stage
        }
        
    except Exception as e:
        logger.error(f"Validation node failed: {e}", exc_info=True)
        # Return empty conflicts to allow workflow to continue
        return {
            'conflicts': [],
            'processing_stage': ProcessingStage.COMPLETE,
            'error_log': [f"Validation failed: {str(e)}"]
        }


def auto_resolution_node(state: DocumentProcessingState) -> Dict[str, Any]:
    """Automatically resolve low-impact conflicts.
    
    Args:
        state: Current processing state
        
    Returns:
        Partial state update with resolutions
    """
    logger.info("Auto-resolution node processing conflicts")
    
    conflicts = state.get('conflicts', [])
    
    # Simple auto-resolution: accept OCR for low-impact conflicts
    resolutions = []
    for conflict in conflicts:
        if hasattr(conflict, 'impact_score') and conflict.impact_score < 0.5:
            resolution = {
                'conflict_id': conflict.id if hasattr(conflict, 'id') else str(conflict),
                'resolved_value': conflict.ocr_value if hasattr(conflict, 'ocr_value') else None,
                'resolution_method': 'auto_ocr_preference'
            }
            resolutions.append(resolution)
    
    logger.info(f"Auto-resolved {len(resolutions)}/{len(conflicts)} conflicts")
    
    return {
        'resolutions': resolutions,
        'processing_stage': ProcessingStage.COMPLETE
    }


def human_review_node(state: DocumentProcessingState) -> Dict[str, Any]:
    """Pause workflow for human review of high-impact conflicts.
    
    This is a placeholder that marks the state as awaiting human input.
    The actual UI interaction happens outside the workflow.
    
    Args:
        state: Current processing state
        
    Returns:
        Partial state update indicating human review needed
    """
    logger.info("Human review node - workflow paused for manual resolution")
    
    conflicts = state.get('conflicts', [])
    high_impact = [c for c in conflicts if hasattr(c, 'impact_score') and c.impact_score >= 0.5]
    
    logger.warning(f"Awaiting human review for {len(high_impact)} high-impact conflicts")
    
    return {
        'processing_stage': ProcessingStage.HUMAN_REVIEW,
        'error_log': [f"Workflow paused: {len(high_impact)} conflicts require manual review"]
    }
