import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";
import { HealthIndicator } from "@/components/HealthIndicator";

export const metadata: Metadata = {
  title: "CortexOS Studio",
  description:
    "Visual control and observability for the CortexOS adaptive inference runtime",
};

const NAV = [
  { href: "/", label: "Command Center" },
  { href: "/playground", label: "Playground" },
  { href: "/executions", label: "Executions" },
  { href: "/benchmarks", label: "Benchmarks" },
];

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <div className="flex min-h-screen flex-col">
          <header className="sticky top-0 z-20 border-b border-ink-700 bg-ink-950/90 backdrop-blur">
            <div className="mx-auto flex h-14 max-w-7xl items-center gap-8 px-6">
              <Link href="/" className="flex items-baseline gap-2">
                <span className="font-mono text-sm font-bold tracking-tight text-ink-100">
                  Cortex<span className="text-signal-blue">OS</span>
                </span>
                <span className="text-[10px] uppercase tracking-[0.2em] text-ink-400">
                  Studio
                </span>
              </Link>
              <nav className="flex gap-1">
                {NAV.map((item) => (
                  <Link
                    key={item.href}
                    href={item.href}
                    className="rounded px-3 py-1.5 text-[13px] text-ink-300 transition-colors hover:bg-ink-800 hover:text-ink-100"
                  >
                    {item.label}
                  </Link>
                ))}
              </nav>
              <div className="ml-auto">
                <HealthIndicator />
              </div>
            </div>
          </header>
          <main className="mx-auto w-full max-w-7xl flex-1 px-6 py-8">
            {children}
          </main>
          <footer className="border-t border-ink-800 py-4 text-center text-[11px] text-ink-500">
            CortexOS — adaptive inference runtime · Docker-first · zero-cost ·
            all metrics from real executions
          </footer>
        </div>
      </body>
    </html>
  );
}
