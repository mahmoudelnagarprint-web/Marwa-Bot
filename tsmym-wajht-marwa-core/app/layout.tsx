import { Analytics } from '@vercel/analytics/next'
import type { Metadata, Viewport } from 'next'
import { IBM_Plex_Sans_Arabic, IBM_Plex_Mono, Reem_Kufi } from 'next/font/google'
import './globals.css'

const plexArabic = IBM_Plex_Sans_Arabic({
  subsets: ['arabic', 'latin'],
  weight: ['400', '500', '600', '700'],
  variable: '--font-plex-arabic',
  display: 'swap',
})

const reemKufi = Reem_Kufi({
  subsets: ['arabic', 'latin'],
  weight: ['500', '600', '700'],
  variable: '--font-reem-kufi',
  display: 'swap',
})

const plexMono = IBM_Plex_Mono({
  subsets: ['latin'],
  weight: ['400', '500'],
  variable: '--font-plex-mono',
  display: 'swap',
})

export const metadata: Metadata = {
  title: 'مروة كور — غرفة القيادة',
  description: 'لوحة تحكم ذكية بإدارة مركزية لورشة النجار برنت بربط 10 وكلاء ذكاء اصطناعي متخصصين.',
  generator: 'v0.app',
  icons: {
    icon: [
      { url: '/icon-light-32x32.png', media: '(prefers-color-scheme: light)' },
      { url: '/icon-dark-32x32.png', media: '(prefers-color-scheme: dark)' },
      { url: '/icon.svg', type: 'image/svg+xml' },
    ],
    apple: '/apple-icon.png',
  },
}

export const viewport: Viewport = {
  colorScheme: 'dark',
  themeColor: '#171926',
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html
      lang="ar"
      dir="rtl"
      className={`dark ${plexArabic.variable} ${reemKufi.variable} ${plexMono.variable}`}
      suppressHydrationWarning
    >
      <body className="antialiased font-sans bg-background text-foreground" suppressHydrationWarning>
        {children}
        {process.env.NODE_ENV === 'production' && <Analytics />}
      </body>
    </html>
  )
}
