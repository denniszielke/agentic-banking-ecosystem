---
name: human-in-the-loop-actions
description: Use when the customer wants to order a product, cancel a product, or update their contact details. Enforces mandatory human confirmation before any write operation.
---

# Schreibende Aktionen (Human-in-the-Loop)

Leite den Kunden durch eine Produktbestellung, Kündigung oder Kontaktdatenänderung.
Jede schreibende Aktion erfordert eine explizite Bestätigung des Kunden.

## Wann verwenden
- „Ich möchte ein Sparkonto eröffnen."
- „Bitte beantrage die VR-BankCard für mich."
- „Kündige mein Tagesgeldkonto."
- „Aktualisiere meine Telefonnummer / Adresse."

## Methode

### Schritt 1 — Berechtigung und Guardrails prüfen
Bevor eine Bestellung vorgeschlagen wird:
- Prüfe Eignung und Berechtigung (Alter, KYC-Status, Segment, Produktbedingungen).
- Zitiere die relevante Compliance-Regel (Datei + Abschnitt).
- Bei Unklarheit oder fehlendem Compliance-Entscheid: `ask_compliance` aufrufen (wenn verfügbar)
  oder an die persönliche Beratung verweisen — niemals raten.

### Schritt 2 — Vorschau erstellen
Rufe das Schreib-Tool mit `confirm=false` auf, um eine Vorschau der Änderung zu erhalten:
- `order_product` für ein neues Produkt
- `cancel_product` für eine Kündigung
- `update_customer` für Kontaktdatenänderungen

### Schritt 3 — Bestätigung einholen
1. Zeige die Vorschau dem Kunden: genau was sich ändern würde, welches Tool, welche Werte.
2. Stelle genau eine Rückfrage: „Soll ich das so ausführen? (ja/nein)"
3. Setze in der Sidebar `awaiting_confirmation=true` über `update_overview`.

### Schritt 4 — Ausführen
Nur nach eindeutiger Zustimmung (z. B. „ja", „bestätige", „mach das"):
- Rufe das Tool mit `confirm=true` auf.
- `order_product` legt einen Auftragsfall an (Status `requested`, Konto startet als `pending`).

### Schritt 5 — Nächste Schritte kommunizieren
- Bestätigung mit `order_id`, neuer Konto-ID und — bei Karte — Lieferdetails (Geschäftstage + Adresse).
- Sidebar auf `awaiting_confirmation=false` zurücksetzen.

## Ausgabeformat
- **Vorschau:** Produkt/Änderung mit Konditionen und Kosten.
- **Rückfrage:** „Soll ich das so ausführen?"
- **Nach Bestätigung:** Bestätigung, `order_id`, aktuelle Status.

## Guardrails
- Niemals `confirm=true` ohne ausdrückliches Kundenja.
- Niemals eine Eignungsregel umgehen. Wenn Compliance eine menschliche Entscheidung erfordert, Stop.
- Kein Vortäuschen eines abgeschlossenen Auftrags, solange der Status noch `requested` oder `pending` ist.
- Bei „nein", Unklarheit oder Änderungswunsch: Vorschlag anpassen und erneut fragen.
