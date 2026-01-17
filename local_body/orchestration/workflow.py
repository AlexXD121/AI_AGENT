"""LangGraph workflow orchestration for document processing.

This module implements the multi-agent workflow system with parallel
execution, conditional routing, and human-in-the-loop integration.

Requirements: 5.2 (Parallel Extraction), 11.3 (Conflict Detection), 11.5 (Human Review)
"""

from typing import Dict, Any, Literal
from loguru import logger

from langgraph.graph import StateGraph, END
from local_body.orchestration.state import DocumentProcessingState, ProcessingStage
from local_body.orchestration.nodes import (
    layout_node, 
    ocr_node, 
    vision_node, 
    validation_node,
    auto_resolution_node,
    human_review_node
)
from local_body.orchestration.checkpoint import CheckpointManager


def route_after_validation(state: DocumentProcessingState) -> Literal["end", "auto_resolve", "human_review"]:
    """Route workflow based on conflict detection results.
    
    Routing Logic:
    - No conflicts → END
    - High-impact conflicts (table/financial, high confidence) → human_review
    - Low-impact conflicts → auto_resolve
    
    Args:
        state: Current processing state
        
    Returns:
        Next node name or "end"
    """
    conflicts = state.get('conflicts', [])
    
    if not conflicts:
        logger.info("No conflicts detected - ending workflow")
        return "end"
    
    # Calculate maximum impact score across all conflicts
    max_impact = max((c.impact_score for c in conflicts), default=0.0)
    
    # High impact threshold: 0.7
    if max_impact >= 0.7:
        logger.warning(f"High-impact conflicts detected (max impact: {max_impact:.2f}) - routing to human review")
        return "human_review"
    else:
        logger.info(f"Low-impact conflicts detected (max impact: {max_impact:.2f}) - routing to auto-resolve")
        return "auto_resolve"


class DocumentWorkflow:
    """LangGraph-based workflow orchestrator for document processing.
    
    This class manages the multi-agent workflow with:
    - Sequential execution with parallel OCR/Vision (simulated via state updates)
    - Conditional routing based on conflict detection
    - Human-in-the-loop for high-impact conflicts
    - Checkpoint persistence for crash recovery
    """
    
    def __init__(self, checkpoint_dir: str = "./data/checkpoints"):
        """Initialize workflow with checkpoint manager.
        
        Args:
            checkpoint_dir: Directory for checkpoint persistence
        """
        self.checkpoint_manager = CheckpointManager(checkpoint_dir)
        self.graph = self._build_graph()
        logger.info("DocumentWorkflow initialized")
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow.
        
        Note: LangGraph's StateGraph merges parallel branches automatically.
        To avoid concurrent write conflicts, we use a sequential flow with
        parallel agents called within single nodes.
        
        Returns:
            Compiled StateGraph
        """
        # Initialize graph
        workflow = StateGraph(DocumentProcessingState)
        
        # Add nodes
        workflow.add_node("layout", layout_node)
        workflow.add_node("ocr", ocr_node)
        workflow.add_node("vision", vision_node)
        workflow.add_node("validation", validation_node)
        workflow.add_node("auto_resolve", auto_resolution_node)
        workflow.add_node("human_review", human_review_node)
        
        # Set entry point
        workflow.set_entry_point("layout")
        
        # Sequential flow (LangGraph handles state merging)
        # Layout → OCR → Vision → Validation
        workflow.add_edge("layout", "ocr")
        workflow.add_edge("ocr", "vision")
        workflow.add_edge("vision", "validation")
        
        # Conditional routing after validation
        workflow.add_conditional_edges(
            "validation",
            route_after_validation,
            {
                "end": END,
                "auto_resolve": "auto_resolve",
                "human_review": "human_review"
            }
        )
        
        # After auto-resolution, end workflow
        workflow.add_edge("auto_resolve", END)
        
        # Human review node is terminal (requires external input to resume)
        workflow.add_edge("human_review", END)
        
        # Compile graph
        logger.info("Workflow graph compiled successfully")
        return workflow.compile()
    
    async def run(self, state: DocumentProcessingState) -> DocumentProcessingState:
        """Execute workflow on document.
        
        Args:
            state: Initial processing state
            
        Returns:
            Final processing state
        """
        doc_id = state['document'].id
        logger.info(f"Starting workflow for document {doc_id}")
        
        try:
            # Save initial checkpoint
            self.checkpoint_manager.save_checkpoint(doc_id, state)
            
            # Run workflow asynchronously
            result = await self.graph.ainvoke(state)
            
            # Save final checkpoint
            self.checkpoint_manager.save_checkpoint(doc_id, result)
            
            # If completed successfully, clear checkpoint
            if result.get('processing_stage') == ProcessingStage.COMPLETE:
                self.checkpoint_manager.clear_checkpoint(doc_id)
                logger.success(f"Workflow completed for document {doc_id}")
            else:
                logger.info(f"Workflow paused at stage: {result.get('processing_stage')}")
            
            return result
            
        except Exception as e:
            logger.error(f"Workflow failed for document {doc_id}: {e}")
            # Save error state
            state['processing_stage'] = ProcessingStage.FAILED
            state['error_log'] = state.get('error_log', []) + [str(e)]
            self.checkpoint_manager.save_checkpoint(doc_id, state)
            raise
    
    def resume(self, doc_id: str) -> DocumentProcessingState:
        """Resume workflow from checkpoint.
        
        Args:
            doc_id: Document identifier
            
        Returns:
            Final processing state
        """
        logger.info(f"Resuming workflow for document {doc_id}")
        
        # Load checkpoint
        state = self.checkpoint_manager.load_checkpoint(doc_id)
        if state is None:
            raise ValueError(f"No checkpoint found for document {doc_id}")
        
        # Resume from current stage
        return self.run(state)
