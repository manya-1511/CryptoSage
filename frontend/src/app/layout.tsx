import type { Metadata } from "next";
import { Inter } from "next/font/google";
// @ts-ignore: CSS side-effect import without declaration file
import "./globals.css";
import { Providers } from "./providers";
import { Sidebar } from "@/components/layout/Sidebar";
import { Toaster } from "react-hot-toast";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "CryptoSage — Firmware Analysis Platform",
  description: "Extract, analyze, and understand firmware binaries",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body
        className={`${inter.className} bg-crypto-900 text-gray-100 min-h-screen`}
      >
        <Providers>
          <div className="flex min-h-screen">
            <Sidebar />
            <main className="flex-1 ml-64 p-8 overflow-auto">{children}</main>
          </div>
          <Toaster
            position="bottom-right"
            toastOptions={{
              style: {
                background: "#111b33",
                color: "#f1f5f9",
                border: "1px solid rgba(34,197,94,0.2)",
              },
            }}
          />
        </Providers>
      </body>
    </html>
  );
}
