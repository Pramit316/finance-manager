---
name: finance-ai
description: Implement AI-powered categorisation, analysis and conversational features for personal financial data.
---

# Finance AI

AI must sit on top of validated financial data.

AI must NOT be the authoritative calculation engine.

Incorrect:

Send all transactions to AI and ask:
"How much did I spend?"

Correct:

SQL/database calculates spending = 25,420.

AI explains:
"Your spending increased mainly because..."

## Appropriate AI Uses

AI may perform:

- transaction categorisation
- merchant interpretation
- natural-language explanations
- financial trend summaries
- question understanding
- unusual spending explanations

## Deterministic Calculations

Use application code or SQL for:

- totals
- balances
- percentages
- averages
- savings rate
- income
- expenses
- budgets
- date filtering

Never depend on an LLM for arithmetic that the application can calculate.

## Privacy

Provide the AI only the minimum financial information required
for the requested analysis.

Never send credentials or authentication information to an AI model.