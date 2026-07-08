---
name: account-enquiry
description: Use when the customer asks about their balance, transactions, or personal details. Produces a grounded, confidential answer from the Fabric data agent.
---

# Kontoinformationen abrufen

Beantworte Fragen des Kunden zu seinen eigenen Konten, Salden und Transaktionen —
ausschließlich für den eingeloggten Kunden.

## Wann verwenden
- „Wie hoch ist mein Kontostand?"
- „Was ist mein Gesamtvermögen über alle Konten?"
- „Was habe ich letzten Monat ausgegeben / in welche Kategorien?"
- „Zeig mir meine Transaktionen vom [Datum] bis [Datum]."
- „Was sind meine Kontaktdaten?"

## Methode
1. **Kunden im Kontext identifizieren.** Verwende die Kunden-ID aus dem Gespräch.
   Frage niemals nach fremden Kundendaten oder gib diese preis.
2. **Daten abrufen.** Nutze den Fabric-Data-Agent:
   - Salden und Konto-Details für einzelne Konten.
   - Gesamtübersicht über alle Konten für „alle meine Konten" / „Gesamtvermögen"-Fragen.
   - Ausgabenanalyse (nach Kategorie, Händler, größte Transaktion) für Ausgabenfragen.
   - Kontoliste und Kundenprofil für Profilfragen.
   - Transaktionsliste mit Datumsfilter, wenn der Kunde die Rohbewegungen sehen möchte.
3. **Verständlich aufbereiten.** Beträge in EUR, nach Datum gruppiert, mit laufendem
   Saldo wo sinnvoll. Ausgabenfragen: zuerst die Gesamtsumme, dann die größten Posten.
4. **Sidebar aktualisieren.** `update_overview` mit Kundenprofil und aktuellen Konten
   aufrufen, bevor die Chat-Antwort geschrieben wird.

## Ausgabeformat
Direkte Antwort voranstellen (z. B. der Saldo), dann ggf. eine kompakte Tabelle
(Datum, Beschreibung, Kategorie, Betrag, Saldo danach).

## Guardrails
- Nur die Daten des eingeloggten Kunden — niemals die eines anderen.
- Hier keine Schreiboperationen — nur Lesezugriff. Kontaktdatenänderungen laufen
  über den Bestätigungsfluss.
