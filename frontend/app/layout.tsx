import type { Metadata } from "next";
import { ClerkProvider } from "@clerk/nextjs";
import { ThemeProvider } from "@/components/theme-provider";
import "./globals.css";

// Note: intentionally using the system font stack defined in
// globals.css (--font-sans) instead of next/font/google. Fetching
// DM Sans from Google Fonts at build time makes the Docker build
// fail in any environment without outbound internet access (common
// in CI runners and locked-down build servers). If you want DM Sans
// specifically and know your build environment has internet access,
// swap this back to `import { DM_Sans } from "next/font/google"`.

export const metadata: Metadata = {
  title: "CryptoSage — Firmware Cryptographic Security Analysis",
  description:
    "Upload firmware to detect cryptographic algorithms, assess security risk, and get evidence-backed explanations powered by AI.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <ClerkProvider>
      <html lang="en" suppressHydrationWarning>
        <body className="font-sans antialiased">
          <ThemeProvider
            attribute="class"
            defaultTheme="dark"
            enableSystem
            disableTransitionOnChange
          >
            {children}
          </ThemeProvider>
        </body>
      </html>
    </ClerkProvider>
  );
}
