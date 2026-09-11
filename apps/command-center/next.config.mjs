/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,

  // Emits a self-contained server plus only the node_modules it actually
  // reaches. infra/docker/dashboard.Dockerfile depends on this.
  output: "standalone",

  poweredByHeader: false,

  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "no-referrer" },
          {
            // The command center never needs the operator's camera, microphone,
            // or location. Denying them is one line and closes a whole class of
            // supply-chain escalation.
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=(), interest-cohort=()",
          },
        ],
      },
    ];
  },
};

export default nextConfig;
