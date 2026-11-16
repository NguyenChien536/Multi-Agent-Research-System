/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  // A separate QA build avoids stale OneDrive placeholders in the default cache.
  distDir: process.env.NEXT_DIST_DIR || '.next',
};

export default nextConfig;
