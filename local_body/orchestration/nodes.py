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
from local_body.agents.resolution_agent import ResolutionAgent
from local_body.orchestration.state import DocumentProcessingState, ProcessingStage
from local_body.core.config_manager import ConfigManager


# Agent singleton cache
_agents: Dict[str, Any] = {}


def _get_agent(agent_type: str, config: Dict[str, Any]):
    """Get or create agent instance (singleton pattern).
    
    Args:
        agent_type: Type of agent ('layout', 'ocr', 'vision', 'validation', 'resolution')
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
            
            # FIX: Start the tunnel if not already active
            if not tunnel.public_url:
                logger.info("Starting Secure Tunnel for Vision Agent...")
                tunnel.start()
                logger.success(f"Tunnel started: {tunnel.public_url}")
            else:
                logger.info(f"Using existing tunnel: {tunnel.public_url}")
            
            _agents[agent_type] = VisionAgent(config, tunnel)
        elif agent_type == "validation":
            _agents[agent_type] = ValidationAgent(config)
        elif agent_type == "resolution":
            _agents[agent_type] = ResolutionAgent(config)
        else:
            raise ValueError(f"Unknown agent type: {agent_type}")
    
    return _agents[agent_type]


# ==================== ASYNC WORKFLOW NODES ====================

async def layout_node(state: DocumentProcessingState) -> Dict[str, Any]:
    """Process document with layout detection (YOLOv8).
    
    Detects regions (text, tables, images, charts) in document pages.
    IDEMPOTENT: Skips if layout regions already exist.
    
    Args:
        state: Current processing state
        
    Returns:
        Partial state update with detected regions
    """
    # IDEMPOTENCY CHECK: Skip if already processed
    if state.get('layout_regions') and len(state['layout_regions']) > 0:
        logger.info(f"Skipping layout detection: Already complete ({len(state['layout_regions'])} regions exist)")
        return {
            'document': state['document'],
            'layout_regions': state['layout_regions'],
            'processing_stage': ProcessingStage.LAYOUT
        }
    
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
    """Process document with OCR (PaddleOCR).
    
    Extracts text from detected regions with retry logic.
    IDEMPOTENT: Skips if OCR results already exist.
    
    Args:
        state: Current processing state
        
    Returns:
        Partial state update with OCR results
    """
    # IDEMPOTENCY CHECK: Skip if already processed
    if state.get('ocr_results') and state['ocr_results'].get('regions_processed', 0) > 0:
        logger.info(f"Skipping OCR: Already complete ({state['ocr_results'].get('regions_processed')} regions processed)")
        return {
            'document': state['document'],
            'ocr_results': state['ocr_results'],
            'processing_stage': ProcessingStage.OCR
        }
    
    logger.info(f"OCR node processing document {state['document'].id}")
    
    try:
        # Load config
        config_manager = ConfigManager()
        config = config_manager.load_config()
        
        # Get agent
        agent = _get_agent("ocr", config.model_dump())
        
        # Process
        document = await agent.process(state['document'])
        
        # Collect OCR results summary
        ocr_results = {
            'regions_processed': sum(len(page.regions) for page in document.pages),
            'extraction_method': 'paddleocr'
        }
        
        logger.success(f"OCR complete: {ocr_results['regions_processed']} regions processed")
        
        return {
            'document': document,
            'ocr_results': ocr_results,
            'processing_stage': ProcessingStage.OCR
        }
        
    except Exception as e:
        logger.error(f"OCR node failed: {e}", exc_info=True)
        return {
            'ocr_results': {},
            'error_log': [f"OCR failed: {str(e)}"]
        }


async def vision_node(state: DocumentProcessingState) -> Dict[str, Any]:
    """Process document with vision model (Qwen-VL).
    
    Extracts semantic understanding from regions.
    IDEMPOTENT: Skips if vision results already exist.
    
    Args:
        state: Current processing state
        
    Returns:
        Partial state update with vision results
    """
    # IDEMPOTENCY CHECK: Skip if already processed
    if state.get('vision_results') and state['vision_results'].get('regions_analyzed', 0) > 0:
        logger.info(f"Skipping vision analysis: Already complete ({state['vision_results'].get('regions_analyzed')} regions analyzed)")
        return {
            'document': state['document'],
            'vision_results': state['vision_results'],
            'processing_stage': ProcessingStage.VISION
        }
    
    logger.info(f"Vision node processing document {state['document'].id}")
    
    try:
        # Load config
        config_manager = ConfigManager()
        config = config_manager.load_config()
        
        # Get agent
        agent = _get_agent("vision", config.model_dump())
        
        # Process
        document = await agent.process(state['document'])
        
        # Collect vision results summary
        vision_results = {
            'regions_analyzed': sum(len(page.regions) for page in document.pages),
            'model': 'qwen-vl'
        }
        
        logger.success(f"Vision analysis complete: {vision_results['regions_analyzed']} regions analyzed")
        
        return {
            'document': document,
            'vision_results': vision_results,
            'processing_stage': ProcessingStage.VISION
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


async def auto_resolution_node(state: DocumentProcessingState) -> Dict[str, Any]:
    """Automatically resolve conflicts using ResolutionAgent.
    
    Applies contextual resolution strategies (Confidence Dominance, Region Bias)
    to auto-resolve conflicts when possible, reducing manual review workload.
    
    Args:
        state: Current processing state with detected conflicts
        
    Returns:
        Partial state update with resolutions and updated conflict statuses
    """
    try:
        conflicts = state.get('conflicts', [])
        
        if not conflicts:
            logger.info("No conflicts to auto-resolve")
            return {
                'processing_stage': ProcessingStage.COMPLETE,
                'resolutions': []
            }
        
        logger.info(f"Auto-resolution node started with {len(conflicts)} conflicts")
        
        # Get config and initialize ResolutionAgent
        config_manager = ConfigManager()
        config = config_manager.load_config()
        agent = _get_agent('resolution', config.model_dump())
        
        # Run resolution logic
        document = state['document']
        resolutions = agent.resolve(document, conflicts)
        
        # Update conflict statuses based on resolutions
        from local_body.core.datamodels import ResolutionStatus, ResolutionMethod
        updated_conflicts = []
        
        for conflict in conflicts:
            # Find corresponding resolution
            resolution = next(
                (r for r in resolutions if r.conflict_id == conflict.id),
                None
            )
            
            if resolution and resolution.resolution_method == ResolutionMethod.AUTO:
                # Auto-resolved - update conflict status
                conflict.resolution_status = ResolutionStatus.RESOLVED
                conflict.resolution_method = ResolutionMethod.AUTO
            
            updated_conflicts.append(conflict)
        
        # Count auto vs manual
        auto_count = sum(1 for r in resolutions if r.resolution_method == ResolutionMethod.AUTO)
        manual_count = sum(1 for r in resolutions if r.resolution_method == ResolutionMethod.MANUAL)
        
        logger.success(
            f"Auto-resolution complete: {auto_count} auto-resolved, "
            f"{manual_count} require manual review"
        )
        
        return {
            'conflicts': updated_conflicts,
            'resolutions': resolutions,
            'processing_stage': ProcessingStage.AUTO_RESOLVED
        }
        
    except Exception as e:
        logger.error(f"Auto-resolution failed: {e}")
        return {
            'processing_stage': ProcessingStage.FAILED,
            'error_log': [f"Auto-resolution error: {str(e)}"]
        }
