/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  
  // Enable environment variables for client-side
  env: {
    NEXT_PUBLIC_KG_WS_URL: process.env.NEXT_PUBLIC_KG_WS_URL || 'http://localhost:9001',
    NEXT_PUBLIC_KG_WS_PORT: process.env.NEXT_PUBLIC_KG_WS_PORT || '9001',
  },
};

export default nextConfig;
