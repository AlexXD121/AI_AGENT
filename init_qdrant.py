"""Initialize Qdrant collection for Sovereign-Doc."""

import asyncio
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
from loguru import logger

async def main():
    print("Initializing Qdrant collection...")
    
    # Connect to Qdrant
    client = QdrantClient(host="localhost", port=6333)
    
    collection_name = "documents"
    vector_size = 384  # BGE-small-en-v1.5 embedding dimension
    
    try:
        # Check if collection exists
        collections = client.get_collections().collections
        exists = any(c.name == collection_name for c in collections)
        
        if exists:
            print(f"✅ Collection '{collection_name}' already exists!")
        else:
            # Create collection
            client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=vector_size,
                    distance=Distance.COSINE
                )
            )
            print(f"✅ Collection '{collection_name}' created successfully!")
        
        print(f"   - Vector Size: {vector_size}")
        print(f"   - Distance: COSINE")
        print(f"   - Host: localhost:6333")
        
        return 0
        
    except Exception as e:
        logger.error(f"Failed to create collection: {e}")
        print(f"❌ Failed: {e}")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
