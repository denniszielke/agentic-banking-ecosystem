"""Ingest the banking knowledge base into the two Azure AI Search indexes.

Parses the hand-authored markdown under ``data/`` into search documents,
optionally embeds the text with Azure OpenAI, and uploads them:

  * **Financial products** (``banking-products``) — every product section of
    ``data/knowledge/savings-products.md``,
    ``data/knowledge/childrens-savings-products.md`` and
    ``data/knowledge/credit-card-products.md``, plus the catalogue rows in
    ``data/products.md``.

  * **Compliance rules** (``banking-compliance``) — every ``## N.M`` section of
    ``data/knowledge/compliance-regulatory.md``, tagged by regulatory domain.

Every document carries a ``source_ref`` (``file §N.M``) so agents can cite it.
Run ``python -m scripts.create_search_indexes`` first to create the schemas.

Embeddings are optional: if ``AZURE_OPENAI_ENDPOINT`` and the embedding
deployment are configured, ``description_vector`` (and ``scenario_vector`` for
compliance) are populated; otherwise the documents are pushed without vectors
and text/semantic search still works.

Environment variables:
  AZURE_SEARCH_ENDPOINT                   required
  AZURE_SEARCH_ADMIN_KEY                  admin key; falls back to DefaultAzureCredential
  AZURE_SEARCH_PRODUCT_INDEX_NAME         default: banking-products
  AZURE_SEARCH_COMPLIANCE_INDEX_NAME      default: banking-compliance
  AZURE_OPENAI_ENDPOINT                   Azure OpenAI endpoint for embeddings (optional)
  AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME  default: text-embedding-3-small
  OPENAI_API_VERSION                      default: 2024-05-01-preview
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Optional

from azure.core.credentials import AzureKeyCredential
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from azure.search.documents import SearchClient
from dotenv import load_dotenv

load_dotenv(override=True)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DATA_DIR = _REPO_ROOT / "data"
_KNOWLEDGE_DIR = _DATA_DIR / "knowledge"

PRODUCT_INDEX_NAME = os.getenv("AZURE_SEARCH_PRODUCT_INDEX_NAME", "banking-products")
COMPLIANCE_INDEX_NAME = os.getenv("AZURE_SEARCH_COMPLIANCE_INDEX_NAME", "banking-compliance")

# filename -> (category, tags)
_PRODUCT_FILES = {
    "savings-products.md": "savings",
    "childrens-savings-products.md": "childrens_savings",
    "credit-card-products.md": "credit_card",
}

# Regulatory domain keyword map for tagging compliance rules.
_DOMAIN_KEYWORDS = {
    "KYC": ["kyc", "identity", "verification", "verify", "identification"],
    "AML": ["aml", "money laundering", "suspicious", "monitoring", "source of funds"],
    "CTF": ["terrorist", "ctf", "financing"],
    "Sanctions": ["sanction", "pep", "politically exposed", "screening"],
    "Fraud Prevention": ["fraud", "scam", "abuse"],
    "Consumer Protection": ["consumer", "protection", "vulnerable", "disclosure"],
    "Credit Risk": ["credit", "card", "limit", "assessment", "lending", "eligibility"],
    "Data Privacy": ["privacy", "personal data", "gdpr", "retention"],
    "Beneficial Ownership": ["beneficial", "ownership", "ultimate owner"],
    "Auditability": ["audit", "evidence", "record", "log"],
}


# ---------------------------------------------------------------------------
# Markdown parsing
# ---------------------------------------------------------------------------

def _slug(text: str) -> str:
    return re.sub(r"[^0-9a-zA-Z]+", "-", text).strip("-").lower()


def _parse_sections(md_text: str) -> list[dict[str, str]]:
    """Split markdown into ``## N.M`` sections, tracking the parent ``# N`` heading.

    Returns dicts with: number, title, body, h1_number, h1_title.
    """
    lines = md_text.splitlines()
    sections: list[dict[str, str]] = []
    h1_number = h1_title = ""
    current: Optional[dict[str, Any]] = None
    body: list[str] = []

    h1_re = re.compile(r"^#\s+(\d+(?:\.\d+)*)\.?\s*(.*)$")
    h2_re = re.compile(r"^##\s+(\d+(?:\.\d+)*)\.?\s*(.*)$")

    def _flush() -> None:
        if current is not None:
            current["body"] = "\n".join(body).strip()
            sections.append(current)  # type: ignore[arg-type]

    for line in lines:
        h1 = h1_re.match(line)
        h2 = h2_re.match(line)
        if h1:
            _flush()
            current = None
            body = []
            h1_number, h1_title = h1.group(1), h1.group(2).strip()
            continue
        if h2:
            _flush()
            body = []
            current = {
                "number": h2.group(1),
                "title": h2.group(2).strip(),
                "h1_number": h1_number,
                "h1_title": h1_title,
            }
            continue
        if current is not None:
            body.append(line)
    _flush()
    return sections


# ---------------------------------------------------------------------------
# Document builders
# ---------------------------------------------------------------------------

def _build_product_docs() -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []

    for filename, category in _PRODUCT_FILES.items():
        path = _KNOWLEDGE_DIR / filename
        if not path.exists():
            continue
        for sec in _parse_sections(path.read_text(encoding="utf-8")):
            title, number, body = sec["title"], sec["number"], sec["body"]
            if not body:
                continue
            description = f"{title}\n\n{body}".strip()
            docs.append({
                "id": f"prod-{_slug(filename.removesuffix('.md'))}-{number.replace('.', '-')}",
                "name": title or f"{filename} §{number}",
                "description": description,
                "bank_id": "all",
                "category": category,
                "product_code": "",
                "tags": [category, *[t for t in [title.split()[0].lower()] if t]],
                "source_ref": f"{filename} §{number}",
            })

    # Catalogue rows (covers products without a dedicated knowledge file, e.g.
    # the current account) parsed from data/products.md.
    catalogue = _DATA_DIR / "products.md"
    if catalogue.exists():
        for code, name, cat, desc, ref in _parse_catalogue(catalogue.read_text(encoding="utf-8")):
            docs.append({
                "id": f"prod-catalogue-{_slug(code)}",
                "name": name,
                "description": desc,
                "bank_id": "all",
                "category": cat,
                "product_code": code,
                "tags": [cat, name.lower()],
                "source_ref": ref,
            })
    return docs


def _parse_catalogue(md_text: str) -> list[tuple[str, str, str, str, str]]:
    """Extract catalogue rows from the products.md markdown table."""
    rows: list[tuple[str, str, str, str, str]] = []
    for line in md_text.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 6:
            continue
        code = cells[0]
        if not re.match(r"^[A-Z]+$", code):  # skip header / non-code rows
            continue
        name, category = cells[1], cells[2]
        desc = f"{name} — {category.replace('_', ' ')} product from the bank catalogue."
        rows.append((code, name, category, desc, "products.md §1.2"))
    return rows


def _domain_for(text: str) -> tuple[str, list[str]]:
    """Return the best-matching regulatory domain and the matched domain tags."""
    lowered = text.lower()
    matched = [d for d, kws in _DOMAIN_KEYWORDS.items() if any(k in lowered for k in kws)]
    primary = matched[0] if matched else "General"
    return primary, matched or ["General"]


def _build_compliance_docs() -> list[dict[str, Any]]:
    path = _KNOWLEDGE_DIR / "compliance-regulatory.md"
    if not path.exists():
        return []
    docs: list[dict[str, Any]] = []
    for sec in _parse_sections(path.read_text(encoding="utf-8")):
        title, number, body = sec["title"], sec["number"], sec["body"]
        if not body:
            continue
        scenario = f"{sec['h1_title']}: {title}".strip(": ")
        description = f"{title}\n\n{body}".strip()
        domain, tags = _domain_for(f"{title} {body} {sec['h1_title']}")
        docs.append({
            "id": f"comp-{number.replace('.', '-')}",
            "name": title or f"compliance §{number}",
            "description": description,
            "scenario": scenario,
            "domain": domain,
            "tags": tags,
            "source_ref": f"compliance-regulatory.md §{number}",
        })
    return docs


# ---------------------------------------------------------------------------
# Embeddings (optional)
# ---------------------------------------------------------------------------

class _Embedder:
    """Thin Azure OpenAI embedding wrapper; disabled if not configured."""

    def __init__(self) -> None:
        self._client = None
        self._model = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME", "text-embedding-3-small")
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "").strip()
        if not endpoint:
            print("No AZURE_OPENAI_ENDPOINT — uploading without vectors.")
            return
        try:
            from openai import AzureOpenAI
        except ImportError:
            print("openai package not installed — uploading without vectors.")
            return
        api_key = os.getenv("AZURE_OPENAI_API_KEY", "").strip()
        api_version = os.getenv("OPENAI_API_VERSION", "2024-05-01-preview")
        if api_key:
            self._client = AzureOpenAI(azure_endpoint=endpoint, api_key=api_key, api_version=api_version)
        else:
            token_provider = get_bearer_token_provider(
                DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
            )
            self._client = AzureOpenAI(
                azure_endpoint=endpoint,
                azure_ad_token_provider=token_provider,
                api_version=api_version,
            )

    @property
    def enabled(self) -> bool:
        return self._client is not None

    def embed(self, texts: list[str]) -> list[list[float]]:
        if self._client is None:
            return [[] for _ in texts]
        # Azure OpenAI embeddings accept batches; keep them modest.
        vectors: list[list[float]] = []
        for i in range(0, len(texts), 16):
            batch = [t[:8000] for t in texts[i : i + 16]]
            resp = self._client.embeddings.create(model=self._model, input=batch)
            vectors.extend([d.embedding for d in resp.data])
        return vectors


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------

def _search_client(index_name: str) -> SearchClient:
    endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
    if not endpoint:
        raise RuntimeError("AZURE_SEARCH_ENDPOINT is required")
    api_key = os.getenv("AZURE_SEARCH_ADMIN_KEY", "").strip()
    credential = AzureKeyCredential(api_key) if api_key else DefaultAzureCredential()
    return SearchClient(endpoint=endpoint, index_name=index_name, credential=credential)


def _upload(index_name: str, docs: list[dict[str, Any]]) -> None:
    if not docs:
        print(f"No documents to upload to '{index_name}'.")
        return
    client = _search_client(index_name)
    for i in range(0, len(docs), 500):
        batch = docs[i : i + 500]
        client.upload_documents(documents=batch)
    print(f"Uploaded {len(docs)} documents to '{index_name}'.")


def ingest() -> None:
    embedder = _Embedder()

    product_docs = _build_product_docs()
    if embedder.enabled and product_docs:
        vectors = embedder.embed([d["description"] for d in product_docs])
        for doc, vec in zip(product_docs, vectors):
            if vec:
                doc["description_vector"] = vec
    _upload(PRODUCT_INDEX_NAME, product_docs)

    compliance_docs = _build_compliance_docs()
    if embedder.enabled and compliance_docs:
        desc_vecs = embedder.embed([d["description"] for d in compliance_docs])
        scen_vecs = embedder.embed([d["scenario"] for d in compliance_docs])
        for doc, dvec, svec in zip(compliance_docs, desc_vecs, scen_vecs):
            if dvec:
                doc["description_vector"] = dvec
            if svec:
                doc["scenario_vector"] = svec
    _upload(COMPLIANCE_INDEX_NAME, compliance_docs)


if __name__ == "__main__":
    ingest()
