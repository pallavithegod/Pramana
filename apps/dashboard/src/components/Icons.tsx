/** Inline stroke icon set (24×24 viewBox, stroke=currentColor, 1.7px) — keeps
 * the SaaS-admin look without an icon dependency. */

function I({
  children,
  size = 18,
  className,
}: {
  children: React.ReactNode;
  size?: number;
  className?: string;
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden
    >
      {children}
    </svg>
  );
}

export const IconGrid = (p: { size?: number; className?: string }) => (
  <I {...p}>
    <rect x="3" y="3" width="7" height="7" rx="1.5" />
    <rect x="14" y="3" width="7" height="7" rx="1.5" />
    <rect x="3" y="14" width="7" height="7" rx="1.5" />
    <rect x="14" y="14" width="7" height="7" rx="1.5" />
  </I>
);

export const IconRoute = (p: { size?: number; className?: string }) => (
  <I {...p}>
    <circle cx="6" cy="19" r="2.2" />
    <circle cx="18" cy="5" r="2.2" />
    <path d="M8 19h6a4 4 0 0 0 4-4v0a4 4 0 0 0-4-4H10a4 4 0 0 1-4-4v0" />
  </I>
);

export const IconLayers = (p: { size?: number; className?: string }) => (
  <I {...p}>
    <path d="m12 3 9 5-9 5-9-5 9-5Z" />
    <path d="m3 13 9 5 9-5" />
  </I>
);

export const IconTrend = (p: { size?: number; className?: string }) => (
  <I {...p}>
    <path d="M3 17l6-6 4 4 8-8" />
    <path d="M15 7h6v6" />
  </I>
);

export const IconScale = (p: { size?: number; className?: string }) => (
  <I {...p}>
    <path d="M12 3v18M4 21h16" />
    <path d="M7 7 4 13a3 3 0 0 0 6 0L7 7ZM17 7l-3 6a3 3 0 0 0 6 0l-3-6Z" />
    <path d="M5 7h14" />
  </I>
);

export const IconUsers = (p: { size?: number; className?: string }) => (
  <I {...p}>
    <circle cx="9" cy="8" r="3.2" />
    <path d="M3.5 20a5.5 5.5 0 0 1 11 0" />
    <path d="M16 5.5a3.2 3.2 0 0 1 0 5.8M17.5 14.6a5.5 5.5 0 0 1 3 4.9" />
  </I>
);

export const IconShield = (p: { size?: number; className?: string }) => (
  <I {...p}>
    <path d="M12 3 5 6v5c0 4.5 3 8.2 7 10 4-1.8 7-5.5 7-10V6l-7-3Z" />
    <path d="m9 12 2 2 4-4" />
  </I>
);

export const IconSearch = (p: { size?: number; className?: string }) => (
  <I {...p}>
    <circle cx="11" cy="11" r="6.5" />
    <path d="m20 20-3.8-3.8" />
  </I>
);

export const IconSun = (p: { size?: number; className?: string }) => (
  <I {...p}>
    <circle cx="12" cy="12" r="4" />
    <path d="M12 2v2m0 16v2M4.9 4.9l1.4 1.4m11.4 11.4 1.4 1.4M2 12h2m16 0h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
  </I>
);

export const IconBell = (p: { size?: number; className?: string }) => (
  <I {...p}>
    <path d="M6 9a6 6 0 1 1 12 0c0 5 2 6 2 6H4s2-1 2-6Z" />
    <path d="M10.5 20a1.8 1.8 0 0 0 3 0" />
  </I>
);

export const IconCalendar = (p: { size?: number; className?: string }) => (
  <I {...p}>
    <rect x="3" y="5" width="18" height="16" rx="2.5" />
    <path d="M8 3v4m8-4v4M3 10h18" />
  </I>
);

export const IconDownload = (p: { size?: number; className?: string }) => (
  <I {...p}>
    <path d="M12 4v11m0 0 4-4m-4 4-4-4" />
    <path d="M4 19h16" />
  </I>
);

export const IconChevronDown = (p: { size?: number; className?: string }) => (
  <I {...p}>
    <path d="m6 9 6 6 6-6" />
  </I>
);

export const IconPlane = (p: { size?: number; className?: string }) => (
  <I {...p}>
    <path d="M10.5 13.5 3 11l1.5-1.5L10 10l4.5-4.5a1.6 1.6 0 0 1 2.3 2.3L12.3 12l.5 5.5L11.3 19l-2.5-7.5" />
  </I>
);

export const IconDatabase = (p: { size?: number; className?: string }) => (
  <I {...p}>
    <ellipse cx="12" cy="5.5" rx="7.5" ry="3" />
    <path d="M4.5 5.5v13c0 1.7 3.4 3 7.5 3s7.5-1.3 7.5-3v-13" />
    <path d="M4.5 12c0 1.7 3.4 3 7.5 3s7.5-1.3 7.5-3" />
  </I>
);

export const IconActivity = (p: { size?: number; className?: string }) => (
  <I {...p}>
    <path d="M3 12h4l3-8 4 16 3-8h4" />
  </I>
);

export const IconBook = (p: { size?: number; className?: string }) => (
  <I {...p}>
    <path d="M4 5a2 2 0 0 1 2-2h14v18H6a2 2 0 0 1-2-2V5Z" />
    <path d="M20 17H6a2 2 0 0 0-2 2" />
  </I>
);

export const IconEye = (p: { size?: number; className?: string }) => (
  <I {...p}>
    <path d="M2 12s3.5-6.5 10-6.5S22 12 22 12s-3.5 6.5-10 6.5S2 12 2 12Z" />
    <circle cx="12" cy="12" r="2.8" />
  </I>
);
