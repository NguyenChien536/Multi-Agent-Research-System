import type { Metadata } from "next";
import "./globals.css";
import 'katex/dist/katex.min.css';
import { LanguageProvider } from "@/lib/i18n";

export const metadata: Metadata = {
  title: "Synthia | Automated Research System",
  description: "Advanced multi-agent research platform for scientific inquiry, synthesis, and evidence-backed writing.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <LanguageProvider>
          {children}
        </LanguageProvider>
      </body>
    </html>
  );
}
