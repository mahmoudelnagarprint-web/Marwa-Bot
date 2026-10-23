/** @type {import('next').NextConfig} */
const nextConfig = {
  typescript: {
    ignoreBuildErrors: true,
  },
  images: {
    unoptimized: true,
  },
  // Next 16 يمنع موارد التطوير (/_next/hmr) من أصل غير localhost افتراضياً،
  // فيفشل ترطيب React عند فتح الواجهة عبر 127.0.0.1. السماح به صريحاً.
  allowedDevOrigins: ['127.0.0.1', 'localhost', '192.168.1.50'],
}

export default nextConfig
