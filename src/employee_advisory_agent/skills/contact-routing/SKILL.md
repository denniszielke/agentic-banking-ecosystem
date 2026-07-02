---
name: contact-routing
description: Use when an employee needs the best internal contact or branch for a product, or wants to schedule a customer follow-up. Routes to the right branch specialist and uses WorkIQ for scheduling.
---

# Contact Routing & Follow-up Skill

Find the right internal contact for a product or topic, and help the employee
schedule the follow-up in their own calendar.

## When to use
- "Who is the specialist for business lending in the North branch?"
- "Where is the nearest branch that handles children's savings?"
- "Book a follow-up with this customer next week about the credit card."

## Method
1. **Resolve the routing.** Use `search_financial_products` and the branch
   directory grounding (bank-north.md / bank-south.md) to identify the branch,
   department or specialist that owns the product or topic. Cite the file and
   numbered section.
2. **Confirm availability.** For scheduling, use the WorkIQ tools to read the
   employee's calendar and propose a concrete free slot.
3. **Create the follow-up** only when the employee explicitly asks: draft the
   calendar item (title, time, attendees), confirm it, then summarise what was
   created.

## Output format
- **Contact / branch:** name, department, and how to reach them.
- **Proposed follow-up:** date, time, subject (when scheduling).
- **Sources:** branch-directory file + numbered section.

## Guardrails
- Only take a calendar/write action after explicit employee confirmation.
- Use the employee's own user context via WorkIQ — never another user's.
