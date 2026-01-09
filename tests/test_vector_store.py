"""Unit tests for DocumentVectorStore.

These tests use mocking to avoid requiring actual Docker/Qdrant running.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from uuid import uuid4

from qdrant_client.http.exceptions import UnexpectedResponse

from local_body.core.config_manager import SystemConfig
from local_body.core.datamodels import (
    Document,
    DocumentMetadata,
    Page,
    Region,
    BoundingBox,
    RegionType,
    TextContent,
    ProcessingStatus
)
from local_body.database.vector_store import DocumentVectorStore


@pytest.fixture
def mock_config():
    """Create a mock SystemConfig for testing."""
    config = SystemConfig(
        qdrant_host="localhost",
        qdrant_port=6333,
        vector_collection="test_documents",
        embedding_model="BGE-small-en-v1.5"
    )
    return config


@pytest.fixture
def sample_document():
    """Create a sample document for testing."""
    doc = Document(
        id=str(uuid4()),
        file_path="/test/document.pdf",
        metadata=DocumentMetadata(
            title="Test Document",
            page_count=2,
            file_size_bytes=1024
        ),
        pages=[
            Page(
                page_number=1,
                regions=[
                    Region(
                        bbox=BoundingBox(x=0, y=0, width=100, height=50),
                        region_type=RegionType.TEXT,
                        content=TextContent(
                            text="This is page one content.",
                            confidence=0.95
                        ),
                        confidence=0.95,
                        extraction_method="ocr"
                    )
                ]
            ),
            Page(
                page_number=2,
                regions=[
                    Region(
                        bbox=BoundingBox(x=0, y=0, width=100, height=50),
                        region_type=RegionType.TEXT,
                        content=TextContent(
                            text="This is page two content.",
                            confidence=0.92
                        ),
                        confidence=0.92,
                        extraction_method="ocr"
                    )
                ]
            )
        ],
        processing_status=ProcessingStatus.COMPLETED
    )
    return doc


class TestDocumentVectorStore:
    """Test suite for DocumentVectorStore class."""
    
    @patch('local_body.database.vector_store.TextEmbedding')
    @patch('local_body.database.vector_store.QdrantClient')
    def test_health_check_connection_error(
        self, 
        mock_qdrant_client, 
        mock_text_embedding,
        mock_config
    ):
        """Test 1: Health check returns False when connection fails."""
        # Setup mocks
        mock_client_instance = MagicMock()
        mock_qdrant_client.return_value = mock_client_instance
        
        # Mock get_collections to succeed (for initialization)
        mock_collections = MagicMock()
        mock_collections.collections = []
        mock_client_instance.get_collections.return_value = mock_collections
        
        # Mock embedding model
        mock_embedding_instance = MagicMock()
        mock_text_embedding.return_value = mock_embedding_instance
        
        # Initialize vector store
        vector_store = DocumentVectorStore(mock_config)
        
        # Mock get_collection to raise ConnectionError
        mock_client_instance.get_collection.side_effect = ConnectionError(
            "Connection refused"
        )
        
        # Test health check
        result = vector_store.check_health()
        
        # Assert
        assert result is False
        mock_client_instance.get_collection.assert_called_once_with(
            collection_name="test_documents"
        )
    
    @patch('local_body.database.vector_store.TextEmbedding')
    @patch('local_body.database.vector_store.QdrantClient')
    def test_initialization_creates_collection(
        self, 
        mock_qdrant_client, 
        mock_text_embedding,
        mock_config
    ):
        """Test 2: Initialization creates collection with size 384."""
        # Setup mocks
        mock_client_instance = MagicMock()
        mock_qdrant_client.return_value = mock_client_instance
        
        # Mock get_collections to return empty list (collection doesn't exist)
        mock_collections = MagicMock()
        mock_collections.collections = []
        mock_client_instance.get_collections.return_value = mock_collections
        
        # Mock embedding model
        mock_embedding_instance = MagicMock()
        mock_text_embedding.return_value = mock_embedding_instance
        
        # Initialize vector store
        vector_store = DocumentVectorStore(mock_config)
        
        # Assert create_collection was called with correct parameters
        mock_client_instance.create_collection.assert_called_once()
        call_args = mock_client_instance.create_collection.call_args
        
        # Check collection name
        assert call_args.kwargs['collection_name'] == "test_documents"
        
        # Check vector config has size 384
        vectors_config = call_args.kwargs['vectors_config']
        assert vectors_config.size == 384
    
    @patch('local_body.database.vector_store.TextEmbedding')
    @patch('local_body.database.vector_store.QdrantClient')
    def test_store_document_with_correct_payload(
        self, 
        mock_qdrant_client, 
        mock_text_embedding,
        mock_config,
        sample_document
    ):
        """Test 3: Document storage creates points with correct payload structure."""
        # Setup mocks
        mock_client_instance = MagicMock()
        mock_qdrant_client.return_value = mock_client_instance
        
        # Mock get_collections
        mock_collections = MagicMock()
        mock_collections.collections = [MagicMock(name="test_documents")]
        mock_client_instance.get_collections.return_value = mock_collections
        
        # Mock embedding model
        mock_embedding_instance = MagicMock()
        # Create mock embeddings that have .tolist() method
        mock_embedding_1 = MagicMock()
        mock_embedding_1.tolist.return_value = [0.1] * 384
        mock_embedding_2 = MagicMock()
        mock_embedding_2.tolist.return_value = [0.2] * 384
        
        # Return dummy embeddings (384-dimensional) as a generator for each call
        # Use side_effect to return different values for each call
        mock_embedding_instance.embed.side_effect = [
            iter([mock_embedding_1]),  # First page embedding (as generator)
            iter([mock_embedding_2])   # Second page embedding (as generator)
        ]
        mock_text_embedding.return_value = mock_embedding_instance
        
        # Initialize vector store
        vector_store = DocumentVectorStore(mock_config)
        
        # Store document
        vector_store.store_document(sample_document)
        
        # Assert upsert was called
        mock_client_instance.upsert.assert_called_once()
        call_args = mock_client_instance.upsert.call_args
        
        # Check collection name
        assert call_args.kwargs['collection_name'] == "test_documents"
        
        # Check points structure
        points = call_args.kwargs['points']
        assert len(points) == 2  # Two pages
        
        # Check first point payload
        first_point = points[0]
        assert first_point.payload['doc_id'] == sample_document.id
        assert first_point.payload['page_num'] == 1
        assert 'metadata' in first_point.payload
        assert first_point.payload['metadata']['title'] == "Test Document"
        
        # Check second point payload
        second_point = points[1]
        assert second_point.payload['doc_id'] == sample_document.id
        assert second_point.payload['page_num'] == 2
    
    @patch('local_body.database.vector_store.TextEmbedding')
    @patch('local_body.database.vector_store.QdrantClient')
    def test_health_check_success(
        self, 
        mock_qdrant_client, 
        mock_text_embedding,
        mock_config
    ):
        """Test: Health check returns True when connection succeeds."""
        # Setup mocks
        mock_client_instance = MagicMock()
        mock_qdrant_client.return_value = mock_client_instance
        
        # Mock get_collections
        mock_collections = MagicMock()
        mock_collections.collections = [MagicMock(name="test_documents")]
        mock_client_instance.get_collections.return_value = mock_collections
        
        # Mock embedding model
        mock_embedding_instance = MagicMock()
        mock_text_embedding.return_value = mock_embedding_instance
        
        # Initialize vector store
        vector_store = DocumentVectorStore(mock_config)
        
        # Mock get_collection to succeed
        mock_client_instance.get_collection.return_value = MagicMock()
        
        # Test health check
        result = vector_store.check_health()
        
        # Assert
        assert result is True
    
    @patch('local_body.database.vector_store.TextEmbedding')
    @patch('local_body.database.vector_store.QdrantClient')
    def test_semantic_search(
        self, 
        mock_qdrant_client, 
        mock_text_embedding,
        mock_config
    ):
        """Test: Semantic search returns formatted results."""
        # Setup mocks
        mock_client_instance = MagicMock()
        mock_qdrant_client.return_value = mock_client_instance
        
        # Mock get_collections
        mock_collections = MagicMock()
        mock_collections.collections = [MagicMock(name="test_documents")]
        mock_client_instance.get_collections.return_value = mock_collections
        
        # Mock embedding model
        mock_embedding_instance = MagicMock()
        # Create mock embedding with .tolist() method
        mock_query_embedding = MagicMock()
        mock_query_embedding.tolist.return_value = [0.1] * 384
        mock_embedding_instance.embed.return_value = iter([mock_query_embedding])  # Return as generator
        mock_text_embedding.return_value = mock_embedding_instance
        
        # Initialize vector store
        vector_store = DocumentVectorStore(mock_config)
        
        # Mock search results
        mock_hit = MagicMock()
        mock_hit.payload = {
            "doc_id": "test-doc-123",
            "page_num": 1,
            "metadata": {"title": "Test"},
            "text_preview": "Sample text"
        }
        mock_hit.score = 0.95
        mock_client_instance.search.return_value = [mock_hit]
        
        # Perform search
        results = vector_store.semantic_search("test query", limit=5)
        
        # Assert
        assert len(results) == 1
        assert results[0]['doc_id'] == "test-doc-123"
        assert results[0]['page_num'] == 1
        assert results[0]['score'] == 0.95
        
        # Verify search was called with correct parameters
        mock_client_instance.search.assert_called_once()
        call_args = mock_client_instance.search.call_args
        assert call_args.kwargs['collection_name'] == "test_documents"
        assert call_args.kwargs['limit'] == 5
