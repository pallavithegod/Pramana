"use client";

import Link from "next/link";
import Image from "next/image";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

/** Close on any pointerdown outside `ref` — fires before the outside element's
 * own click, so the first outside click both closes the popover AND lands. */
function useClickOutside(open: boolean, ref: React.RefObject<HTMLElement | null>, close: () => void) {
  useEffect(() => {
    if (!open) return;
    const onDown = (e: PointerEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) close();
    };
    document.addEventListener("pointerdown", onDown);
    return () => document.removeEventListener("pointerdown", onDown);
  }, [open, ref, close]);
}
import { API_BASE } from "@/lib/api";
import {
  IconBell,
  IconBook,
  IconGrid,
  IconLayers,
  IconRoute,
  IconScale,
  IconSearch,
  IconShield,
  IconSun,
  IconTrend,
  IconUsers,
} from "@/components/Icons";

const NAV: {
  section: string;
  items: { href: string; label: string; icon: React.ComponentType<{ size?: number }> }[];
}[] = [
  {
    section: "Monitor",
    items: [
      { href: "/", label: "Overview", icon: IconGrid },
      { href: "/routes", label: "Routes", icon: IconRoute },
      { href: "/prism", label: "PRISM", icon: IconLayers },
    ],
  },
  {
    section: "Analytics",
    items: [
      { href: "/nowcast", label: "Nowcast", icon: IconTrend },
      { href: "/competition", label: "Competition", icon: IconScale },
    ],
  },
  {
    section: "Access",
    items: [
      { href: "/fair-fare", label: "Fair-Fare Check", icon: IconUsers },
      { href: "/trust", label: "Trust & Evidence", icon: IconShield },
    ],
  },
];

const LANDING_PAGE_URL = "https://air-sankhyiki.vercel.app/";
const DOCUMENTATION_URL = "https://air-sankhyiki.mintlify.site/";

function ThemeToggle() {
  // Two-state: read the EFFECTIVE theme (stamp or OS preference) and flip it —
  // a 3-way auto/dark/light cycle needed multiple clicks to visibly change.
  const [, force] = useState(0);
  const flip = () => {
    const stamp = document.documentElement.dataset.theme;
    const effectiveDark =
      stamp === "dark" ||
      (!stamp && window.matchMedia("(prefers-color-scheme: dark)").matches);
    document.documentElement.dataset.theme = effectiveDark ? "light" : "dark";
    force((n) => n + 1);
  };
  return (
    <button
      onClick={flip}
      className="flex h-9 w-9 items-center justify-center rounded-full"
      style={{ background: "var(--surface-2)", color: "var(--ink-secondary)" }}
      title="Switch light/dark"
      aria-label="Switch light/dark theme"
    >
      <IconSun size={17} />
    </button>
  );
}

function SearchBox() {
  const router = useRouter();
  const [q, setQ] = useState("");
  const [routes, setRoutes] = useState<string[]>([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const wrap = useRef<HTMLDivElement>(null);
  useClickOutside(open, wrap, () => setOpen(false));

  useEffect(() => {
    import("@/lib/api").then(({ routeList }) =>
      routeList().then(setRoutes).catch(() => setRoutes([])),
    );
  }, []);

  const needle = q.trim().toUpperCase();
  const matches = needle
    ? routes.filter((r) => r.includes(needle)).slice(0, 7)
    : routes.slice(0, 7);

  const go = (route: string) => {
    setOpen(false);
    setQ("");
    router.push(`/routes?route=${encodeURIComponent(route)}`);
  };

  return (
    <div className="relative w-full max-w-[340px]" ref={wrap}>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (matches.length) go(matches[Math.min(active, matches.length - 1)]);
        }}
        className="flex h-10 items-center gap-2.5 rounded-full border px-4"
        style={{ borderColor: "var(--hairline)", background: "var(--surface-2)" }}
      >
        <span style={{ color: "var(--ink-muted)" }}>
          <IconSearch size={15} />
        </span>
        <input
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setOpen(true);
            setActive(0);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") {
              e.preventDefault();
              setActive((a) => Math.min(a + 1, matches.length - 1));
            } else if (e.key === "ArrowUp") {
              e.preventDefault();
              setActive((a) => Math.max(a - 1, 0));
            } else if (e.key === "Escape") setOpen(false);
          }}
          placeholder="Search a route… e.g. DEL-BOM"
          className="w-full bg-transparent text-[13px] outline-none"
          style={{ color: "var(--ink)" }}
          aria-label="Search a route"
        />
      </form>
      {open && (
        <div
          className="card absolute left-0 right-0 top-11 z-30 overflow-hidden py-1"
          role="listbox"
        >
          {matches.map((r, i) => (
            <button
              key={r}
              type="button"
              role="option"
              aria-selected={i === active}
              onMouseDown={(e) => {
                e.preventDefault();
                go(r);
              }}
              onMouseEnter={() => setActive(i)}
              className="tnum flex w-full items-center justify-between px-4 py-2 text-left text-[13px]"
              style={{
                background: i === active ? "var(--accent-soft)" : "transparent",
                color: "var(--ink)",
              }}
            >
              {r}
              <span className="text-[11px]" style={{ color: "var(--ink-muted)" }}>
                view route ↵
              </span>
            </button>
          ))}
          {matches.length === 0 && (
            <div className="px-4 py-2.5 text-[12px]" style={{ color: "var(--ink-muted)" }}>
              No route in the basket matches “{needle}” — try a IATA pair like DEL-BOM.
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function NotificationsBell() {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<{ title: string; detail: string; tone: string }[]>([]);
  const wrap = useRef<HTMLDivElement>(null);
  useClickOutside(open, wrap, () => setOpen(false));

  useEffect(() => {
    if (!open || items.length) return;
    import("@/lib/api").then(({ api }) =>
      Promise.allSettled([api.index(), api.sourceHealth(), api.ledgerStatus()]).then(
        ([idx, health, ledger]) => {
          const out: { title: string; detail: string; tone: string }[] = [];
          if (idx.status === "fulfilled" && idx.value.data.length) {
            const last = idx.value.data[idx.value.data.length - 1];
            out.push({
              title: `APIx ${last.index.toFixed(2)} (${last.inflation != null ? `${last.inflation > 0 ? "+" : ""}${last.inflation.toFixed(2)}% DoD` : "base day"})`,
              detail: `Provisional daily index for ${last.date}`,
              tone: (last.inflation ?? 0) >= 0 ? "var(--diverge-pos)" : "var(--diverge-neg)",
            });
          }
          if (health.status === "fulfilled" && health.value.data.length) {
            const rows = health.value.data;
            const day = rows.reduce((m, r) => (r.date > m ? r.date : m), "");
            const n = rows.filter((r) => r.date === day).reduce((a, b) => a + b.quotes, 0);
            out.push({
              title: `Collection ran — ${n.toLocaleString("en-IN")} quotes`,
              detail: `Latest collection day ${day}, all sources`,
              tone: "var(--status-good)",
            });
          }
          if (ledger.status === "fulfilled" && ledger.value.data[0]) {
            const l = ledger.value.data[0];
            out.push({
              title: l.intact ? "Evidence ledger intact" : "LEDGER CHAIN BROKEN",
              detail: `${l.entries.toLocaleString("en-IN")} raw responses sealed`,
              tone: l.intact ? "var(--status-good)" : "var(--status-critical)",
            });
          }
          setItems(out);
        },
      ),
    );
  }, [open, items.length]);

  return (
    <div className="relative" ref={wrap}>
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex h-9 w-9 items-center justify-center rounded-full"
        style={{
          background: open ? "var(--accent-soft)" : "var(--surface-2)",
          color: open ? "var(--accent)" : "var(--ink-secondary)",
        }}
        title="Status notifications"
        aria-label="Status notifications"
        aria-expanded={open}
      >
        <IconBell size={17} />
      </button>
      {open && (
        <div className="card absolute right-0 top-11 z-30 w-[320px] overflow-hidden">
          <div
            className="border-b px-4 py-2.5 text-[13px] font-semibold"
            style={{ borderColor: "var(--hairline)" }}
          >
            Status
          </div>
          {items.length === 0 && (
            <div className="px-4 py-3 text-[12px]" style={{ color: "var(--ink-muted)" }}>
              Loading…
            </div>
          )}
          {items.map((it) => (
            <div
              key={it.title}
              className="flex gap-2.5 border-b px-4 py-2.5"
              style={{ borderColor: "var(--hairline)" }}
            >
              <span
                aria-hidden
                className="mt-1.5 inline-block h-2 w-2 shrink-0 rounded-full"
                style={{ background: it.tone }}
              />
              <div>
                <div className="text-[12.5px] font-medium">{it.title}</div>
                <div className="text-[11.5px]" style={{ color: "var(--ink-muted)" }}>
                  {it.detail}
                </div>
              </div>
            </div>
          ))}
          <Link
            href="/trust"
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => setOpen(false)}
            className="block px-4 py-2.5 text-[12.5px] font-semibold"
            style={{ color: "var(--accent)" }}
          >
            View Trust &amp; Evidence →
          </Link>
        </div>
      )}
    </div>
  );
}

export default function AppShell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const [asOf, setAsOf] = useState<string | null>(null);
  useEffect(() => {
    fetch(`${API_BASE}/api/apix/getSourceHealth`, { cache: "no-store" })
      .then((r) => r.json())
      .then((j) => {
        const rows: { last_collected_at: string }[] = j.data ?? [];
        const last = rows.reduce(
          (m, r) => (r.last_collected_at > m ? r.last_collected_at : m),
          "",
        );
        if (last) setAsOf(last.slice(0, 16).replace("T", " "));
      })
      .catch(() => null);
  }, []);

  return (
    <div className="flex min-h-screen">
      {/* ------------------------------------------------ sidebar */}
      <aside
        className="fixed inset-y-0 left-0 z-20 hidden w-[232px] flex-col border-r md:flex"
        style={{ background: "var(--surface)", borderColor: "var(--hairline)" }}
      >
        <a
          href={LANDING_PAGE_URL}
          className="flex items-center gap-2.5 px-5 pb-4 pt-5 transition-opacity hover:opacity-80"
          aria-label="Open the Air-Sankhyiki landing page"
          title="Air-Sankhyiki home"
        >
          <span className="flex h-10 w-10 shrink-0 items-center justify-center overflow-hidden rounded-xl">
            <Image
              src="/icon.png"
              alt=""
              width={40}
              height={40}
              className="h-full w-full object-contain"
              priority
            />
          </span>
          <div>
            <div className="text-[15px] font-bold leading-4 tracking-tight">APIx</div>
            <div className="text-[10.5px]" style={{ color: "var(--ink-muted)" }}>
              Air-Sankhyiki · एयर-सांख्यिकी
            </div>
          </div>
        </a>

        <nav className="flex-1 space-y-4 overflow-y-auto px-3 pt-1">
          {NAV.map((group) => (
            <div key={group.section}>
              <div className="eyebrow px-3 pb-1.5">{group.section}</div>
              <div className="space-y-0.5">
                {group.items.map((n) => {
                  const active = n.href === "/" ? path === "/" : path.startsWith(n.href);
                  const Icon = n.icon;
                  return (
                    <Link key={n.href} href={n.href} className={`nav-item ${active ? "active" : ""}`}>
                      <Icon size={17} />
                      {n.label}
                    </Link>
                  );
                })}
              </div>
            </div>
          ))}

          <div>
            <div className="eyebrow px-3 pb-1.5">Resources</div>
            <a href={`${API_BASE}/docs`} target="_blank" rel="noreferrer" className="nav-item">
              <IconBook size={17} />
              API Reference
            </a>
          </div>
        </nav>

        {/* API access card */}
        <div className="p-3">
          <div
            className="rounded-2xl p-4 text-white"
            style={{
              background:
                "linear-gradient(145deg, var(--accent-deep) 0%, var(--accent) 130%)",
            }}
          >
            <span className="mb-2 flex h-8 w-8 items-center justify-center rounded-lg bg-white/15">
              <IconDatabaseInline />
            </span>
            <div className="text-[13px] font-semibold">Air-Sankhyiki Docs</div>
            <p className="mt-1 text-[11px] leading-4 text-white/75">
              Explore the methodology, data pipeline, evidence model and API
              reference behind every dashboard view.
            </p>
            <a
              href={DOCUMENTATION_URL}
              target="_blank"
              rel="noreferrer"
              className="mt-3 block rounded-lg bg-white/95 py-1.5 text-center text-[12px] font-semibold"
              style={{ color: "var(--accent-deep)" }}
            >
              View documentation
            </a>
          </div>
        </div>
      </aside>

      {/* ------------------------------------------------ main */}
      <div className="flex min-w-0 flex-1 flex-col md:pl-[232px]">
        <header
          className="sticky top-0 z-10 flex h-[64px] items-center gap-4 border-b px-6"
          style={{ background: "var(--surface)", borderColor: "var(--hairline)" }}
        >
          <a
            href={LANDING_PAGE_URL}
            className="flex h-9 w-9 shrink-0 items-center justify-center overflow-hidden rounded-lg md:hidden"
            aria-label="Open the Air-Sankhyiki landing page"
            title="Air-Sankhyiki home"
          >
            <Image src="/icon.png" alt="" width={36} height={36} className="h-full w-full object-contain" priority />
          </a>
          <SearchBox />
          <div className="ml-auto flex items-center gap-2.5">
            {asOf && (
              <span className="tnum mr-1 hidden text-[11.5px] lg:block" style={{ color: "var(--ink-muted)" }}>
                Data as of {asOf} IST
              </span>
            )}
            <ThemeToggle />
            <NotificationsBell />
          </div>
        </header>

        <main className="mx-auto w-full max-w-[1200px] flex-1 px-6 py-6">{children}</main>

        <footer
          className="mx-auto w-full max-w-[1200px] px-6 pb-8 text-[11px]"
          style={{ color: "var(--ink-muted)" }}
        >
          Prototype for SIH 2026 PS 26056 (MoSPI). Data: robots.txt-compliant collection +
          licensed sources — see Trust &amp; Evidence for the full compliance matrix.
        </footer>
      </div>
    </div>
  );
}

function IconDatabaseInline() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="1.7" strokeLinecap="round" aria-hidden>
      <ellipse cx="12" cy="5.5" rx="7.5" ry="3" />
      <path d="M4.5 5.5v13c0 1.7 3.4 3 7.5 3s7.5-1.3 7.5-3v-13" />
      <path d="M4.5 12c0 1.7 3.4 3 7.5 3s7.5-1.3 7.5-3" />
    </svg>
  );
}
