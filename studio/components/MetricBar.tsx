// Horizontal comparison bar — used for token/latency comparisons.
export function MetricBar({
  label,
  value,
  max,
  color = "bg-signal-blue",
  suffix = "",
}: {
  label: string;
  value: number;
  max: number;
  color?: string;
  suffix?: string;
}) {
  const width = max > 0 ? Math.max(2, (value / max) * 100) : 0;
  return (
    <div className="space-y-1">
      <div className="flex justify-between font-mono text-[11px]">
        <span className="text-ink-300">{label}</span>
        <span className="text-ink-100">
          {value.toLocaleString()}
          {suffix}
        </span>
      </div>
      <div className="h-1.5 rounded-full bg-ink-800">
        <div
          className={`h-1.5 rounded-full ${color} transition-all duration-500`}
          style={{ width: `${width}%` }}
        />
      </div>
    </div>
  );
}
