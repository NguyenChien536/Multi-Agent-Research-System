import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Synthia | Automated Research System",
  description: "Hệ thống nghiên cứu tự động chuyên sâu, tổng hợp thông tin và trích dẫn bằng AI.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="vi">
      <body>{children}</body>
    </html>
  );
}
