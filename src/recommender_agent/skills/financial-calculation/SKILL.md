---
name: financial-calculation
description: Use when the customer asks about savings growth, interest earned, or the present value of future cash flows. Uses the finance MCP tools for accurate calculations.
---

# Finanzberechnungen (Zins und Barwert)

Führe Zinsberechnungen und Barwertanalysen für den Kunden durch — immer auf Basis
der Finance-Tools, nicht manuell gerechnet.

## Wann verwenden
- „Was ergibt sich, wenn ich X € bei Y % p. a. über Z Jahre anlege?"
- „Wie viel Zinsen erhalte ich auf meinem Tagesgeld?"
- „Was ist der heutige Wert von X €, die ich in 10 Jahren erhalte?"
- „Wie viel muss ich monatlich sparen, um in N Jahren Y € zu haben?"

## Verfügbare Tools
| Tool | Zweck |
|---|---|
| `calculate_compound_interest` | Endkapital und Zinsergebnis bei Zinseszins |
| `discount_cashflow` | Barwert einer zukünftigen Zahlung |

Alle Zinssätze als Jahresprozentsatz übergeben (z. B. 3.5 für 3,5 % p. a.).

## Methode
1. **Parameter aus dem Gespräch extrahieren.** Betrag, Zinssatz, Laufzeit und
   Zinsperiode (jährlich = Standard).
2. **Tool aufrufen.** Immer `calculate_compound_interest` oder `discount_cashflow`
   verwenden — nie manuell rechnen.
3. **Ergebnis verständlich aufbereiten.** Startkapital, Endkapital, erzielte Zinsen
   und Gesamtrendite in Prozent als kurze Tabelle oder Fließtext.
4. **Produktbezug herstellen** (optional). Wenn der Satz aus einem echten Produkt stammt,
   zitiere Produkt und Quelle. Wenn nicht, weise darauf hin, dass der Satz ein Beispiel ist.

## Ausgabeformat
```
Anlage: €15.000 | Zinssatz: 3,5 % p. a. | Laufzeit: 5 Jahre
Endkapital: €17.748,97 | Zinsen: €2.748,97 | Gesamtrendite: 18,33 %
```

## Guardrails
- Nie Zinssätze erfinden — nur Sätze aus Produktdaten oder vom Kunden genannte Werte verwenden.
- Keine steuerliche Beratung (Abgeltungsteuer, Freistellungsauftrag) — nur auf die
  persönliche Beratung hinweisen.
