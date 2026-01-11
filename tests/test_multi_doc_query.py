"""Tests for Multi-Document Query System (Task 8.3).

This test suite verifies the high-level query capabilities:
- Cross-document search with grouping
- Comparative analysis across documents
- Trend analysis with metrics
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from local_body.database.multi_doc_query import MultiDocumentQuery


@pytest.fixture
def mock_vector_store():
    """Create a mock DocumentVectorStore."""
    mock_store = AsyncMock()
    return mock_store


@pytest.fixture
def multi_doc_query(mock_vector_store):
    """Create MultiDocumentQuery instance with mocked store."""
    return MultiDocumentQuery(mock_vector_store)


class TestCrossDocumentSearch:
    """Test suite for cross-document search with grouping."""
    
    @pytest.mark.asyncio
    async def test_search_grouped_by_document(self, multi_doc_query, mock_vector_store):
        """Test 1: Cross-document search groups results by document ID."""
        # Setup mock results
        mock_vector_store.hybrid_search.return_value = [
            {"doc_id": "doc_a", "page": 1, "text_preview": "Privacy Policy text", "score": 0.95},
            {"doc_id": "doc_a", "page": 3, "text_preview": "Privacy terms", "score": 0.88},
            {"doc_id": "doc_b", "page": 1, "text_preview": "Privacy conditions", "score": 0.92},
            {"doc_id": "doc_b", "page": 2, "text_preview": "Privacy statement", "score": 0.85}
        ]
        
        # Execute
        result = await multi_doc_query.cross_document_search(
            query="Privacy Policy",
            group_by="document",
            limit=20
        )
        
        # Assert structure
        assert result["query"] == "Privacy Policy"
        assert result["total_count"] == 4
        assert result["group_by"] == "document"
        
        # Assert grouping
        grouped = result["grouped_results"]
        assert "doc_a" in grouped
        assert "doc_b" in grouped
        assert len(grouped["doc_a"]) == 2
        assert len(grouped["doc_b"]) == 2
        
        # Verify search was called
        mock_vector_store.hybrid_search.assert_called_once_with(
            query_text="Privacy Policy",
            limit=20
        )
    
    @pytest.mark.asyncio
    async def test_search_grouped_by_type(self, multi_doc_query, mock_vector_store):
        """Test 2: Cross-document search groups results by content type."""
        # Setup mock results
        mock_vector_store.hybrid_search.return_value = [
            {"doc_id": "doc_a", "type": "table", "text_preview": "Revenue table", "score": 0.95},
            {"doc_id": "doc_a", "type": "text", "text_preview": "Revenue text", "score": 0.88},
            {"doc_id": "doc_b", "type": "table", "text_preview": "Revenue data", "score": 0.92},
            {"doc_id": "doc_b", "type": "summary", "text_preview": "Revenue summary", "score": 0.85}
        ]
        
        # Execute
        result = await multi_doc_query.cross_document_search(
            query="Revenue",
            group_by="type",
            limit=20
        )
        
        # Assert grouping by type
        grouped = result["grouped_results"]
        assert "table" in grouped
        assert "text" in grouped
        assert "summary" in grouped
        assert len(grouped["table"]) == 2
        assert len(grouped["text"]) == 1
        assert len(grouped["summary"]) == 1
    
    @pytest.mark.asyncio
    async def test_search_with_doc_filter(self, multi_doc_query, mock_vector_store):
        """Test 3: Filter results to specific document IDs."""
        # Setup mock results (4 docs, but we'll filter to 2)
        mock_vector_store.hybrid_search.return_value = [
            {"doc_id": "doc_a", "text_preview": "Content A", "score": 0.95},
            {"doc_id": "doc_b", "text_preview": "Content B", "score": 0.92},
            {"doc_id": "doc_c", "text_preview": "Content C", "score": 0.88},
            {"doc_id": "doc_d", "text_preview": "Content D", "score": 0.85}
        ]
        
        # Execute with filter
        result = await multi_doc_query.cross_document_search(
            query="test",
            doc_ids=["doc_a", "doc_c"],  # Only these two
            group_by="ungrouped",
            limit=20
        )
        
        # Assert only filtered docs remain
        assert result["total_count"] == 2
        results = result["grouped_results"]
        doc_ids = [r["doc_id"] for r in results]
        assert "doc_a" in doc_ids
        assert "doc_c" in doc_ids
        assert "doc_b" not in doc_ids
        assert "doc_d" not in doc_ids
    
    @pytest.mark.asyncio
    async def test_search_ungrouped(self, multi_doc_query, mock_vector_store):
        """Test 4: Ungrouped search returns flat list."""
        # Setup mock results
        mock_vector_store.hybrid_search.return_value = [
            {"doc_id": "doc_a", "score": 0.95},
            {"doc_id": "doc_b", "score": 0.92}
        ]
        
        # Execute
        result = await multi_doc_query.cross_document_search(
            query="test",
            group_by="ungrouped",
            limit=10
        )
        
        # Assert ungrouped (flat list)
        assert isinstance(result["grouped_results"], list)
        assert len(result["grouped_results"]) == 2


class TestComparativeAnalysis:
    """Test suite for comparative analysis across documents."""
    
    @pytest.mark.asyncio
    async def test_extract_revenue_from_multiple_docs(self, multi_doc_query, mock_vector_store):
        """Test 5: Extract and compare revenue values across documents."""
        # Mock search results for each document
        async def mock_search(query_text, limit):
            # Return different results based on query context
            # This simulates searching each document separately
            if hasattr(mock_search, 'call_count'):
                mock_search.call_count += 1
            else:
                mock_search.call_count = 1
            
            # First call (doc_a): Revenue $100M
            if mock_search.call_count == 1:
                return [
                    {"doc_id": "doc_a", "text_preview": "Total Revenue: $100M", "score": 0.95}
                ]
            # Second call (doc_b): Revenue $120M
            elif mock_search.call_count == 2:
                return [
                    {"doc_id": "doc_b", "text_preview": "Total Revenue: $120M", "score": 0.92}
                ]
            return []
        
        mock_vector_store.hybrid_search.side_effect = mock_search
        
        # Execute comparative analysis
        result = await multi_doc_query.comparative_analysis(
            field_name="Total Revenue",
            doc_ids=["doc_a", "doc_b"]
        )
        
        # Assert structure
        assert result["field_name"] == "Total Revenue"
        assert result["documents_analyzed"] == 2
        assert result["values_extracted"] == 2
        
        # Assert extracted values (ValidationAgent should parse $100M and $120M)
        assert "doc_a" in result["results"]
        assert "doc_b" in result["results"]
        
        doc_a_value = result["results"]["doc_a"]["value"]
        doc_b_value = result["results"]["doc_b"]["value"]
        
        # Check that values were extracted (should be 100M and 120M)
        assert doc_a_value == 100_000_000  # $100M
        assert doc_b_value == 120_000_000  # $120M
        
        # Assert summary statistics
        assert result["min"] == 100_000_000
        assert result["max"] == 120_000_000
        assert result["avg"] == 110_000_000
    
    @pytest.mark.asyncio
    async def test_comparative_handles_missing_values(self, multi_doc_query, mock_vector_store):
        """Test 6: Handle documents where field is not found."""
        # Mock: doc_a has value, doc_b doesn't, doc_c has value
        async def mock_search(query_text, limit):
            if hasattr(mock_search, 'call_count'):
                mock_search.call_count += 1
            else:
                mock_search.call_count = 1
            
            if mock_search.call_count == 1:
                return [{"doc_id": "doc_a", "text_preview": "Cost: $50M", "score": 0.9}]
            elif mock_search.call_count == 2:
                return [{"doc_id": "doc_b", "text_preview": "No numeric data", "score": 0.5}]
            elif mock_search.call_count == 3:
                return [{"doc_id": "doc_c", "text_preview": "Cost: $75M", "score": 0.88}]
            return []
        
        mock_vector_store.hybrid_search.side_effect = mock_search
        
        # Execute
        result = await multi_doc_query.comparative_analysis(
            field_name="Operating Cost",
            doc_ids=["doc_a", "doc_b", "doc_c"]
        )
        
        # Assert: doc_a and doc_c have values, doc_b doesn't
        assert result["documents_analyzed"] == 3
        assert result["values_extracted"] == 2  # Only 2 valid values
        
        assert result["results"]["doc_a"]["value"] == 50_000_000
        assert result["results"]["doc_b"]["value"] is None  # No numeric value
        assert result["results"]["doc_c"]["value"] == 75_000_000
    
    @pytest.mark.asyncio
    async def test_comparative_with_percentages(self, multi_doc_query, mock_vector_store):
        """Test 7: Extract percentage values correctly."""
        async def mock_search(query_text, limit):
            if hasattr(mock_search, 'call_count'):
                mock_search.call_count += 1
            else:
                mock_search.call_count = 1
            
            if mock_search.call_count == 1:
                return [{"doc_id": "doc_a", "text_preview": "Growth Rate: 15%", "score": 0.9}]
            elif mock_search.call_count == 2:
                return [{"doc_id": "doc_b", "text_preview": "Growth Rate: 22%", "score": 0.88}]
            return []
        
        mock_vector_store.hybrid_search.side_effect = mock_search
        
        # Execute
        result = await multi_doc_query.comparative_analysis(
            field_name="Growth Rate",
            doc_ids=["doc_a", "doc_b"]
        )
        
        # Assert percentage conversion (15% = 0.15, 22% = 0.22)
        assert result["results"]["doc_a"]["value"] == 0.15
        assert result["results"]["doc_b"]["value"] == 0.22


class TestTrendAnalysis:
    """Test suite for trend analysis."""
    
    @pytest.mark.asyncio
    async def test_trend_calculates_percent_change(self, multi_doc_query, mock_vector_store):
        """Test 8: Trend analysis calculates percentage change."""
        # Mock progressive values: 100M → 120M → 150M
        async def mock_search(query_text, limit):
            if hasattr(mock_search, 'call_count'):
                mock_search.call_count += 1
            else:
                mock_search.call_count = 1
            
            if mock_search.call_count == 1:
                return [{"doc_id": "q1", "text_preview": "Revenue: $100M", "score": 0.9}]
            elif mock_search.call_count == 2:
                return [{"doc_id": "q2", "text_preview": "Revenue: $120M", "score": 0.9}]
            elif mock_search.call_count == 3:
                return [{"doc_id": "q3", "text_preview": "Revenue: $150M", "score": 0.9}]
            return []
        
        mock_vector_store.hybrid_search.side_effect = mock_search
        
        # Execute trend analysis
        result = await multi_doc_query.trend_analysis(
            field_name="Revenue",
            doc_ids=["q1", "q2", "q3"]
        )
        
        # Assert ordered values
        assert result["field_name"] == "Revenue"
        assert result["total_points"] == 3
        assert len(result["ordered_values"]) == 3
        
        # Check values are in order
        assert result["ordered_values"][0]["doc_id"] == "q1"
        assert result["ordered_values"][0]["value"] == 100_000_000
        assert result["ordered_values"][2]["doc_id"] == "q3"
        assert result["ordered_values"][2]["value"] == 150_000_000
        
        # Assert trend metrics
        # From 100M to 150M = 50% increase
        assert result["percent_change"] == 50.0
        assert result["direction"] == "increasing"
        
        # Average period change: (20% + 25%) / 2 = 22.5%
        assert "avg_period_change" in result
        assert abs(result["avg_period_change"] - 22.5) < 0.1
    
    @pytest.mark.asyncio
    async def test_trend_detects_decreasing(self, multi_doc_query, mock_vector_store):
        """Test 9: Trend analysis detects decreasing trends."""
        # Mock declining values: 200 → 180 → 150
        async def mock_search(query_text, limit):
            if hasattr(mock_search, 'call_count'):
                mock_search.call_count += 1
            else:
                mock_search.call_count = 1
            
            values = [200, 180, 150]
            idx = mock_search.call_count - 1
            doc_id = f"period_{idx+1}"
            
            return [{
                "doc_id": doc_id,
                "text_preview": f"Cost: ${values[idx]}M",
                "score": 0.9
            }]
        
        mock_vector_store.hybrid_search.side_effect = mock_search
        
        # Execute
        result = await multi_doc_query.trend_analysis(
            field_name="Cost",
            doc_ids=["period_1", "period_2", "period_3"]
        )
        
        # Assert decreasing trend
        # From 200M to 150M = -25% change
        assert result["percent_change"] == -25.0
        assert result["direction"] == "decreasing"
