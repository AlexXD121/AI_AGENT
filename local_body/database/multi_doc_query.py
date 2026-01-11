"""Multi-document querying and analysis system.

This module provides high-level query capabilities across multiple documents
using the hybrid search foundation. Supports:
- Cross-document search with grouping
- Comparative analysis (e.g., comparing revenue across quarters)
- Trend analysis with temporal ordering
"""

from typing import List, Optional, Dict, Any
from collections import defaultdict

from loguru import logger

from local_body.database.vector_store import DocumentVectorStore
from local_body.agents.validation_agent import ValidationAgent


class MultiDocumentQuery:
    """High-level query interface for multi-document analysis.
    
    This class provides analytical capabilities on top of hybrid search:
    - Cross-document search with flexible grouping
    - Comparative field extraction across documents
    - Trend analysis with temporal ordering
    """
    
    def __init__(self, vector_store: DocumentVectorStore):
        """Initialize multi-document query system.
        
        Args:
            vector_store: Initialized DocumentVectorStore instance
        """
        self.store = vector_store
        self.validation_agent = ValidationAgent(config={})  # For numeric extraction
        
        logger.info("MultiDocumentQuery initialized")
    
    async def cross_document_search(
        self,
        query: str,
        doc_ids: Optional[List[str]] = None,
        group_by: str = "document",
        limit: int = 20
    ) -> Dict[str, Any]:
        """Search across multiple documents with flexible grouping.
        
        Example queries:
        - "Privacy Policy section" - Find privacy sections in all docs
        - "Revenue table" - Find revenue tables across documents
        - "CEO statement" - Find CEO statements in quarterly reports
        
        Args:
            query: Search query text
            doc_ids: Optional list of document IDs to restrict search
            group_by: Grouping strategy - "document", "type", or "ungrouped"
            limit: Maximum total results to retrieve
        
        Returns:
            Dict with query, grouped_results, and total_count
        """
        logger.info(f"Cross-document search: '{query}' (group_by={group_by}, limit={limit})")
        
        # Perform hybrid search
        all_results = await self.store.hybrid_search(
            query_text=query,
            limit=limit
        )
        
        # Filter by doc_ids if provided
        if doc_ids:
            filtered_results = [
                r for r in all_results 
                if r.get('doc_id') in doc_ids
            ]
            logger.debug(f"Filtered from {len(all_results)} to {len(filtered_results)} results")
        else:
            filtered_results = all_results
        
        # Group results
        if group_by == "document":
            grouped = defaultdict(list)
            for result in filtered_results:
                doc_id = result.get('doc_id', 'unknown')
                grouped[doc_id].append(result)
            grouped_results = dict(grouped)
            
        elif group_by == "type":
            grouped = defaultdict(list)
            for result in filtered_results:
                result_type = result.get('type', 'unknown')
                grouped[result_type].append(result)
            grouped_results = dict(grouped)
            
        elif group_by == "ungrouped":
            grouped_results = filtered_results
            
        else:
            raise ValueError(f"Invalid group_by value: {group_by}. Use 'document', 'type', or 'ungrouped'")
        
        logger.success(
            f"Cross-document search complete: {len(filtered_results)} results "
            f"grouped by {group_by}"
        )
        
        return {
            "query": query,
            "grouped_results": grouped_results,
            "total_count": len(filtered_results),
            "group_by": group_by
        }
    
    async def comparative_analysis(
        self,
        field_name: str,
        doc_ids: List[str]
    ) -> Dict[str, Any]:
        """Extract and compare a specific field across multiple documents.
        
        Example use cases:
        - Compare "Total Revenue" across Q1, Q2, Q3 reports
        - Compare "Operating Costs" across fiscal years
        - Compare "Employee Count" across annual reports
        
        Args:
            field_name: Name of field to extract (e.g., "Total Revenue")
            doc_ids: List of document IDs to compare
        
        Returns:
            Dict mapping doc_id to extracted value with metadata
        """
        logger.info(f"Comparative analysis: '{field_name}' across {len(doc_ids)} documents")
        
        results = {}
        
        for doc_id in doc_ids:
            # Search for field in this specific document
            search_results = await self.store.hybrid_search(
                query_text=field_name,
                limit=5  # Get top 5 matches for this field
            )
            
            # Filter to this document only
            doc_results = [r for r in search_results if r.get('doc_id') == doc_id]
            
            if not doc_results:
                logger.warning(f"No results found for '{field_name}' in document {doc_id}")
                results[doc_id] = {
                    "value": None,
                    "source_text": None,
                    "confidence": 0.0,
                    "error": "No matching content found"
                }
                continue
            
            # Try to extract numeric value from top results
            extracted_value = None
            source_text = None
            confidence = 0.0
            
            for hit in doc_results:
                text_preview = hit.get('text_preview', '')
                
                # Use ValidationAgent's extract_numeric_value
                numeric_value = self.validation_agent.extract_numeric_value(text_preview)
                
                if numeric_value is not None:
                    # Found a valid numeric value
                    extracted_value = numeric_value
                    source_text = text_preview
                    confidence = hit.get('score', 0.0)
                    logger.debug(
                        f"Extracted {field_name}={extracted_value} from {doc_id} "
                        f"(confidence={confidence:.3f})"
                    )
                    break
            
            if extracted_value is None:
                logger.warning(f"Could not extract numeric value for '{field_name}' in {doc_id}")
            
            results[doc_id] = {
                "value": extracted_value,
                "source_text": source_text,
                "confidence": confidence,
                "field_name": field_name
            }
        
        # Calculate summary statistics
        valid_values = [
            r['value'] for r in results.values() 
            if r['value'] is not None
        ]
        
        summary = {
            "field_name": field_name,
            "documents_analyzed": len(doc_ids),
            "values_extracted": len(valid_values),
            "results": results
        }
        
        if valid_values:
            summary["min"] = min(valid_values)
            summary["max"] = max(valid_values)
            summary["avg"] = sum(valid_values) / len(valid_values)
        
        logger.success(
            f"Comparative analysis complete: {len(valid_values)}/{len(doc_ids)} "
            f"values extracted for '{field_name}'"
        )
        
        return summary
    
    async def trend_analysis(
        self,
        field_name: str,
        doc_ids: List[str],
        sort_by_metadata: str = "created_date"
    ) -> Dict[str, Any]:
        """Analyze trends of a field across ordered documents.
        
        Example use cases:
        - Track revenue growth over quarters
        - Monitor cost trends over fiscal years
        - Analyze employee headcount changes
        
        Args:
            field_name: Name of field to analyze
            doc_ids: List of document IDs (ideally chronologically ordered)
            sort_by_metadata: Metadata field to use for ordering (if available)
        
        Returns:
            Dict with ordered values and trend statistics
        """
        logger.info(f"Trend analysis: '{field_name}' across {len(doc_ids)} documents")
        
        # Get comparative analysis first
        comparative_results = await self.comparative_analysis(field_name, doc_ids)
        
        # Extract values in document order
        ordered_values = []
        for doc_id in doc_ids:
            if doc_id in comparative_results['results']:
                result = comparative_results['results'][doc_id]
                if result['value'] is not None:
                    ordered_values.append({
                        "doc_id": doc_id,
                        "value": result['value'],
                        "confidence": result['confidence']
                    })
        
        # Calculate trend metrics
        trend_metrics = {
            "field_name": field_name,
            "ordered_values": ordered_values,
            "total_points": len(ordered_values)
        }
        
        if len(ordered_values) >= 2:
            # Calculate percentage change
            first_value = ordered_values[0]['value']
            last_value = ordered_values[-1]['value']
            
            if first_value != 0:
                pct_change = ((last_value - first_value) / abs(first_value)) * 100
                trend_metrics["percent_change"] = pct_change
                trend_metrics["direction"] = "increasing" if pct_change > 0 else "decreasing"
            
            # Calculate period-over-period changes
            period_changes = []
            for i in range(1, len(ordered_values)):
                prev_val = ordered_values[i-1]['value']
                curr_val = ordered_values[i]['value']
                
                if prev_val != 0:
                    change_pct = ((curr_val - prev_val) / abs(prev_val)) * 100
                    period_changes.append(change_pct)
            
            if period_changes:
                trend_metrics["avg_period_change"] = sum(period_changes) / len(period_changes)
        
        logger.success(
            f"Trend analysis complete: {len(ordered_values)} data points for '{field_name}'"
        )
        
        return trend_metrics
