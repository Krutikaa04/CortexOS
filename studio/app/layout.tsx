import type { Metadata } from "next";
import "./globals.css";
import { RepoProvider } from "@/lib/repo-context";
import { Sidebar } from "@/components/Sidebar";

export const metadata: Metadata = {
  title: "CortexOS",
  description:
    "AI operating system for software engineering — understand, generate, and debug real repositories at minimum inference cost.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <RepoProvider>
          <div className="flex h-screen overflow-hidden">
            <Sidebar />
            <main className="flex-1 overflow-hidden">{children}</main>
          </div>
        </RepoProvider>
      </body>
    </html>
  );
}
