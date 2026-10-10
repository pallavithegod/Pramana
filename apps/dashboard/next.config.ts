import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // FastAPI serves the data; the dashboard is a pure client of the MoSPI-mirror API.
  env: {
    NEXT_PUBLIC_APIX_BASE: process.env.NEXT_PUBLIC_APIX_BASE ?? "http://127.0.0.1:8001",
  },
};

export default nextConfig;
