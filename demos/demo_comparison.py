"""Comparative Document Analysis Demo.

Demonstrates multi-document querying and comparison using the RAG engine.
Compares two documents and answers analytical questions across them.

Usage:
    python demos/demo_comparison.py <doc1.pdf> <doc2.pdf> [query]
"""

import sys
import asyncio
from pathlib import Path

from utils import (
    setup_demo_env,
    print_header,
    run_workflow,
    print_result_summary
)

from loguru import logger


def main():
    """Run comparative document analysis demo."""
    
    # Setup
    env = setup_demo_env()
    print_header("COMPARATIVE DOCUMENT ANALYSIS DEMO")
    
    # Get file paths
    if len(sys.argv) < 3:
        logger.error("Two documents required for comparison")
        logger.info("Usage: python demos/demo_comparison.py <doc1.pdf> <doc2.pdf> [query]")
        logger.info("Example: python demos/demo_comparison.py q3_report.pdf q4_report.pdf")
        
        # Try default examples
        test_dir = Path(env['project_root']) / "test_data" / "quarterly_reports"
        if test_dir.exists():
            pdfs = list(test_dir.glob("*.pdf"))
            if len(pdfs) >= 2:
                doc1_path = str(pdfs[0])
                doc2_path = str(pdfs[1])
                logger.info(f"Using sample documents: {pdfs[0].name}, {pdfs[1].name}")
            else:
                return 1
        else:
            return 1
    else:
        doc1_path = sys.argv[1]
        doc2_path = sys.argv[2]
    
    # Optional custom query
    if len(sys.argv) > 3:
        query = " ".join(sys.argv[3:])
    else:
        query = "Compare the key financial metrics between these two documents"
    
    logger.info(f"Document A: {doc1_path}")
    logger.info(f"Document B: {doc2_path}")
    logger.info(f"Query: {query}")
    
    print("""
🔍 Comparative Analysis Features:
  ✓ Process multiple documents independently
  ✓ Index to vector database for semantic search
  ✓ Cross-document querying with RAG
  ✓ Synthesized answers from multiple sources
  ✓ Citation tracking
""")
    
    try:
        # Process Document A
        print("\n" + "="*80)
        print("📄 Processing Document A...")
        print("="*80)
        state_a = run_workflow(doc1_path)
        print_result_summary(state_a)
        
        # Process Document B
        print("\n" + "="*80)
        print("📄 Processing Document B...")
        print("="*80)
        state_b = run_workflow(doc2_path)
        print_result_summary(state_b)
        
        # Index both documents to vector store
        print("\n" + "="*80)
        print("💾 Indexing Documents to Knowledge Base...")
        print("="*80)
        
        from local_body.database.vector_store import DocumentVectorStore
        
        vector_store = DocumentVectorStore()
        
        async def index_documents():
            """Index both documents."""
            doc_a = state_a.get('document')
            doc_b = state_b.get('document')
            
            if doc_a:
                logger.info(f"Indexing Document A: {doc_a.file_path}")
                await vector_store.ingest_document(doc_a)
                logger.success("✓ Document A indexed")
            
            if doc_b:
                logger.info(f"Indexing Document B: {doc_b.file_path}")
                await vector_store.ingest_document(doc_b)
                logger.success("✓ Document B indexed")
        
        # Run async indexing
        asyncio.run(index_documents())
        
        # Query across both documents
        print("\n" + "="*80)
        print("🤖 Running Comparative Query...")
        print("="*80)
        print(f"\n💬 Query: {query}\n")
        
        from local_body.database.multi_doc_query import MultiDocQueryEngine
        
        query_engine = MultiDocQueryEngine()
        
        async def run_query():
            """Execute comparative query."""
            # Get document IDs
            doc_a_id = state_a.get('document').id if state_a.get('document') else None
            doc_b_id = state_b.get('document').id if state_b.get('document') else None
            
            if not (doc_a_id and doc_b_id):
                logger.error("Document IDs not available")
                return None
            
            # Run query
            result = await query_engine.query_multiple_documents(
                query=query,
                document_ids=[doc_a_id, doc_b_id]
            )
            
            return result
        
        result = asyncio.run(run_query())
        
        if result:
            print("📊 Analysis Result:")
            print("="*80)
            print(result.get('answer', 'No answer generated'))
            print()
            
            # Show citations
            citations = result.get('citations', [])
            if citations:
                print("\n📚 Sources:")
                for idx, citation in enumerate(citations, 1):
                    print(f"  [{idx}] {citation.get('document_name')} (Page {citation.get('page', 'N/A')})")
                print()
        else:
            logger.warning("No result generated from query")
        
        # Show comparison stats
        print("\n📈 Comparison Statistics:")
        print("="*80)
        
        from tabulate import tabulate
        
        # Extract metrics
        doc_a = state_a.get('document')
        doc_b = state_b.get('document')
        
        comparison_data = [
            ["Pages", 
             len(doc_a.pages) if doc_a and hasattr(doc_a, 'pages') else 0,
             len(doc_b.pages) if doc_b and hasattr(doc_b, 'pages') else 0],
            ["Regions",
             len(state_a.get('layout_regions', [])),
             len(state_b.get('layout_regions', []))],
            ["Conflicts",
             len(state_a.get('conflicts', [])),
             len(state_b.get('conflicts', []))],
            ["OCR Confidence",
             f"{state_a.get('ocr_results', {}).get('avg_confidence', 0.0):.1%}",
             f"{state_b.get('ocr_results', {}).get('avg_confidence', 0.0):.1%}"]
        ]
        
        print(tabulate(
            comparison_data,
            headers=["Metric", "Document A", "Document B"],
            tablefmt="grid"
        ))
        print()
        
        logger.success("Comparative analysis demo complete!")
        return 0
        
    except Exception as e:
        logger.error(f"Demo failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
