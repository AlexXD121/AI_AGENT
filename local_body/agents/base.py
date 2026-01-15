"""Base agent interface for document processing agents.

This module defines the abstract base class that all specialized agents
(OCR, Vision, Layout, Validation, Resolution) must implement.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from local_body.core.datamodels import Document


class BaseAgent(ABC):
    """Abstract base class for all document processing agents.
    
    All specialized agents (OCRAgent, VisionAgent, LayoutAgent, etc.) must
    inherit from this class and implement the required abstract methods.
    """
    
    def __init__(self, agent_type: str, config: Dict[str, Any]):
        """Initialize the base agent.
        
        Args:
            agent_type: Type of agent (ocr, vision, layout, validator, resolver)
            config: Configuration dictionary for the agent
        """
        self.agent_type = agent_type
        self.config = config
        self._confidence: float = 0.0
    
    @abstractmethod
    async def process(self, document: Document) -> Any:
        """Process a document and return results.
        
        This is the main processing method that each agent must implement.
        The return type varies based on the agent type:
        - OCRAgent: Returns TextContent or TableContent
        - VisionAgent: Returns ImageContent
        - LayoutAgent: Returns List[Region]
        - ValidationAgent: Returns List[Conflict]
        - ResolutionAgent: Returns List[ConflictResolution]
        
        Args:
            document: The document to process
            
        Returns:
            Processing results specific to the agent type
            
        Raises:
            NotImplementedError: If the agent hasn't implemented this method
        """
        raise NotImplementedError("Agents must implement the process method")
    
    def confidence_score(self) -> float:
        """Get the confidence score of the last processing operation.
        
        Returns:
            Confidence score between 0.0 and 1.0
        """
        return self._confidence
    
    def set_confidence(self, score: float) -> None:
        """Set the confidence score for the current operation.
        
        Args:
            score: Confidence score between 0.0 and 1.0
            
        Raises:
            ValueError: If score is not in valid range
        """
        if not 0.0 <= score <= 1.0:
            raise ValueError(f"Confidence score must be between 0.0 and 1.0, got {score}")
        self._confidence = score
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """Get a configuration value.
        
        Handles both dict configs and Pydantic SystemConfig objects.
        
        Args:
            key: Configuration key to retrieve
            default: Default value if key doesn't exist
            
        Returns:
            Configuration value or default
        """
        # Handle Pydantic models (SystemConfig)
        if hasattr(self.config, 'model_dump'):
            config_dict = self.config.model_dump()
            return config_dict.get(key, default)
        # Handle regular dicts
        elif hasattr(self.config, 'get'):
            return self.config.get(key, default)
        # Handle objects with attributes
        else:
            return getattr(self.config, key, default)
    
    def update_config(self, updates: Dict[str, Any]) -> None:
        """Update agent configuration.
        
        Args:
            updates: Dictionary of configuration updates
        """
        self.config.update(updates)
    
    def __repr__(self) -> str:
        """String representation of the agent."""
        return f"{self.__class__.__name__}(type={self.agent_type}, confidence={self._confidence:.2f})"
