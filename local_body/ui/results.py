"""Results visualization and export interface.

This module provides comprehensive results inspection and export:
- JSON tree preview of structured data
- Confidence analytics and charts
- Multi-format export (JSON, Excel, Markdown)
"""

import json
from typing import List, Dict, Any, Optional
from io import BytesIO
from datetime import datetime

import streamlit as st
import pandas as pd
from loguru import logger

from local_body.core.datamodels import Document, RegionType, TextContent, TableContent
from local_body.orchestration.state import DocumentProcessingState


class ResultsRenderer:
    """Render processing results with analytics and export options."""
    
    def __init__(self, state: DocumentProcessingState):
        """Initialize results renderer.
        
        Args:
            state: Final document processing state
        """
        self.state = state
        self.document = state.get('document')
    
    def render(self) -> None:
        """Render the complete results view with tabs."""
        if not self.document:
            st.error("No document data available")
            return
        
        st.title("📊 Processing Results")
        st.caption(f"Document: **{self.document.file_path}**")
        
        # Create tabs for different views
        tab1, tab2, tab3 = st.tabs(["📄 Data Preview", "📊 Analytics", "💾 Export"])
        
        with tab1:
            self._render_data_preview()
        
        with tab2:
            self._render_analytics()
        
        with tab3:
            self._render_export_section()
    
    def _render_data_preview(self) -> None:
        """Render structured data preview."""
        st.subheader("📄 Structured Data")
        
        # Show document metadata
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Pages", len(self.document.pages))
        with col2:
            total_regions = sum(len(page.regions) for page in self.document.pages)
            st.metric("Total Regions", total_regions)
        with col3:
            st.metric("Status", self.document.processing_status.value)
        
        st.divider()
        
        # JSON tree view
        st.markdown("#### JSON Structure")
        st.caption("Full document data in JSON format (excluding raw image bytes)")
        
        try:
            # Convert to dict and exclude heavy fields
            doc_dict = self.document.model_dump(exclude={'pages': {'__all__': {'raw_image_bytes'}}})
            
            # Display with JSON viewer
            st.json(doc_dict, expanded=False)
        
        except Exception as e:
            logger.error(f"Error rendering JSON preview: {e}")
            st.error(f"Could not render JSON: {str(e)}")
    
    def _render_analytics(self) -> None:
        """Render confidence analytics and charts."""
        st.subheader("📊 Confidence Analytics")
        
        # Calculate confidence statistics
        confidence_data = self._calculate_confidence_stats()
        
        if not confidence_data['all_scores']:
            st.warning("No confidence data available")
            return
        
        # Overview metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "Average Confidence",
                f"{confidence_data['average']:.1%}",
                delta="Good" if confidence_data['average'] > 0.8 else "Review"
            )
        
        with col2:
            st.metric(
                "High Confidence",
                f"{confidence_data['high_count']}",
                delta=f"{confidence_data['high_percent']:.0%}"
            )
        
        with col3:
            st.metric(
                "Medium Confidence",
                f"{confidence_data['medium_count']}",
                delta=f"{confidence_data['medium_percent']:.0%}"
            )
        
        with col4:
            st.metric(
                "Low Confidence",
                f"{confidence_data['low_count']}",
                delta=f"{confidence_data['low_percent']:.0%}"
            )
        
        st.divider()
        
        # Confidence by page chart
        st.markdown("#### Confidence by Page")
        page_confidence = confidence_data['by_page']
        
        if page_confidence:
            # Create dataframe for chart
            chart_data = pd.DataFrame({
                'Page': list(page_confidence.keys()),
                'Average Confidence': list(page_confidence.values())
            })
            
            st.bar_chart(chart_data.set_index('Page'))
        
        # Confidence distribution
        st.markdown("#### Confidence Distribution")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Histogram
            dist_data = pd.DataFrame({
                'Confidence Range': ['High (>90%)', 'Medium (70-90%)', 'Low (<70%)'],
                'Count': [
                    confidence_data['high_count'],
                    confidence_data['medium_count'],
                    confidence_data['low_count']
                ]
            })
            st.bar_chart(dist_data.set_index('Confidence Range'))
        
        with col2:
            # Summary statistics
            st.markdown("**Statistics**")
            st.caption(f"Min: {confidence_data['min']:.1%}")
            st.caption(f"Max: {confidence_data['max']:.1%}")
            st.caption(f"Median: {confidence_data['median']:.1%}")
            st.caption(f"Std Dev: {confidence_data['std']:.3f}")
        
        # Processing timeline
        st.divider()
        st.markdown("#### Processing Timeline")
        
        # Show processing stages (if available)
        stage = self.state.get('processing_stage')
        if stage:
            st.success(f"✅ Status: {stage.value}")
        
        # Show completion progress
        st.progress(1.0)
        st.caption("Processing complete")
    
    def _render_export_section(self) -> None:
        """Render export options."""
        st.subheader("💾 Export Results")
        
        st.markdown("""
        Export your processed document in multiple formats:
        - **JSON**: Complete structured data
        - **Excel**: Tabular format for analysis
        - **Markdown**: Human-readable format
        """)
        
        st.divider()
        
        # Export format selection
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # JSON Export
            st.markdown("#### JSON Format")
            st.caption("Complete structured data")
            
            json_data = self._export_json()
            st.download_button(
                label="📥 Download JSON",
                data=json_data,
                file_name=f"{self.document.id}_results.json",
                mime="application/json",
                use_container_width=True
            )
        
        with col2:
            # Excel Export
            st.markdown("#### Excel Format")
            st.caption("Tabular data for spreadsheets")
            
            try:
                excel_data = self._export_excel()
                st.download_button(
                    label="📥 Download Excel",
                    data=excel_data,
                    file_name=f"{self.document.id}_results.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            except Exception as e:
                st.error(f"Excel export failed: {str(e)}")
        
        with col3:
            # Markdown Export
            st.markdown("#### Markdown Format")
            st.caption("Human-readable text")
            
            markdown_data = self._export_markdown()
            st.download_button(
                label="📥 Download Markdown",
                data=markdown_data,
                file_name=f"{self.document.id}_results.md",
                mime="text/markdown",
                use_container_width=True
            )
        
        # Preview section
        st.divider()
        st.markdown("#### Export Preview")
        
        preview_format = st.selectbox(
            "Select format to preview",
            ["JSON", "Excel (table)", "Markdown"]
        )
        
        if preview_format == "JSON":
            st.json(json.loads(json_data), expanded=False)
        elif preview_format == "Excel (table)":
            df = self._to_flat_dataframe()
            st.dataframe(df, use_container_width=True)
        elif preview_format == "Markdown":
            st.markdown(markdown_data)
    
    def _calculate_confidence_stats(self) -> Dict[str, Any]:
        """Calculate confidence statistics from document.
        
        Returns:
            Dictionary with confidence metrics
        """
        all_scores = []
        by_page = {}
        
        for page in self.document.pages:
            page_scores = []
            
            for region in page.regions:
                if hasattr(region, 'confidence') and region.confidence is not None:
                    all_scores.append(region.confidence)
                    page_scores.append(region.confidence)
            
            if page_scores:
                by_page[page.page_number] = sum(page_scores) / len(page_scores)
        
        if not all_scores:
            return {
                'all_scores': [],
                'average': 0.0,
                'min': 0.0,
                'max': 0.0,
                'median': 0.0,
                'std': 0.0,
                'high_count': 0,
                'medium_count': 0,
                'low_count': 0,
                'high_percent': 0.0,
                'medium_percent': 0.0,
                'low_percent': 0.0,
                'by_page': {}
            }
        
        # Calculate statistics
        import statistics
        
        high_count = sum(1 for s in all_scores if s > 0.9)
        medium_count = sum(1 for s in all_scores if 0.7 <= s <= 0.9)
        low_count = sum(1 for s in all_scores if s < 0.7)
        total = len(all_scores)
        
        return {
            'all_scores': all_scores,
            'average': sum(all_scores) / total,
            'min': min(all_scores),
            'max': max(all_scores),
            'median': statistics.median(all_scores),
            'std': statistics.stdev(all_scores) if total > 1 else 0.0,
            'high_count': high_count,
            'medium_count': medium_count,
            'low_count': low_count,
            'high_percent': high_count / total if total > 0 else 0,
            'medium_percent': medium_count / total if total > 0 else 0,
            'low_percent': low_count / total if total > 0 else 0,
            'by_page': by_page
        }
    
    def _to_flat_dataframe(self) -> pd.DataFrame:
        """Convert document to flat tabular format.
        
        Returns:
            Pandas DataFrame with flattened data
        """
        rows = []
        
        for page in self.document.pages:
            for region in page.regions:
                # Extract text content
                text = ""
                if isinstance(region.content, TextContent):
                    text = region.content.text
                elif isinstance(region.content, TableContent):
                    # Convert table to CSV-like string
                    text = "\n".join([",".join(row) for row in region.content.rows])
                
                row = {
                    'Page': page.page_number,
                    'Region ID': region.id if hasattr(region, 'id') else 'N/A',
                    'Type': region.region_type.value if hasattr(region, 'region_type') else 'unknown',
                    'Text': text[:200],  # Truncate for readability
                    'Confidence': region.confidence if hasattr(region, 'confidence') else None,
                    'Source': region.extraction_method if hasattr(region, 'extraction_method') else 'N/A'
                }
                rows.append(row)
        
        return pd.DataFrame(rows)
    
    def _export_json(self) -> str:
        """Export document as JSON string.
        
        Returns:
            JSON string
        """
        # Convert to dict excluding raw bytes
        doc_dict = self.document.model_dump(exclude={'pages': {'__all__': {'raw_image_bytes'}}})
        
        # Serialize with datetime handling
        return json.dumps(doc_dict, indent=2, default=str)
    
    def _export_excel(self) -> bytes:
        """Export document as Excel file.
        
        Returns:
            Excel file as bytes
        """
        df = self._to_flat_dataframe()
        
        # Create Excel file in memory
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Extracted Data', index=False)
            
            # Add metadata sheet
            metadata = pd.DataFrame({
                'Property': ['Document ID', 'Pages', 'Total Regions', 'Processing Status'],
                'Value': [
                    self.document.id,
                    len(self.document.pages),
                    sum(len(page.regions) for page in self.document.pages),
                    self.document.processing_status.value
                ]
            })
            metadata.to_excel(writer, sheet_name='Metadata', index=False)
        
        buffer.seek(0)
        return buffer.read()
    
    def _export_markdown(self) -> str:
        """Export document as Markdown.
        
        Returns:
            Markdown string
        """
        lines = []
        
        # Header
        lines.append(f"# Document: {self.document.id}\n")
        lines.append(f"**Status:** {self.document.processing_status.value}\n")
        lines.append(f"**Pages:** {len(self.document.pages)}\n")
        lines.append("\n---\n")
        
        # Process each page
        for page in self.document.pages:
            lines.append(f"\n## Page {page.page_number}\n")
            
            # Add vision summary if available
            if hasattr(page, 'metadata') and page.metadata:
                vision_summary = page.metadata.get('vision_summary')
                if vision_summary:
                    lines.append(f"\n**Vision Summary:**\n> {vision_summary}\n")
            
            # Add regions
            for idx, region in enumerate(page.regions):
                region_type = region.region_type.value if hasattr(region, 'region_type') else 'unknown'
                lines.append(f"\n### Region {idx + 1}: {region_type}\n")
                
                if isinstance(region.content, TextContent):
                    lines.append(f"\n{region.content.text}\n")
                
                elif isinstance(region.content, TableContent):
                    # Convert to markdown table
                    if region.content.rows:
                        # Header
                        if len(region.content.rows) > 0:
                            lines.append("\n| " + " | ".join(region.content.rows[0]) + " |")
                            lines.append("|" + "|".join(["---"] * len(region.content.rows[0])) + "|")
                            
                            # Data rows
                            for row in region.content.rows[1:]:
                                lines.append("| " + " | ".join(row) + " |")
                        lines.append("\n")
                
                # Add confidence info
                if hasattr(region, 'confidence'):
                    lines.append(f"\n*Confidence: {region.confidence:.1%}*\n")
        
        return "\n".join(lines)


def render_results_section(state: DocumentProcessingState) -> None:
    """Render results section (main entry point).
    
    Args:
        state: Document processing state
    """
    renderer = ResultsRenderer(state)
    renderer.render()
