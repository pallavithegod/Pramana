# Pramana Agent Workspace

Next.js chat interface with a side-panel Telemetry Console. Setup, exact monorepo tree and the API contract are in ../../README.md. Start FastAPI on port 8000, then run `npm ci` and `npm run dev` here.

The browser uses same-origin `/api/chat/*` requests. `next.config.ts` proxies to the local API; `PRAMANA_BASE_URL` can override its default address on the Next server. Credentials belong only in the backend `.env.pramana`.

The four agent components are in `src/components/agent/`. Chat transport and types are in `src/lib/chat.ts`. Layout/style/icon are in `src/app/`. Old dashboard routes were removed.

Run `npm run typecheck` and `npm run build`. Preview PNGs were captured using explicit mocked provider/model-readiness and SSE responses to check layout and rendering. They do not demonstrate live model inference or search.
