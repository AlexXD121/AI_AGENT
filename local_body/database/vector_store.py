"""Vector storage and retrieval system using Qdrant.

This module implements the DocumentVectorStore class for storing document
embeddings and performing semantic search using Qdrant vector database.
"""

from typing import List, Optional, Dict, Any
from uuid import uuid5, NAMESPACE_DNS

from fastembed import TextEmbedding
from loguru import logger
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from qdrant_client.http.exceptions import UnexpectedResponse

from local_body.core.config_manager import SystemConfig
from local_body.core.datamodels import Document, Page, Region, TextContent


class DocumentVectorStore:
    """Vector store for document embeddings using Qdrant and FastEmbed.
    
    This class handles:
    - Initialization of async Qdrant client and embedding model
    - Collection management with proper vector configuration
    - Document storage with page-level batch embeddings
    - Semantic search functionality
    - Health checks and connection management
    """
    
    def __init__(self, config: SystemConfig):
        """Initialize the vector store with configuration.
        
        Args:
            config: SystemConfig instance with Qdrant and embedding settings
        """
        self.config = config
        
        # Initialize async Qdrant client
        logger.info(
            f"Initializing async Qdrant client: {config.qdrant_host}:{config.qdrant_port}"
        )
        self.client = AsyncQdrantClient(
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
                model_name=config.embedding_model
            )
            logger.success("Embedding model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            raise
        
        # Collection name
        self.collection_name = config.vector_collection
    
    async def ensure_collection_exists(self) -> None:
        """Ensure the document collection exists with proper configuration.
        
        Creates the collection if it doesn't exist with:
        - Vector size: 384 (BGE-small-en-v1.5 embedding dimension)
        - Distance metric: COSINE (best for semantic similarity)
        """
        try:
            # Check if collection exists
            collections = await self.client.get_collections()
            collection_names = [col.name for col in collections.collections]
            
            if self.collection_name in collection_names:
                logger.info(f"Collection '{self.collection_name}' already exists")
                return
            
            # Create collection with proper vector configuration
            logger.info(f"Creating collection '{self.collection_name}'")
            await self.client.create_collection(
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
    
    async def check_health(self) -> bool:
        """Check if Qdrant connection is healthy.
        
        Returns:
            True if connection is healthy, False otherwise
        """
        try:
            # Try to get collection info as a health check
            await self.client.get_collection(collection_name=self.collection_name)
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
    
    async def store_document(self, document: Document) -> None:
        """Store document embeddings in Qdrant using batch processing.
        
        For each page in the document:
        1. Extract text from all text regions
        2. Generate embeddings for all pages in a single batch
        3. Store as points with metadata
        
        Args:
            document: Document instance to store
        """
        logger.info(f"Storing document {document.id} with {len(document.pages)} pages")
        
        # Step 1: Collect all valid page texts
        valid_pages: List[Page] = []
        texts: List[str] = []
        
        for page in document.pages:
            # Extract text from all text regions on the page
            page_text = self._extract_page_text(page)
            
            if not page_text.strip():
                logger.warning(
                    f"Page {page.page_number} has no text content, skipping"
                )
                continue
            
            valid_pages.append(page)
            texts.append(page_text)
        
        if not texts:
            logger.warning(f"No valid pages to store for document {document.id}")
            return
        
        # Step 2: Generate all embeddings in one batch (major optimization)
        logger.debug(f"Generating embeddings for {len(texts)} pages in batch")
        try:
            # FastEmbed returns a generator, convert to list
            # This is the key optimization: one call instead of N calls
            embeddings = list(self.embedding_model.embed(texts))
            
            if len(embeddings) != len(valid_pages):
                logger.error(
                    f"Embedding count mismatch: {len(embeddings)} embeddings "
                    f"for {len(valid_pages)} pages"
                )
                return
                
        except Exception as e:
            logger.error(f"Error generating batch embeddings: {e}")
            raise
        
        # Step 3: Map embeddings back to pages and create points
        points: List[PointStruct] = []
        
        for page, embedding_vector in zip(valid_pages, embeddings):
            # Create deterministic UUID based on doc_id + page_num
            point_id = str(uuid5(NAMESPACE_DNS, f"{document.id}:{page.page_number}"))
            
            # Extract page text for preview
            page_text = self._extract_page_text(page)
            
            # Create point with metadata
            point = PointStruct(
                id=point_id,
                vector=embedding_vector.tolist(),
                payload={
                    "doc_id": document.id,
                    "page_num": page.page_number,
                    "metadata": document.metadata.model_dump(),
                    "text_preview": page_text[:200]  # Store preview for debugging
                }
            )
            
            points.append(point)
        
        # Upload all points to Qdrant
        try:
            await self.client.upsert(
                collection_name=self.collection_name,
                points=points
            )
            logger.success(
                f"Stored {len(points)} page embeddings for document {document.id}"
            )
        except Exception as e:
            logger.error(f"Failed to upsert points to Qdrant: {e}")
            raise
    
    async def semantic_search(
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
            search_results = await self.client.search(
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
    
    async def close(self) -> None:
        """Close the async Qdrant client and cleanup resources."""
        logger.info("Closing async Qdrant client")
        await self.client.close()
    
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
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.ensure_collection_exists()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
