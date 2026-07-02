"""Delete the two banking Azure AI Search indexes (schema + data).

Removes ``banking-products`` and ``banking-compliance`` entirely. To clear only
the documents but keep the schemas, re-run ``python -m scripts.create_search_indexes``
after deleting, or delete and recreate.

Environment variables:
  AZURE_SEARCH_ENDPOINT                 required
  AZURE_SEARCH_ADMIN_KEY                admin key; falls back to DefaultAzureCredential
  AZURE_SEARCH_PRODUCT_INDEX_NAME       default: banking-products
  AZURE_SEARCH_COMPLIANCE_INDEX_NAME    default: banking-compliance
"""

from __future__ import annotations

import os

from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import ResourceNotFoundError
from azure.identity import DefaultAzureCredential
from azure.search.documents.indexes import SearchIndexClient
from dotenv import load_dotenv

load_dotenv(override=True)

INDEXES = [
    os.getenv("AZURE_SEARCH_PRODUCT_INDEX_NAME", "banking-products"),
    os.getenv("AZURE_SEARCH_COMPLIANCE_INDEX_NAME", "banking-compliance"),
]


def _get_index_client() -> SearchIndexClient:
    endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
    if not endpoint:
        raise RuntimeError("AZURE_SEARCH_ENDPOINT is required")
    api_key = os.getenv("AZURE_SEARCH_ADMIN_KEY", "").strip()
    credential = AzureKeyCredential(api_key) if api_key else DefaultAzureCredential()
    return SearchIndexClient(endpoint=endpoint, credential=credential)


def delete_indexes() -> None:
    client = _get_index_client()
    for name in INDEXES:
        try:
            client.delete_index(name)
            print(f"Deleted index '{name}'.")
        except ResourceNotFoundError:
            print(f"Index '{name}' does not exist — skipping.")


if __name__ == "__main__":
    delete_indexes()
