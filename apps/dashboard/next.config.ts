import type { NextConfig } from "next";
const nextConfig: NextConfig = {
    async rewrites() { return [{ source: "/api/chat/:path*", destination: `${process.env.PRAMANA_BASE_URL ?? "http://127.0.0.1:8000"}/api/chat/:path*` }]; },
};
export default nextConfig;
