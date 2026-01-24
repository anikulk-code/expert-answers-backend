#!/usr/bin/env python3
"""
Script to set up vector index on Cosmos DB container.

This script:
1. Creates a new container with vector index policy (or updates existing)
2. Configures vector index for embeddings (3072 dimensions, flat index)
3. Migrates data if creating new container

Note: Vector indexes can only be applied to NEW containers in Azure Cosmos DB.
If you have existing data, you'll need to migrate it.
"""

import os
import sys
from typing import Dict, List

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.cosmos_service import get_cosmos_client, get_cosmos_database
from azure.cosmos import PartitionKey, exceptions


def create_container_with_vector_index(
    database_name: str = "expert-answers-db",
    container_name: str = "questions",
    new_container_name: str = "questions_v2"  # Changed to v2 to be clear it's a new container
):
    """
    Create a new container with vector index policy.
    
    Args:
        database_name: Name of the database
        container_name: Name of existing container (for reference)
        new_container_name: Name for new container with vector index
    
    Returns:
        Container client for the new container
    """
    client = get_cosmos_client()
    database = client.get_database_client(database_name)
    
    # Vector embedding policy - REQUIRED for vector search to work!
    # This defines the vector field, its dimensions, and distance function
    vector_embedding_policy = {
        "vectorEmbeddings": [
            {
                "path": "/embedding",
                "dataType": "float32",
                "dimensions": 3072,  # text-embedding-3-large dimension
                "distanceFunction": "cosine"  # cosine, euclidean, or dotproduct
            }
        ]
    }
    
    # Vector index policy for indexing
    # Using quantizedFlat for 3072 dimensions (flat only supports up to 505)
    vector_index_policy = {
        "vectorIndexes": [
            {
                "path": "/embedding",
                "type": "quantizedFlat"  # quantizedFlat supports up to 4096 dimensions
            }
        ]
    }
    
    # Full text search policy - for BM25 search
    full_text_search_policy = {
        "defaultLanguage": "en-US",
        "fullTextPaths": [
            {
                "path": "/questionText",
                "language": "en-US"
            },
            {
                "path": "/topics",
                "language": "en-US"
            }
        ]
    }
    
    # Container indexing policy with vector index
    # According to Azure docs: vector paths should be excluded from regular indexing
    indexing_policy = {
        "indexingMode": "consistent",
        "automatic": True,
        "includedPaths": [
            {
                "path": "/*"
            }
        ],
        "excludedPaths": [
            {
                "path": "/\"_etag\"/?"
            },
            {
                "path": "/embedding/*"  # Exclude vector path from regular indexing (per Azure docs)
            }
        ],
        "vectorIndexes": vector_index_policy["vectorIndexes"]
    }
    
    try:
        # Create new container with BOTH vector embedding policy AND indexing policy
        # Note: Parameter name might vary by SDK version - if this fails, check Azure SDK docs
        container = database.create_container(
            id=new_container_name,
            partition_key=PartitionKey(path="/id"),
            indexing_policy=indexing_policy,
            vector_embedding_policy=vector_embedding_policy,  # ← CRITICAL: This was missing!
            full_text_search_policy=full_text_search_policy  # Full text search for BM25
        )
        print(f"✅ Created container '{new_container_name}' with:")
        print(f"   Vector embedding: {len(vector_embedding_policy['vectorEmbeddings'])} path(s)")
        print(f"   Vector indexes: {len(indexing_policy['vectorIndexes'])} index(es)")
        print(f"   Full text paths: {len(full_text_search_policy['fullTextPaths'])} path(s)")
        return container
    except TypeError as e:
        # Parameter name might be wrong - try alternative
        if "unexpected keyword argument" in str(e) or "vector_embedding_policy" in str(e):
            print(f"⚠️  Parameter name issue. Trying alternative format...")
            print(f"   Error: {e}")
            print(f"\n   Attempting to create container with vector embedding policy as container_properties...")
            # Try passing as part of container properties
            container_properties = {
                "id": new_container_name,
                "partitionKey": {"paths": ["/id"], "kind": "Hash"},
                "indexingPolicy": indexing_policy,
                "vectorEmbeddingPolicy": vector_embedding_policy  # Note: camelCase
            }
            container = database.create_container(**container_properties)
            print(f"✅ Created container '{new_container_name}' using alternative method")
            return container
        else:
            raise
    except exceptions.CosmosHttpResponseError as e:
        if e.status_code == 409:  # Container already exists
            print(f"⚠️  Container '{new_container_name}' already exists")
            return database.get_container_client(new_container_name)
        else:
            print(f"❌ Error creating container: {e}")
            print(f"   Status code: {e.status_code}")
            print(f"   Error message: {e.message}")
            raise


def migrate_data_to_vector_container(
    source_container_name: str = "questions",
    target_container_name: str = "questions_with_vector",
    database_name: str = "expert-answers-db"
):
    """
    Migrate data from old container to new container with vector index.
    
    Args:
        source_container_name: Name of source container
        target_container_name: Name of target container
        database_name: Name of database
    """
    client = get_cosmos_client()
    database = client.get_database_client(database_name)
    
    source_container = database.get_container_client(source_container_name)
    target_container = database.get_container_client(target_container_name)
    
    print(f"Migrating data from '{source_container_name}' to '{target_container_name}'...")
    
    # Get all items from source
    query = "SELECT * FROM c"
    items = list(source_container.query_items(
        query=query,
        enable_cross_partition_query=True
    ))
    
    print(f"Found {len(items)} items to migrate")
    
    # Copy items to target
    migrated = 0
    for item in items:
        try:
            target_container.create_item(body=item)
            migrated += 1
            if migrated % 100 == 0:
                print(f"  Migrated {migrated}/{len(items)} items...")
        except Exception as e:
            print(f"  Error migrating item {item.get('id')}: {e}")
    
    print(f"✅ Migration complete: {migrated}/{len(items)} items migrated")


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Set up vector index on Cosmos DB container"
    )
    parser.add_argument(
        "--new-container",
        type=str,
        default="questions_v2",
        help="Name for new container with vector index (default: questions_v2)"
    )
    parser.add_argument(
        "--migrate",
        action="store_true",
        help="Migrate data from existing 'questions' container to new container"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without actually doing it"
    )
    
    args = parser.parse_args()
    
    if args.dry_run:
        print("🔍 DRY RUN MODE\n")
        print(f"Would create container: {args.new_container}")
        print(f"Vector embedding policy: path=/embedding, dimensions=3072, dataType=float32, distanceFunction=cosine")
        print(f"Vector index: flat, path=/embedding")
        if args.migrate:
            print(f"Would migrate data from 'questions' to '{args.new_container}'")
        return
    
    try:
        # Create new container with vector index
        container = create_container_with_vector_index(
            new_container_name=args.new_container
        )
        
        # Migrate data if requested
        if args.migrate:
            migrate_data_to_vector_container(
                target_container_name=args.new_container
            )
        
        print("\n✅ Vector index setup complete!")
        print(f"\nNext steps:")
        print(f"1. Update COSMOS_CONTAINER_NAME in .env to: {args.new_container}")
        print(f"2. Update vector_search() in search_service.py to use VectorDistance()")
        print(f"3. Test vector search functionality")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
