"""Vector storage and retrieval system using Qdrant.

This module implements the DocumentVectorStore class for storing document
embeddings and performing semantic search using Qdrant vector database.
"""

from typing import List, Optional, Dict, Any
from uuid import uuid5, uuid4, NAMESPACE_DNS
import time
from collections import OrderedDict

from fastembed import TextEmbedding, SparseTextEmbedding
from loguru import logger
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance, 
    VectorParams, 
    PointStruct, 
    SparseVectorParams,
    SparseIndexParams,
    Prefetch,
    QueryRequest,
    FusionQuery,
    Fusion
)
from qdrant_client.http.exceptions import UnexpectedResponse

from local_body.core.config_manager import SystemConfig
from local_body.core.datamodels import (
    Document, 
    Page, 
    Region, 
    TextContent, 
    TableContent,
    RegionType
)


class DocumentVectorStore:
    """Hybrid vector store using dense + sparse embeddings with Qdrant.
    
    This class handles:
    - Initialization of async Qdrant client with dense (BGE) and sparse (SPLADE) embedding models
    - Collection management with named vector configuration (text-dense, text-sparse)
    - Document storage with hybrid embeddings
    - Hybrid search with RRF (Reciprocal Rank Fusion)
    - Performance monitoring and query caching
    - Health checks and connection management
    """
    
    # Cache configuration
    MAX_CACHE_SIZE = 100
    CACHE_TTL_SECONDS = 300  # 5 minutes
    
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
        
        # Initialize dense embedding model (BGE-small-en-v1.5)
        # This model produces 384-dimensional embeddings for semantic search
        logger.info(f"Loading dense embedding model: {config.embedding_model}")
        try:
            self.embedding_model = TextEmbedding(
                model_name=config.embedding_model
            )
            logger.success("Dense embedding model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load dense embedding model: {e}")
            raise
        
        # Initialize sparse embedding model (SPLADE)
        # This model produces sparse vectors for keyword/exact matching
        logger.info("Loading sparse embedding model: prithivida/Splade_PP_en_v1")
        try:
            self.sparse_embedding_model = SparseTextEmbedding(
                model_name="prithivida/Splade_PP_en_v1"
            )
            logger.success("Sparse embedding model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load sparse embedding model: {e}")
            raise
        
        # Collection name
        self.collection_name = config.vector_collection
        
        # Initialize query cache (LRU-style with OrderedDict)
        self.query_cache: OrderedDict[str, tuple[List[Dict[str, Any]], float]] = OrderedDict()
        self._cache_hits = 0
        self._cache_misses = 0
    
    async def ensure_collection_exists(self) -> None:
        """Ensure the document collection exists with hybrid vector configuration.
        
        Creates the collection if it doesn't exist with:
        - Dense vector (text-dense): 384 dimensions (BGE-small-en-v1.5), COSINE distance
        - Sparse vector (text-sparse): SPLADE model for keyword matching
        
        Note: If upgrading from dense-only collection, delete the old collection first.
        """
        try:
            # Check if collection exists
            collections = await self.client.get_collections()
            collection_names = [col.name for col in collections.collections]
            
            if self.collection_name in collection_names:
                logger.info(f"Collection '{self.collection_name}' already exists")
                # TODO: Verify it has sparse vectors config (migration logic)
                logger.warning(
                    "If search fails, the collection may need recreation with sparse vector support. "
                    f"Delete collection '{self.collection_name}' and restart."
                )
                return
            
            # Create collection with hybrid vector configuration
            logger.info(f"Creating hybrid collection '{self.collection_name}'")
            await self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config={
                    "text-dense": VectorParams(
                        size=384,  # BGE-small-en-v1.5 embedding dimension
                        distance=Distance.COSINE
                    )
                },
                sparse_vectors_config={
                    "text-sparse": SparseVectorParams(
                        index=SparseIndexParams(
                            on_disk=False  # Keep sparse index in memory for speed
                        )
                    )
                }
            )
            logger.success(
                f"Hybrid collection '{self.collection_name}' created successfully "
                "(dense + sparse vectors)"
            )
            
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
    
    async def hybrid_search(
        self,
        query_text: str,
        limit: int = 10,
        score_threshold: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """Perform hybrid search using dense + sparse vectors with RRF fusion.
        
        Combines semantic search (dense BGE vectors) with keyword search (sparse SPLADE)
        using Reciprocal Rank Fusion for optimal results.
        
        Args:
            query_text: Text query to search for
            limit: Maximum number of results to return
            score_threshold: Optional minimum similarity score (0-1)
        
        Returns:
            List of search results with fused scores and metadata
        """
        # Step 1: Check cache
        cache_key = f"{query_text}:{limit}:{score_threshold}"
        current_time = time.time()
        
        if cache_key in self.query_cache:
            cached_results, cache_time = self.query_cache[cache_key]
            
            # Check if cache is still valid (TTL)
            if current_time - cache_time < self.CACHE_TTL_SECONDS:
                self._cache_hits += 1
                logger.debug(f"Cache HIT for query: '{query_text[:50]}...' (hits: {self._cache_hits})")
                return cached_results
            else:
                # Expired cache entry
                del self.query_cache[cache_key]
        
        self._cache_misses += 1
        
        # Step 2: Performance monitoring
        start_time = time.perf_counter()
        logger.info(f"Performing hybrid search: '{query_text[:50]}...'")
        
        try:
            # Step 3: Generate dense embedding
            dense_embeddings = list(self.embedding_model.embed([query_text]))
            if not dense_embeddings:
                logger.error("Failed to generate dense query embedding")
                return []
            dense_vector = dense_embeddings[0].tolist()
            
            # Step 4: Generate sparse embedding
            sparse_embeddings = list(self.sparse_embedding_model.query_embed([query_text]))
            if not sparse_embeddings:
                logger.error("Failed to generate sparse query embedding")
                return []
            sparse_vector = sparse_embeddings[0]
            
            # Step 5: Perform hybrid search with RRF fusion
            from qdrant_client.models import SparseVector
            
            search_result = await self.client.query_points(
                collection_name=self.collection_name,
                prefetch=[
                    Prefetch(
                        query=dense_vector,
                        using="text-dense",
                        limit=limit * 2  # Fetch more for better fusion
                    ),
                    Prefetch(
                        query=SparseVector(
                            indices=sparse_vector.indices.tolist(),
                            values=sparse_vector.values.tolist()
                        ),
                        using="text-sparse",
                        limit=limit * 2
                    )
                ],
                query=FusionQuery(fusion=Fusion.RRF),  # Reciprocal Rank Fusion
                limit=limit,
                score_threshold=score_threshold
            )
            
            # Step 6: Format results
            results = []
            for point in search_result.points:
                results.append({
                    "doc_id": point.payload.get("doc_id"),
                    "page": point.payload.get("page"),
                    "type": point.payload.get("type"),
                    "source": point.payload.get("source"),
                    "score": point.score,
                    "text_preview": point.payload.get("text_preview"),
                    "file_path": point.payload.get("file_path")
                })
            
            # Step 7: Log performance
            elapsed = time.perf_counter() - start_time
            logger.info(
                f"Hybrid search complete: {len(results)} results in {elapsed:.4f}s "
                f"(cache misses: {self._cache_misses}, hits: {self._cache_hits})"
            )
            
            # Step 8: Update cache (with LRU eviction)
            if len(self.query_cache) >= self.MAX_CACHE_SIZE:
                # Remove oldest entry (FIFO/LRU)
                self.query_cache.popitem(last=False)
            
            self.query_cache[cache_key] = (results, current_time)
            
            return results
            
        except Exception as e:
            logger.error(f"Hybrid search failed: {e}")
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
    
    def _chunk_document(self, document: Document) -> List[Dict[str, Any]]:
        """Smart chunking strategy that respects document structure.
        
        Creates separate chunks for:
        1. Vision summaries (high-value semantic understanding)
        2. Tables (preserving CSV/Markdown structure)
        3. Text blocks (standard chunks)
        
        Args:
            document: Processed Document with layout, OCR, and vision data
            
        Returns:
            List of chunk dictionaries with id, text, and payload
        """
        chunks = []
        
        for page in document.pages:
            # 1. Extract Vision Summary (if available)
            if page.metadata and 'vision_summary' in page.metadata:
                vision_summary = page.metadata['vision_summary']
                
                if vision_summary and vision_summary.strip():
                    chunks.append({
                        'id': str(uuid4()),
                        'text': vision_summary,
                        'payload': {
                            'source': 'vision',
                            'doc_id': document.id,
                            'page': page.page_number,
                            'type': 'summary',
                            'file_path': document.file_path
                        }
                    })
            
            # 2. Extract Regions (Tables and Text)
            for region in page.regions:
                # Skip regions without text content
                if not hasattr(region, 'content') or region.content is None:
                    continue
                
                # Determine content type and extract text
                text_content = None
                chunk_type = None
                
                if isinstance(region.content, TableContent):
                    # Table: Generate CSV representation from rows
                    if region.content.rows:
                        # Convert rows to CSV-like text
                        text_content = "\n".join([",".join(row) for row in region.content.rows])
                    else:
                        text_content = None
                    chunk_type = 'table'
                    
                elif isinstance(region.content, TextContent):
                    # Text: Standard text chunk
                    text_content = region.content.text
                    chunk_type = 'text'
                
                # Add chunk if we have valid text
                if text_content and text_content.strip():
                    source = 'layout' if chunk_type == 'table' else 'ocr'
                    
                    chunks.append({
                        'id': str(uuid4()),
                        'text': text_content,
                        'payload': {
                            'source': source,
                            'doc_id': document.id,
                            'page': page.page_number,
                            'type': chunk_type,
                            'region_id': region.id,
                            'region_type': region.region_type.value if hasattr(region, 'region_type') else None,
                            'confidence': region.confidence if hasattr(region, 'confidence') else None,
                            'file_path': document.file_path
                        }
                    })
        
        logger.debug(f"Generated {len(chunks)} chunks for document {document.id}")
        return chunks
    
    async def add_processed_document(self, document: Document) -> None:
        """Add a fully processed document to the vector store using smart chunking.
        
        This method:
        1. Chunks the document using structure-aware strategy
        2. Generates embeddings in batches
        3. Stores chunks with rich metadata in Qdrant
        
        Args:
            document: Fully processed Document with OCR, layout, and vision data
        """
        logger.info(f"Adding processed document {document.id} to vector store")
        
        # Step 1: Generate smart chunks
        chunks = self._chunk_document(document)
        
        if not chunks:
            logger.warning(f"No valid chunks generated for document {document.id}")
            return
        
        logger.info(f"Generated {len(chunks)} chunks (summaries, tables, text)")
        
        # Step 2: Extract data for batch processing
        texts = [chunk['text'] for chunk in chunks]
        payloads = [chunk['payload'] for chunk in chunks]
        ids = [chunk['id'] for chunk in chunks]
        
        # Step 3: Generate embeddings in batch
        try:
            logger.debug(f"Generating embeddings for {len(texts)} chunks")
            embeddings = list(self.embedding_model.embed(texts))
            
            if len(embeddings) != len(chunks):
                logger.error(
                    f"Embedding count mismatch: {len(embeddings)} embeddings "
                    f"for {len(chunks)} chunks"
                )
                return
                
        except Exception as e:
            logger.error(f"Error generating batch embeddings: {e}")
            raise
        
        # Step 4: Create Qdrant points
        points: List[PointStruct] = []
        
        for chunk_id, embedding_vector, payload, text in zip(ids, embeddings, payloads, texts):
            point = PointStruct(
                id=chunk_id,
                vector=embedding_vector.tolist(),
                payload={
                    **payload,
                    'text_preview': text[:200]  # Store preview for debugging
                }
            )
            points.append(point)
        
        # Step 5: Upload to Qdrant in batches
        batch_size = 50
        for i in range(0, len(points), batch_size):
            batch = points[i:i + batch_size]
            
            try:
                await self.client.upsert(
                    collection_name=self.collection_name,
                    points=batch
                )
                logger.debug(f"Uploaded batch {i//batch_size + 1}/{(len(points)-1)//batch_size + 1}")
                
            except Exception as e:
                logger.error(f"Failed to upsert batch to Qdrant: {e}")
                raise
        
        logger.success(
            f"Successfully added {len(chunks)} chunks for document {document.id} "
            f"to collection '{self.collection_name}'"
        )
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.ensure_collection_exists()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

