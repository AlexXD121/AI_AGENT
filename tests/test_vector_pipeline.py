"""Tests for Document Vector Pipeline (Task 8.1).

This test suite verifies the smart chunking strategy that creates
structure-aware embeddings for vision summaries, tables, and text regions.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from uuid import uuid4
from datetime import datetime

from local_body.database.vector_store import DocumentVectorStore
from local_body.core.datamodels import (
    Document,
    DocumentMetadata,
    Page,
    Region,
    BoundingBox,
    RegionType,
    TextContent,
    TableContent,
    ProcessingStatus
)
from local_body.core.config_manager import SystemConfig


@pytest.fixture
def mock_config():
    """Create mock SystemConfig for testing."""
    config = MagicMock(spec=SystemConfig)
    config.qdrant_host = "localhost"
    config.qdrant_port = 6333
    config.embedding_model = "BAAI/bge-small-en-v1.5"
    config.vector_collection = "test_documents"
    return config


@pytest.fixture
def sample_document_with_structure():
    """Create a document with vision summary, table, and text regions."""
    
    # Create a page with vision summary in metadata
    page = Page(
        page_number=1,
        raw_image_bytes=None,
        metadata={'vision_summary': 'This is a balance sheet showing company financials.'},
        regions=[
            # Table region
            Region(
                bbox=BoundingBox(x=10, y=10, width=200, height=100),
                region_type=RegionType.TABLE,
                content=TableContent(
                    rows=[["Revenue", "500"], ["Expenses", "300"]],
                    text="Revenue,500\nExpenses,300",  # CSV representation
                    confidence=0.95
                ),
                confidence=0.95,
                extraction_method="yolov8"
            ),
            # Text region
            Region(
                bbox=BoundingBox(x=10, y=120, width=200, height=50),
                region_type=RegionType.TEXT,
                content=TextContent(
                    text="CEO Statement: We achieved strong growth this quarter.",
                    confidence=0.92
                ),
                confidence=0.92,
                extraction_method="paddleocr"
            )
        ]
    )
    
    doc = Document(
        id=str(uuid4()),
        file_path="/test/financials.pdf",
        pages=[page],
        metadata=DocumentMetadata(
            file_size_bytes=1024,
            page_count=1,
            created_date=datetime.now()
        ),
        processing_status=ProcessingStatus.COMPLETED,
        created_at=datetime.now()
    )
    
    return doc


class TestSmartChunking:
    """Test suite for structure-aware document chunking."""
    
    @patch('local_body.database.vector_store.TextEmbedding')
    @patch('local_body.database.vector_store.AsyncQdrantClient')
    def test_chunk_document_structure_aware(
        self, 
        mock_qdrant_client, 
        mock_embedding,
        mock_config,
        sample_document_with_structure
    ):
        """Test 1: Smart chunking creates separate chunks for summary, table, and text."""
        # Setup
        store = DocumentVectorStore(mock_config)
        
        # Execute
        chunks = store._chunk_document(sample_document_with_structure)
        
        # Assert: We should have exactly 3 chunks
        assert len(chunks) == 3, f"Expected 3 chunks, got {len(chunks)}"
        
        # Extract chunk types
        chunk_types = [chunk['payload']['type'] for chunk in chunks]
        
        # Assert: Chunk types should be summary, table, text
        assert 'summary' in chunk_types, "Missing vision summary chunk"
        assert 'table' in chunk_types, "Missing table chunk"
        assert 'text' in chunk_types, "Missing text chunk"
        
    @patch('local_body.database.vector_store.TextEmbedding')
    @patch('local_body.database.vector_store.AsyncQdrantClient')
    def test_chunk_metadata_richness(
        self, 
        mock_qdrant_client, 
        mock_embedding,
        mock_config,
        sample_document_with_structure
    ):
        """Test 2: Chunks contain rich metadata for filtering."""
        # Setup
        store = DocumentVectorStore(mock_config)
        
        # Execute
        chunks = store._chunk_document(sample_document_with_structure)
        
        # Assert: Each chunk has required metadata
        for chunk in chunks:
            assert 'id' in chunk, "Missing chunk ID"
            assert 'text' in chunk, "Missing chunk text"
            assert 'payload' in chunk, "Missing chunk payload"
            
            payload = chunk['payload']
            assert 'source' in payload, "Missing source field"
            assert 'doc_id' in payload, "Missing doc_id field"
            assert 'page' in payload, "Missing page field"
            assert 'type' in payload, "Missing type field"
            assert 'file_path' in payload, "Missing file_path field"
        
        # Verify vision summary metadata
        vision_chunk = next(c for c in chunks if c['payload']['type'] == 'summary')
        assert vision_chunk['payload']['source'] == 'vision'
        assert vision_chunk['text'] == 'This is a balance sheet showing company financials.'
        
        # Verify table metadata
        table_chunk = next(c for c in chunks if c['payload']['type'] == 'table')
        assert table_chunk['payload']['source'] == 'layout'
        assert table_chunk['payload']['region_type'] == 'table'
        assert 'Revenue,500' in table_chunk['text']
        
        # Verify text metadata
        text_chunk = next(c for c in chunks if c['payload']['type'] == 'text')
        assert text_chunk['payload']['source'] == 'ocr'
        assert 'CEO Statement' in text_chunk['text']
    
    @patch('local_body.database.vector_store.TextEmbedding')
    @patch('local_body.database.vector_store.AsyncQdrantClient')
    def test_chunk_empty_document(
        self, 
        mock_qdrant_client, 
        mock_embedding,
        mock_config
    ):
        """Test 3: Empty documents produce no chunks."""
        # Setup
        store = DocumentVectorStore(mock_config)
        
        # Create document with no content
        empty_doc = Document(
            id=str(uuid4()),
            file_path="/test/empty.pdf",
            pages=[Page(page_number=1, raw_image_bytes=None, regions=[])],
            metadata=DocumentMetadata(
                file_size_bytes=0,
                page_count=1,
                created_date=datetime.now()
            ),
            processing_status=ProcessingStatus.COMPLETED,
            created_at=datetime.now()
        )
        
        # Execute
        chunks = store._chunk_document(empty_doc)
        
        # Assert: No chunks should be generated
        assert len(chunks) == 0, "Empty document should produce no chunks"


class TestDocumentIngestion:
    """Test suite for add_processed_document method."""
    
    @pytest.mark.asyncio
    @patch('local_body.database.vector_store.TextEmbedding')
    @patch('local_body.database.vector_store.AsyncQdrantClient')
    async def test_add_processed_document_calls_client(
        self, 
        mock_qdrant_client, 
        mock_embedding_class,
        mock_config,
        sample_document_with_structure
    ):
        """Test 4: add_processed_document generates embeddings and uploads to Qdrant."""
        # Setup
        mock_embedding_instance = MagicMock()
        mock_embedding_class.return_value = mock_embedding_instance
        
        # Mock embedding generation
        import numpy as np
        mock_embedding_instance.embed.return_value = [
            np.random.rand(384),
            np.random.rand(384),
            np.random.rand(384)
        ]
        
        # Mock Qdrant client methods
        mock_client_instance = AsyncMock()
        mock_qdrant_client.return_value = mock_client_instance
        
        store = DocumentVectorStore(mock_config)
        
        # Execute
        await store.add_processed_document(sample_document_with_structure)
        
        # Assert: embed was called with correct number of chunks
        assert mock_embedding_instance.embed.called, "Embedding model should be called"
        call_args = mock_embedding_instance.embed.call_args[0][0]
        assert len(call_args) == 3, f"Should embed 3 chunks, got {len(call_args)}"
        
        # Assert: Qdrant upsert was called
        assert mock_client_instance.upsert.called, "Qdrant upsert should be called"
        
        # Verify first upsert call
        upsert_call = mock_client_instance.upsert.call_args
        assert upsert_call[1]['collection_name'] == 'test_documents'
        uploaded_points = upsert_call[1]['points']
        assert len(uploaded_points) == 3, f"Should upload 3 points, got {len(uploaded_points)}"
        
    @pytest.mark.asyncio
    @patch('local_body.database.vector_store.TextEmbedding')
    @patch('local_body.database.vector_store.AsyncQdrantClient')
    async def test_add_processed_document_handles_empty(
        self, 
        mock_qdrant_client, 
        mock_embedding_class,
        mock_config
    ):
        """Test 5: add_processed_document handles empty documents gracefully."""
        # Setup
        mock_embedding_instance = MagicMock()
        mock_embedding_class.return_value = mock_embedding_instance
        
        mock_client_instance = AsyncMock()
        mock_qdrant_client.return_value = mock_client_instance
        
        store = DocumentVectorStore(mock_config)
        
        # Create empty document
        empty_doc = Document(
            id=str(uuid4()),
            file_path="/test/empty.pdf",
            pages=[Page(page_number=1, raw_image_bytes=None, regions=[])],
            metadata=DocumentMetadata(
                file_size_bytes=0,
                page_count=1,
                created_date=datetime.now()
            ),
            processing_status=ProcessingStatus.COMPLETED,
            created_at=datetime.now()
        )
        
        # Execute
        await store.add_processed_document(empty_doc)
        
        # Assert: No embedding or upsert should occur
        assert not mock_embedding_instance.embed.called, "Should not generate embeddings for empty doc"
        assert not mock_client_instance.upsert.called, "Should not upsert empty doc"
    
    @pytest.mark.asyncio
    @patch('local_body.database.vector_store.TextEmbedding')
    @patch('local_body.database.vector_store.AsyncQdrantClient')
    async def test_batch_processing(
        self, 
        mock_qdrant_client, 
        mock_embedding_class,
        mock_config
    ):
        """Test 6: Large documents are processed in batches."""
        # Setup
        mock_embedding_instance = MagicMock()
        mock_embedding_class.return_value = mock_embedding_instance
        
        mock_client_instance = AsyncMock()
        mock_qdrant_client.return_value = mock_client_instance
        
        store = DocumentVectorStore(mock_config)
        
        # Create document with 75 chunks (should result in 2 batches of 50 and 25)
        large_doc = Document(
            id=str(uuid4()),
            file_path="/test/large.pdf",
            pages=[
                Page(
                    page_number=i+1,  # Page numbers start from 1
                    raw_image_bytes=None,
                    regions=[
                        Region(
                            bbox=BoundingBox(x=0, y=0, width=100, height=100),
                            region_type=RegionType.TEXT,
                            content=TextContent(text=f"Text block {i}", confidence=0.9),
                            confidence=0.9,
                            extraction_method="paddleocr"
                        )
                    ]
                )
                for i in range(75)
            ],
            metadata=DocumentMetadata(
                file_size_bytes=10000,
                page_count=75,
                created_date=datetime.now()
            ),
            processing_status=ProcessingStatus.COMPLETED,
            created_at=datetime.now()
        )
        
        # Mock 75 embeddings
        import numpy as np
        mock_embedding_instance.embed.return_value = [
            np.random.rand(384) for _ in range(75)
        ]
        
        # Execute
        await store.add_processed_document(large_doc)
        
        # Assert: Upsert should be called twice (batch_size=50)
        assert mock_client_instance.upsert.call_count == 2, \
            f"Expected 2 batches for 75 chunks, got {mock_client_instance.upsert.call_count}"
        
        # Verify batch sizes
        first_batch = mock_client_instance.upsert.call_args_list[0][1]['points']
        second_batch = mock_client_instance.upsert.call_args_list[1][1]['points']
        
        assert len(first_batch) == 50, f"First batch should have 50 points, got {len(first_batch)}"
        assert len(second_batch) == 25, f"Second batch should have 25 points, got {len(second_batch)}"
