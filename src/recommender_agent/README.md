# Recommender Agent

Der persönliche Banking-Assistent der Volksbank — ein AG-UI-Webagent, der dem eingeloggten Kunden hilft, seine Finanzen zu verstehen, passende Produkte zu entdecken und Aktionen mit expliziter Bestätigung durchzuführen.

## Überblick

Der Recommender Agent ist der kundenorientierte Kanal der Volksbank. Er beantwortet Fragen zu Konten und Transaktionen, erklärt Produkte, berechnet Zinsen und empfiehlt proaktiv passende Angebote aus dem Volksbank-Portfolio und der genossenschaftlichen FinanzGruppe (Union Investment, R+V Versicherung, Bausparkasse Schwäbisch Hall, easyCredit/TeamBank).

### Architektur

```
Browser (AG-UI SSE)
    └── server.py  (FastAPI / AG-UI)
            ├── Fabric Data Agent  (Foundry project connection → Microsoft Fabric)
            │       └── Kontodaten, Transaktionen, Kundenprofil
            ├── Finance MCP Server  (Foundry toolbox oder direkter URL)
            │       └── calculate_compound_interest, discount_cashflow
            ├── Financial Products Index  (Azure AI Search — Kontext-Provider)
            │       └── Produktkatalog, Konditionen, Zinsprodukte
            └── Compliance Agent (A2A, optional)
                    └── Regulatorische Fragen über Bank North
```

## Skills

| Skill | Beschreibung |
|---|---|
| `account-enquiry` | Kontostand, Transaktionen und Kundenprofil über den Fabric-Data-Agent |
| `product-recommendation` | Proaktive Empfehlungen aus dem Volksbank- / FinanzGruppe-Portfolio |
| `financial-calculation` | Zinsberechnungen und Barwertanalysen über die Finance-MCP-Tools |
| `human-in-the-loop-actions` | Produktbestellung, Kündigung und Kontaktdatenänderung mit verbindlicher Bestätigung |

## Lokale Entwicklung

```bash
# Aus dem Repository-Root
cp .env.example .env   # Pflichtfelder befüllen (s. u.)
python -m src.recommender_agent.server
```

Der Server startet auf `http://localhost:8091`. Die Chat-UI ist unter `/` erreichbar.

### Pflicht-Umgebungsvariablen

| Variable | Beschreibung |
|---|---|
| `AZURE_AI_PROJECT_ENDPOINT` | Foundry-Projektendpunkt |
| `AZURE_SEARCH_ENDPOINT` | Azure AI Search-Endpunkt |
| `FABRIC_CONNECTION_ID` | Foundry-Verbindungs-ID für den Fabric-Data-Agent |

### Optionale Konfiguration

| Variable | Standard | Beschreibung |
|---|---|---|
| `AZURE_OPENAI_CHAT_DEPLOYMENT_NAME` | `gpt-4.1-mini` | Chat-Modell |
| `AZURE_OPENAI_ENDPOINT` | — | Azure OpenAI-Endpunkt (für Embedding-Hybridsuche) |
| `AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME` | — | Embedding-Modell |
| `AZURE_SEARCH_ADMIN_KEY` | — | API-Key für AI Search (alternativ: Entra ID) |
| `AZURE_SEARCH_PRODUCT_INDEX_NAME` | `banking-products` | Produktkatalog-Index |
| `FINANCE_TOOLBOX_NAME` | `finance-tools` | Foundry-Toolbox-Name für Finance-MCP |
| `FINANCE_MCP_URL` | — | Direkter MCP-URL (überschreibt Toolbox, für lokale Entwicklung) |
| `COMPLIANCE_A2A_ENABLED` | `false` | Compliance-Agent über A2A einbinden |
| `AZURE_AI_COMPLIANCE_AGENT_NAME` | `compliance-agent` | Name des Compliance-Hosted-Agents |
| `COMPLIANCE_AGENT_A2A_URL` | (auto) | Direkter A2A-Endpunkt (wird sonst aus Projektendpunkt abgeleitet) |
| `COMPLIANCE_AGENT_AUDIENCE` | `https://ai.azure.com` | Entra-Audience für A2A-Bearer-Token |
| `HOST` | `0.0.0.0` | Bind-Adresse |
| `PORT` | `8091` | Container-Port |

## Deployment auf Azure Container Apps

```bash
# Image in ACR bauen und dann deployen
python -m scripts.deploy_recommender_agent --build

# Nur deployen — Image bereits in ACR (nutzt :latest oder TAG)
python -m scripts.deploy_recommender_agent
```

Das Deploy-Skript:
1. Baut das Container-Image in ACR (`src/recommender_agent/Dockerfile`).
2. Weist der Managed Identity die notwendigen RBAC-Rollen zu
   (Cognitive Services User, Search Index Data Reader, Monitoring Metrics Publisher).
3. Deployt die Container App via `infra/core/host/app.bicep`.
4. Gibt die öffentliche URL aus.

Alle Variablen werden aus `.env` geladen (von `azd up` geschrieben).

### Wichtige Deployment-Variablen

| Variable | Standard | Beschreibung |
|---|---|---|
| `RECOMMENDER_AGENT_APP_NAME` | `recommender-agent` | Name der Container App |
| `RECOMMENDER_AGENT_PORT` | `8091` | Containerport |
| `RECOMMENDER_AGENT_EXTERNAL` | `true` | Öffentlicher Ingress |
| `TAG` | `latest` | Image-Tag |

## Agent im Foundry-Projekt veröffentlichen

Nach dem Deployment kann der Agent im Foundry-Projektkatalog registriert werden:

```bash
python -m scripts.publish_recommender_agent
```

Das Skript liest `src/recommender_agent/agentcard.json` und registriert den Agenten
(inkl. Skills und öffentlicher URL) im Foundry-Projekt.

## Human-in-the-Loop

Alle schreibenden Aktionen (Produktbestellung, Kündigung, Kontaktdatenänderung)
sind **verbindlich menschlich bestätigt**:

1. Der Agent legt die geplante Aktion offen (Tool, Parameter, Werte).
2. Er fragt genau einmal: „Soll ich das so ausführen? (ja/nein)"
3. Das Tool wird erst nach ausdrücklicher Zustimmung aufgerufen.
4. Bei „nein" oder Unklarheit: Vorschlag anpassen, erneut fragen.

Lesende Aktionen (Kontostand, Transaktionen, Produkte) benötigen keine Bestätigung.
