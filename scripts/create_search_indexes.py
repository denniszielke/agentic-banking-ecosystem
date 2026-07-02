"""Create (or update) the two banking Azure AI Search indexes.

Defined in ``narrative.md``:

  1. **Financial products** (``banking-products``) — product name, description,
     bank id, category, product code, tags and a ``description_vector`` for
     vector search over product descriptions.

  2. **Compliance rules** (``banking-compliance``) — rule name, description,
     scenario, regulatory domain, tags, a ``description_vector`` and a
     ``scenario_vector`` for vector search over both descriptions and scenarios.

Both indexes are created with HNSW vector search and a semantic configuration so
the agents can run vector, semantic or hybrid queries. Populate them afterwards
with ``python -m scripts.ingest_knowledge``.

Environment variables:
  AZURE_SEARCH_ENDPOINT                 e.g. https://<service>.search.windows.net (required)
  AZURE_SEARCH_ADMIN_KEY                admin key; falls back to DefaultAzureCredential
  AZURE_SEARCH_PRODUCT_INDEX_NAME       default: banking-products
  AZURE_SEARCH_COMPLIANCE_INDEX_NAME    default: banking-compliance
  AZURE_OPENAI_EMBEDDING_DIMENSIONS     embedding vector size (default: 1536)
"""

from __future__ import annotations

import os

from azure.core.credentials import AzureKeyCredential
from azure.identity import DefaultAzureCredential
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    HnswAlgorithmConfiguration,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SemanticConfiguration,
    SemanticField,
    SemanticPrioritizedFields,
    SemanticSearch,
    VectorSearch,
    VectorSearchProfile,
)
from dotenv import load_dotenv

load_dotenv(override=True)

EMBEDDING_DIMENSIONS = int(os.getenv("AZURE_OPENAI_EMBEDDING_DIMENSIONS", "1536"))

PRODUCT_INDEX_NAME = os.getenv("AZURE_SEARCH_PRODUCT_INDEX_NAME", "banking-products")
COMPLIANCE_INDEX_NAME = os.getenv("AZURE_SEARCH_COMPLIANCE_INDEX_NAME", "banking-compliance")


def _get_index_client() -> SearchIndexClient:
    endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
    if not endpoint:
        raise RuntimeError("AZURE_SEARCH_ENDPOINT is required")
    api_key = os.getenv("AZURE_SEARCH_ADMIN_KEY", "").strip()
    credential = AzureKeyCredential(api_key) if api_key else DefaultAzureCredential()
    return SearchIndexClient(endpoint=endpoint, credential=credential)


def _vector_search() -> VectorSearch:
    return VectorSearch(
        profiles=[VectorSearchProfile(name="hnsw", algorithm_configuration_name="hnsw")],
        algorithms=[HnswAlgorithmConfiguration(name="hnsw")],
    )


def _vector_field(name: str) -> SearchField:
    return SearchField(
        name=name,
        type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
        searchable=True,
        vector_search_dimensions=EMBEDDING_DIMENSIONS,
        vector_search_profile_name="hnsw",
    )


def _product_fields() -> list[SearchField]:
    """Financial products index fields."""
    return [
        SearchField(name="id", type=SearchFieldDataType.String, key=True),
        SearchField(name="name", type=SearchFieldDataType.String, searchable=True, filterable=True),
        SearchField(name="description", type=SearchFieldDataType.String, searchable=True),
        SearchField(name="bank_id", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SearchField(name="category", type=SearchFieldDataType.String, searchable=True, filterable=True, facetable=True),
        SearchField(name="product_code", type=SearchFieldDataType.String, filterable=True),
        SearchField(
            name="tags",
            type=SearchFieldDataType.Collection(SearchFieldDataType.String),
            searchable=True, filterable=True, facetable=True,
        ),
        SearchField(name="source_ref", type=SearchFieldDataType.String, searchable=True, filterable=True),
        _vector_field("description_vector"),
    ]


def _compliance_fields() -> list[SearchField]:
    """Compliance rules index fields."""
    return [
        SearchField(name="id", type=SearchFieldDataType.String, key=True),
        SearchField(name="name", type=SearchFieldDataType.String, searchable=True, filterable=True),
        SearchField(name="description", type=SearchFieldDataType.String, searchable=True),
        SearchField(name="scenario", type=SearchFieldDataType.String, searchable=True),
        SearchField(name="domain", type=SearchFieldDataType.String, searchable=True, filterable=True, facetable=True),
        SearchField(
            name="tags",
            type=SearchFieldDataType.Collection(SearchFieldDataType.String),
            searchable=True, filterable=True, facetable=True,
        ),
        SearchField(name="source_ref", type=SearchFieldDataType.String, searchable=True, filterable=True),
        _vector_field("description_vector"),
        _vector_field("scenario_vector"),
    ]


def _semantic(config_name: str, content_fields: list[str], keyword_fields: list[str]) -> SemanticSearch:
    return SemanticSearch(
        default_configuration_name=config_name,
        configurations=[
            SemanticConfiguration(
                name=config_name,
                prioritized_fields=SemanticPrioritizedFields(
                    title_field=SemanticField(field_name="name"),
                    content_fields=[SemanticField(field_name=f) for f in content_fields],
                    keywords_fields=[SemanticField(field_name=f) for f in keyword_fields],
                ),
            )
        ],
    )


def create_or_update_indexes() -> None:
    client = _get_index_client()

    product_index = SearchIndex(
        name=PRODUCT_INDEX_NAME,
        fields=_product_fields(),
        vector_search=_vector_search(),
        semantic_search=_semantic("product-semantic", ["description"], ["tags"]),
    )
    result = client.create_or_update_index(product_index)
    print(f"Index '{result.name}' created/updated.")

    compliance_index = SearchIndex(
        name=COMPLIANCE_INDEX_NAME,
        fields=_compliance_fields(),
        vector_search=_vector_search(),
        semantic_search=_semantic("compliance-semantic", ["description", "scenario"], ["tags"]),
    )
    result = client.create_or_update_index(compliance_index)
    print(f"Index '{result.name}' created/updated.")


if __name__ == "__main__":
    create_or_update_indexes()
