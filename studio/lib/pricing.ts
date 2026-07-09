// Cost framing for token savings.
//
// Integrity rules: CortexOS runs on local open-source models at zero cost —
// it does not call these APIs. What we show is: "the tokens this question
// actually consumed, priced at public commercial API list rates". Token
// counts are real measurements from the local model runtime; only the
// prices come from provider price lists.

export const PRICE_LIST_DATE = "July 2026";

export interface ModelPrice {
  name: string;
  inputPerMTok: number; // USD per million input tokens (public list price)
}

export const REFERENCE_MODELS: ModelPrice[] = [
  { name: "Claude Sonnet 5", inputPerMTok: 3.0 },
  { name: "Claude Opus 4.8", inputPerMTok: 5.0 },
];

export const QUERY_BATCH = 10_000; // cost framing unit: "per 10,000 queries"

export function batchInputCostUSD(
  tokensPerQuery: number,
  price: ModelPrice,
): number {
  return (tokensPerQuery * QUERY_BATCH * price.inputPerMTok) / 1_000_000;
}

export function formatUSD(value: number): string {
  return value >= 100
    ? `$${Math.round(value).toLocaleString()}`
    : `$${value.toFixed(2)}`;
}
