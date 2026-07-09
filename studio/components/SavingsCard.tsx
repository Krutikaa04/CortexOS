// Savings card shown alongside every answer: real measured tokens for this
// question through CortexOS vs a conventional RAG pipeline, plus what those
// tokens would cost at public commercial API list prices.

import {
  batchInputCostUSD,
  formatUSD,
  PRICE_LIST_DATE,
  QUERY_BATCH,
  REFERENCE_MODELS,
} from "@/lib/pricing";

export function SavingsCard({
  cortexTokens,
  baselineTokens,
  baselinePending,
}: {
  cortexTokens: number;
  baselineTokens: number | null; // null = comparison still running
  baselinePending: boolean;
}) {
  const reduction =
    baselineTokens != null && baselineTokens > 0
      ? 100 * (1 - cortexTokens / baselineTokens)
      : null;

  return (
    <section className="panel overflow-hidden">
      <div className="panel-header">
        <span className="panel-title">What this question cost</span>
        <span className="font-mono text-[10px] text-ink-500">
          measured tokens · real executions
        </span>
      </div>

      <div className="grid grid-cols-2 divide-x divide-ink-800">
        <div className="p-4 text-center">
          <div className="stat-label">CortexOS sent</div>
          <div className="stat-value mt-1 text-signal-blue">
            {cortexTokens.toLocaleString()}
          </div>
          <div className="text-[11px] text-ink-500">tokens</div>
        </div>
        <div className="p-4 text-center">
          <div className="stat-label">Conventional RAG sent</div>
          {baselineTokens != null ? (
            <>
              <div className="stat-value mt-1 text-signal-amber">
                {baselineTokens.toLocaleString()}
              </div>
              <div className="text-[11px] text-ink-500">tokens</div>
            </>
          ) : (
            <div className="mt-2 text-sm text-ink-500">
              {baselinePending ? (
                <span className="inline-flex items-center gap-2">
                  <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-signal-amber" />
                  measuring…
                </span>
              ) : (
                "comparison off"
              )}
            </div>
          )}
        </div>
      </div>

      {reduction != null && (
        <div className="border-t border-ink-800 bg-signal-green/5 px-4 py-3 text-center">
          <span className="font-mono text-xl font-semibold text-signal-green">
            {reduction > 0 ? "−" : "+"}
            {Math.abs(reduction).toFixed(1)}%
          </span>
          <span className="ml-2 text-sm text-ink-300">
            tokens {reduction > 0 ? "saved" : "extra"}, same question answered
          </span>
        </div>
      )}

      {baselineTokens != null && reduction != null && reduction > 0 && (
        <div className="border-t border-ink-800 p-4">
          <div className="stat-label mb-2">
            If these tokens were bought from a commercial API
          </div>
          <table className="w-full font-mono text-xs">
            <thead>
              <tr className="text-[10px] uppercase tracking-wider text-ink-500">
                <th className="pb-1 text-left font-normal">
                  per {QUERY_BATCH.toLocaleString()} queries
                </th>
                <th className="pb-1 text-right font-normal">RAG app</th>
                <th className="pb-1 text-right font-normal">via CortexOS</th>
                <th className="pb-1 text-right font-normal">saved</th>
              </tr>
            </thead>
            <tbody>
              {REFERENCE_MODELS.map((m) => {
                const ragCost = batchInputCostUSD(baselineTokens, m);
                const cortexCost = batchInputCostUSD(cortexTokens, m);
                return (
                  <tr key={m.name} className="text-ink-200">
                    <td className="py-0.5 text-ink-300">{m.name}</td>
                    <td className="py-0.5 text-right">{formatUSD(ragCost)}</td>
                    <td className="py-0.5 text-right">{formatUSD(cortexCost)}</td>
                    <td className="py-0.5 text-right text-signal-green">
                      {formatUSD(ragCost - cortexCost)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <p className="mt-3 text-[11px] leading-relaxed text-ink-500">
            Estimated at public API list prices ({PRICE_LIST_DATE}), input
            tokens only. Token counts are real measurements from this
            question run through both pipelines on the same local models —
            CortexOS itself ran on your machine for ₹0.
          </p>
        </div>
      )}
    </section>
  );
}
