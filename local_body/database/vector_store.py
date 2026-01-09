"""Vector storage and retrieval system using Qdrant.

This module implements the DocumentVectorStore class for storing document
embeddings and performing semantic search using Qdrant vector database.
"""

from typing import List, Optional, Dict, Any
from uuid import uuid5, NAMESPACE_DNS

from fastembed import TextEmbedding
from loguru import logger
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from qdrant_client.http.exceptions import UnexpectedResponse

from local_body.core.config_manager import SystemConfig
from local_body.core.datamodels import Document, Page, Region, TextContent


class DocumentVectorStore:
    """Vector store for document embeddings using Qdrant and FastEmbed.
    
    This class handles:
    - Initialization of Qdrant client and embedding model
    - Collection management with proper vector configuration
    - Document storage with page-level embeddings
    - Semantic search functionality
    - Health checks and connection management
    """
    
    def __init__(self, config: SystemConfig):
        """Initialize the vector store with configuration.
        
        Args:
            config: SystemConfig instance with Qdrant and embedding settings
        """
        self.config = config
        
        # Initialize Qdrant client
        logger.info(
            f"Initializing Qdrant client: {config.qdrant_host}:{config.qdrant_port}"
        )
        self.client = QdrantClient(
            host=config.qdrant_host,
            port=config.qdrant_port,
            timeout=30.0
        )
        
        # Initialize embedding model (BGE-small-en-v1.5)
        # This model produces 384-dimensional embeddings
        logger.info(f"Loading embedding model: {config.embedding_model}")
        try:
            # Suppress fastembed download progress for cleaner logs
            self.embedding_model = TextEmbedding(
                model_name="BAAI/bge-small-en-v1.5"
            )
            logger.success("Embedding model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            raise
        
        # Ensure collection exists
        self.collection_name = config.vector_collection
        self.ensure_collection_exists()
    
    def ensure_collection_exists(self) -> None:
        """Ensure the document collection exists with proper configuration.
        
        Creates the collection if it doesn't exist with:
        - Vector size: 384 (BGE-small-en-v1.5 embedding dimension)
        - Distance metric: COSINE (best for semantic similarity)
        """
        try:
            # Check if collection exists
            collections = self.client.get_collections()
            collection_names = [col.name for col in collections.collections]
            
            if self.collection_name in collection_names:
                logger.info(f"Collection '{self.collection_name}' already exists")
                return
            
            # Create collection with proper vector configuration
            logger.info(f"Creating collection '{self.collection_name}'")
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=384,  # BGE-small-en-v1.5 embedding dimension
                    distance=Distance.COSINE
                )
            )
            logger.success(f"Collection '{self.collection_name}' created successfully")
            
        except Exception as e:
            logger.error(f"Failed to ensure collection exists: {e}")
            raise
    
    def check_health(self) -> bool:
        """Check if Qdrant connection is healthy.
        
        Returns:
            True if connection is healthy, False otherwise
        """
        try:
            # Try to get collection info as a health check
            self.client.get_collection(collection_name=self.collection_name)
            logger.debug("Qdrant health check passed")
            return True
            
        except UnexpectedResponse as e:
            logger.error(f"Qdrant health check failed (UnexpectedResponse): {e}")
            return False
        except ConnectionError as e:
            logger.error(f"Qdrant health check failed (ConnectionError): {e}")
            return False
        except Exception as e:
            logger.error(f"Qdrant health check failed: {e}")
            return False
    
    def store_document(self, document: Document) -> None:
        """Store document embeddings in Qdrant.
        
        For each page in the document:
        1. Extract text from all text regions
        2. Generate embedding vector for the page text
        3. Store as a point with metadata
        
        Args:
            document: Document instance to store
        """
        logger.info(f"Storing document {document.id} with {len(document.pages)} pages")
        
        points: List[PointStruct] = []
        
        for page in document.pages:
            # Extract text from all text regions on the page
            page_text = self._extract_page_text(page)
            
            if not page_text.strip():
                logger.warning(
                    f"Page {page.page_number} has no text content, skipping"
                )
                continue
            
            # Generate embedding for the page text
            try:
                # FastEmbed returns a generator, convert to list
                embeddings = list(self.embedding_model.embed([page_text]))
                if not embeddings:
                    logger.warning(
                        f"Failed to generate embedding for page {page.page_number}"
                    )
                    continue
                
                embedding_vector = embeddings[0].tolist()
                
            except Exception as e:
                logger.error(
                    f"Error generating embedding for page {page.page_number}: {e}"
                )
                continue
            
            # Create deterministic UUID based on doc_id + page_num
            point_id = str(uuid5(NAMESPACE_DNS, f"{document.id}:{page.page_number}"))
            
            # Create point with metadata
            point = PointStruct(
                id=point_id,
                vector=embedding_vector,
                payload={
                    "doc_id": document.id,
                    "page_num": page.page_number,
                    "metadata": document.metadata.model_dump(),
                    "text_preview": page_text[:200]  # Store preview for debugging
                }
            )
            
            points.append(point)
        
        # Upload all points to Qdrant
        if points:
            try:
                self.client.upsert(
                    collection_name=self.collection_name,
                    points=points
                )
                logger.success(
                    f"Stored {len(points)} page embeddings for document {document.id}"
                )
            except Exception as e:
                logger.error(f"Failed to upsert points to Qdrant: {e}")
                raise
        else:
            logger.warning(f"No valid pages to store for document {document.id}")
    
    def semantic_search(
        self, 
        query_text: str, 
        limit: int = 10,
        score_threshold: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """Perform semantic search on stored documents.
        
        Args:
            query_text: Text query to search for
            limit: Maximum number of results to return
            score_threshold: Optional minimum similarity score (0-1)
        
        Returns:
            List of search results with metadata and scores
        """
        logger.info(f"Performing semantic search: '{query_text[:50]}...'")
        
        try:
            # Generate embedding for query
            query_embeddings = list(self.embedding_model.embed([query_text]))
            if not query_embeddings:
                logger.error("Failed to generate query embedding")
                return []
            
            query_vector = query_embeddings[0].tolist()
            
            # Perform search
            search_results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                limit=limit,
                score_threshold=score_threshold
            )
            
            # Format results
            results = []
            for hit in search_results:
                results.append({
                    "doc_id": hit.payload.get("doc_id"),
                    "page_num": hit.payload.get("page_num"),
                    "score": hit.score,
                    "metadata": hit.payload.get("metadata"),
                    "text_preview": hit.payload.get("text_preview")
                })
            
            logger.info(f"Found {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            raise
    
    def _extract_page_text(self, page: Page) -> str:
        """Extract all text content from a page.
        
        Args:
            page: Page instance to extract text from
        
        Returns:
            Concatenated text from all text regions
        """
        text_parts = []
        
        for region in page.regions:
            # Only extract from text content regions
            if isinstance(region.content, TextContent):
                text_parts.append(region.content.text)
        
        return " ".join(text_parts)
