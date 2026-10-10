"use client";

import { useState } from "react";
import { apiUrl } from "@/lib/api";
import { copyText } from "@/lib/clipboard";

/** Standard chart-card anatomy (DESIGN.md §4): title · exact subtitle · export
 * menu with the literal API call that reproduces the chart. */
export default function ChartCard({
  title,
  subtitle,
  apiPath,
  children,
  right,
}: {
  title: string;
  subtitle: string;
  apiPath?: string;
  children: React.ReactNode;
  right?: React.ReactNode;
}) {
  const [copied, setCopied] = useState(false);
  return (
    <section className="card p-5">
      <header className="mb-3 flex items-start justify-between gap-4">
        <div>
          <h2 className="text-[15px] font-medium">{title}</h2>
          <p className="mt-0.5 text-xs" style={{ color: "var(--ink-secondary)" }}>
            {subtitle}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {right}
          {apiPath && (
            <button
              onClick={async () => {
                const copiedNow = await copyText(apiUrl(apiPath));
                if (copiedNow) {
                  setCopied(true);
                  setTimeout(() => setCopied(false), 1500);
                }
              }}
              className="btn-api"
              title={`Copy the API call that reproduces this chart:\n${apiUrl(apiPath)}`}
            >
              {copied ? "✓ Copied" : "API"}
            </button>
          )}
        </div>
      </header>
      {children}
    </section>
  );
}
