import type { Metadata } from "next"
import { Bricolage_Grotesque, Geist_Mono } from "next/font/google"
import "./globals.css"

const sans = Bricolage_Grotesque({
  variable: "--font-sans",
  subsets: ["latin"],
})

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
})

export const metadata: Metadata = {
  title: "Self-Maintaining API",
  description:
    "Detect third-party API drift, scan your client code, generate a patch, and open a pull request.",
}

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${sans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col font-sans">{children}</body>
    </html>
  )
}
