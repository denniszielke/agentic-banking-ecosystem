# Recommender Agent

Der persönliche Banking-Assistent der Volksbank — ein **Foundry Hosted Agent**, der dem eingeloggten Kunden hilft, seine Finanzen zu verstehen und passende Produkte zu entdecken.

## Überblick

Der Recommender Agent ist der kundenorientierte Kanal der Volksbank. Er beantwortet Fragen zu Konten und Transaktionen, erklärt Produkte, berechnet Zinsen und empfiehlt proaktiv passende Angebote aus dem Volksbank-Portfolio und der genossenschaftlichen FinanzGruppe (Union Investment, R+V Versicherung, Bausparkasse Schwäbisch Hall, easyCredit/TeamBank).

### Architektur

```
Foundry Agent (RESPONSES protocol)
    └── recommender_agent.py  (ResponsesHostServer)
            ├── Fabric Data Agent  (Foundry project connection → Microsoft Fabric)
            │       └── Kontodaten, Transaktionen, Kundenprofil
            └── Finance MCP Server  (Foundry toolbox finance-tools oder direkter URL)
                    └── calculate_compound_interest, discount_cashflow
```

## Skills

| Skill | Beschreibung |
|---|---|
| `account-enquiry` | Kontostand, Transaktionen und Kundenprofil über den Fabric-Data-Agent |
| `product-recommendation` | Proaktive Empfehlungen aus dem Volksbank- / FinanzGruppe-Portfolio |
| `financial-calculation` | Zinsberechnungen und Barwertanalysen über die Finance-MCP-Tools |

## Lokale Entwicklung

```bash
# Aus dem Repository-Root
cp .env.example .env   # Pflichtfelder befüllen (s. u.)
python -m src.recommender_agent.recommender_agent
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
| `FINANCE_TOOLBOX_NAME` | `finance-tools` | Foundry-Toolbox-Name für Finance-MCP |
| `FINANCE_MCP_URL` | — | Direkter MCP-URL (überschreibt Toolbox, für lokale Entwicklung) |
| `PORT` | `8091` | Container-Port |

## Deployment als Foundry Hosted Agent

```bash
# Prerequisite: Finance-Toolbox registrieren
python -m scripts.register_finance_toolbox

# Agent deployen (baut Image in ACR und registriert den Hosted Agent)
python -m scripts.deploy_recommender_agent
```

Das Deploy-Skript:
1. Baut das Container-Image in ACR (`src/recommender_agent/Dockerfile`).
2. Registriert den Agenten als Foundry Hosted Agent (RESPONSES + A2A + INVOCATIONS).
3. Patcht die Agent Card mit den Skills aus `agentcard.json`.

Alle Variablen werden aus `.env` geladen (von `azd up` geschrieben).

### Deployment-Variablen

| Variable | Standard | Beschreibung |
|---|---|---|
| `AZURE_AI_RECOMMENDER_AGENT_NAME` | `recommender-agent` | Name des Hosted Agents |
| `AZURE_CONTAINER_REGISTRY_ENDPOINT` | (aus RG ermittelt) | ACR Login Server |
| `FABRIC_CONNECTION_ID` | — | Foundry-Verbindungs-ID (Pflicht) |
| `FINANCE_TOOLBOX_NAME` | `finance-tools` | Finance-MCP-Toolbox |
| `FINANCE_MCP_URL` | — | Direkter MCP-URL (optional) |

## Beispiel-Prompts

### Kontoinformationen

- „Wie hoch ist mein aktueller Kontostand?"
- „Zeig mir meine letzten 10 Transaktionen."
- „Wie viel habe ich diesen Monat für Lebensmittel ausgegeben?"
- „Gib mir einen Überblick über alle meine Konten und Karten."
- „Was waren meine größten Ausgaben im letzten Quartal?"

### Finanzberechnungen

- „Wenn ich 10.000 € bei 3,5 % Zinsen anlege – wie viel habe ich in 10 Jahren?"
- „Berechne den Barwert von 500 € monatlich über 15 Jahre bei einem Zinssatz von 4 %."
- „Was wäre mein Endkapital, wenn ich monatlich 200 € spare und 2,5 % p.a. erhalte?"

### Produktempfehlungen

- „Ich habe freie Liquidität auf meinem Konto – was empfiehlst du mir?"
- „Ich plane eine Reise nach Japan. Welche Produkte der Volksbank passen dazu?"
- „Welches Sparprodukt ist für mich am besten geeignet?"
- „Ich möchte ein neues Auto kaufen – welche Finanzierungsmöglichkeiten gibt es?"
- „Erkläre mir die Vorteile der Union Investment Fondsprodukte im Vergleich zum Tagesgeld."

## Nach jedem Re-Deployment: Conditional Access freischalten

Jedes Re-Deployment rotiert die **Entra Agent Identity** des Agents (neue Service-Principal-Objekt-ID).
Die CA-Policy **„High Risk Agents"** (`974ed75d-23d4-4f1f-af57-c1daf9998505`) blockiert standardmäßig alle Agent Identities.
Die neue ID muss nach jedem Deployment in die Ausnahmeliste eingetragen werden, sonst schlägt jeder API-Aufruf mit `AADSTS53003` fehl.

```bash
# 1. Neue Agent Identity Object-ID ermitteln
az rest --method GET \
  --uri "https://graph.microsoft.com/beta/servicePrincipals/microsoft.graph.agentIdentity?\$select=id,displayName" \
  --query "value[?contains(displayName, 'recommender')]" -o json

# 2. Aktuelle Ausnahmeliste lesen
az rest --method GET \
  --uri "https://graph.microsoft.com/beta/identity/conditionalAccess/policies/974ed75d-23d4-4f1f-af57-c1daf9998505" \
  --query "conditions.clientApplications.excludeAgentIdServicePrincipals" -o json

# 3. CA-Policy mit der neuen ID patchen (alle bisherigen IDs + neue ID)
az rest --method PATCH \
  --uri "https://graph.microsoft.com/beta/identity/conditionalAccess/policies/974ed75d-23d4-4f1f-af57-c1daf9998505" \
  --headers "Content-Type=application/json" \
  --body '{
    "conditions": {
      "clientApplications": {
        "excludeAgentIdServicePrincipals": ["<id1>", "<id2>", "...", "<neue-id>"]
      }
    }
  }'
```

> **Symptom bei fehlender Ausnahme:** Der Agent startet, aber jeder Request schlägt mit HTTP 500 fehl.
> Die Logs zeigen `ManagedIdentityCredential: (bad_request) ... AADSTS53003`.
> Die Änderung propagiert nach ca. 2–5 Minuten; kein Redeploy erforderlich.
