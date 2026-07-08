# Recommender Agent

Der persönliche Banking-Assistent der Volksbank — ein Foundry hosted agent, der dem eingeloggten Kunden hilft, seine Finanzen zu verstehen, passende Produkte zu entdecken und Aktionen mit expliziter Bestätigung durchzuführen.

## Überblick

Der Recommender Agent antwortet auf Fragen zu Konten und Transaktionen, erklärt und empfiehlt proaktiv Angebote aus dem Volksbank-Portfolio und der genossenschaftlichen FinanzGruppe (Union Investment, R+V Versicherung, Bausparkasse Schwäbisch Hall, easyCredit/TeamBank) und führt Zinsberechnungen durch.

### Architektur

```
Foundry RESPONSES / A2A / INVOCATIONS
    └── agent.py  (ResponsesHostServer)
            ├── Fabric Data Agent  (Foundry project connection → Microsoft Fabric)
            │       └── Kontodaten, Transaktionen, Kundenprofil
            └── Finance MCP Server  (Foundry toolbox oder direkter URL)
                    └── calculate_compound_interest, discount_cashflow
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
python -m src.recommender_agent.agent
```

### Pflicht-Umgebungsvariablen

| Variable | Beschreibung |
|---|---|
| `AZURE_AI_PROJECT_ENDPOINT` | Foundry-Projektendpunkt |
| `FABRIC_CONNECTION_ID` | Foundry-Verbindungs-ID für den Fabric-Data-Agent |

### Optionale Konfiguration

| Variable | Standard | Beschreibung |
|---|---|---|
| `AZURE_OPENAI_CHAT_DEPLOYMENT_NAME` | `gpt-4.1-mini` | Chat-Modell |
| `AZURE_AI_MODEL_DEPLOYMENT_NAME` | `gpt-4.1-mini` | Fallback-Modell |
| `FINANCE_TOOLBOX_NAME` | `finance-tools` | Foundry-Toolbox-Name für Finance-MCP |
| `FINANCE_MCP_URL` | — | Direkter MCP-URL (überschreibt Toolbox, für lokale Entwicklung) |
| `PORT` | `8091` | Host-Port |

## Deployment als Foundry hosted agent

```bash
# Finance-Toolbox zuerst registrieren (falls noch nicht geschehen)
python -m scripts.register_finance_toolbox

# Agent deployen
python -m scripts.deploy_recommender_agent
```

Das Deploy-Skript baut das Container-Image in ACR und registriert den Agent als
Foundry hosted agent (RESPONSES + A2A + INVOCATIONS Protokolle).

### Deploy-Variablen

| Variable | Standard | Beschreibung |
|---|---|---|
| `AZURE_AI_RECOMMENDER_AGENT_NAME` | `recommender-agent` | Name des hosted agents |
| `AZURE_CONTAINER_REGISTRY_ENDPOINT` | — | ACR Login-Server (required) |
| `FINANCE_TOOLBOX_NAME` | `finance-tools` | Toolbox-Name im hosted agent |
| `FINANCE_MCP_URL` | — | Direkter MCP-URL Override |

## Human-in-the-Loop

Alle schreibenden Aktionen (Produktbestellung, Kündigung, Kontaktdatenänderung)
sind **verbindlich menschlich bestätigt**:

1. Der Agent legt die geplante Aktion offen (Tool, Parameter, Werte).
2. Er fragt genau einmal: „Soll ich das so ausführen? (ja/nein)"
3. Das Tool wird erst nach ausdrücklicher Zustimmung aufgerufen.
4. Bei „nein" oder Unklarheit: Vorschlag anpassen, erneut fragen.

Lesende Aktionen (Kontostand, Transaktionen) benötigen keine Bestätigung.
