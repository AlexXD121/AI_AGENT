"""LangGraph workflow nodes for document processing pipeline.

This module provides node functions that wrap processing agents
and integrate them into the LangGraph workflow state machine.
"""

import asyncio
from typing import Dict, Any
from loguru import logger

from local_body.agents.layout_agent import LayoutAgent
from local_body.agents.ocr_agent import OCRAgent
from local_body.agents.vision_agent import VisionAgent
from local_body.agents.validation_agent import ValidationAgent
from local_body.orchestration.state import DocumentProcessingState, ProcessingStage
from local_body.core.config_manager import ConfigManager


# Global agent instances (singleton pattern for efficiency)
_agents: Dict[str, Any] = {}


def _get_agent(agent_type: str, config: Dict[str, Any]):
    """Get or create agent instance (singleton pattern)."""
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
    
    return _agents[agent_type]


def layout_node(state: DocumentProcessingState) -> Dict[str, Any]:
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
        
        # Process document (modifies document.pages[].regions in place)
        document = asyncio.run(agent.process(state['document']))
        
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
        logger.error(f"Layout node failed: {e}")
        return {
            'processing_stage': ProcessingStage.FAILED,
            'error_log': state.get('error_log', []) + [f"Layout failed: {str(e)}"]
        }


def ocr_node(state: DocumentProcessingState) -> Dict[str, Any]:
    """Process document with OCR text extraction (PaddleOCR).
    
    Extracts text from detected regions.
    
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
        
        # Process document (modifies region.content in place)
        document = asyncio.run(agent.process(state['document']))
        
        # Extract OCR results
        ocr_results = {}
        for page_idx, page in enumerate(document.pages):
            for region_idx, region in enumerate(page.regions):
                if hasattr(region.content, 'text'):
                    key = f"page_{page_idx}_region_{region_idx}"
                    ocr_results[key] = region.content.text
        
        logger.success(f"OCR extraction complete: {len(ocr_results)} text regions")
        
        return {
            'document': document,
            'ocr_results': ocr_results
        }
        
    except Exception as e:
        logger.error(f"OCR node failed: {e}")
        return {
            'processing_stage': ProcessingStage.FAILED,
            'error_log': state.get('error_log', []) + [f"OCR failed: {str(e)}"]
        }


def vision_node(state: DocumentProcessingState) -> Dict[str, Any]:
    """Process document with vision analysis (remote Cloud Brain).
    
    Analyzes images and charts using vision model.
    
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
        
        # Process document (adds vision_summary to page metadata)
        document = asyncio.run(agent.process(state['document']))
        
        # Extract vision results
        vision_results = {}
        for page_idx, page in enumerate(document.pages):
            if page.metadata and 'vision_summary' in page.metadata:
                vision_results[f"page_{page_idx}"] = page.metadata['vision_summary']
        
        logger.success(f"Vision analysis complete: {len(vision_results)} analyses")
        
        return {
            'document': document,
            'vision_results': vision_results
        }
        
    except Exception as e:
        logger.error(f"Vision node failed: {e}")
        return {
            'processing_stage': ProcessingStage.FAILED,
            'error_log': state.get('error_log', []) + [f"Vision failed: {str(e)}"]
        }


def validation_node(state: DocumentProcessingState) -> Dict[str, Any]:
    """Validate document for conflicts between OCR and vision.
    
    Detects discrepancies in numeric values.
    
    Args:
        state: Current processing state
        
    Returns:
        Partial state update with detected conflicts
    """
    logger.info(f"Validation node processing document {state['document'].id}")
    
    try:
        # Load config
        config_manager = ConfigManager()
        config = config_manager.load_config()
        
        # Get agent
        agent = _get_agent("validation", config.model_dump())
        
        # Validate document
        conflicts = agent.validate(
            state['document'],
            state.get('vision_results', {})
        )
        
        logger.success(f"Validation complete: {len(conflicts)} conflicts detected")
        
        # Update processing stage based on conflicts
        if conflicts:
            stage = ProcessingStage.CONFLICT
        else:
            stage = ProcessingStage.COMPLETE
        
        return {
            'conflicts': conflicts,
            'processing_stage': stage
        }
        
    except Exception as e:
        logger.error(f"Validation node failed: {e}")
        return {
            'processing_stage': ProcessingStage.FAILED,
            'error_log': state.get('error_log', []) + [f"Validation failed: {str(e)}"]
        }
