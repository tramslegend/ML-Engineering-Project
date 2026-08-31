/** @type {import('next').NextConfig} */
const nextConfig = {
  // Static export for S3 + CloudFront hosting (infra/modules/cloudfront) --
  // safe here since every page fetches data client-side from the separate
  // FastAPI backend (NEXT_PUBLIC_API_BASE), no Next.js server rendering or
  // API routes to lose.
  output: "export",
};

export default nextConfig;
