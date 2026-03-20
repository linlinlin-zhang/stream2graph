import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  transpilePackages: ["@stream2graph/ui", "@stream2graph/contracts"],
};

export default nextConfig;
