import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Slide Studio",
  description: "Edit presentation text and export an editable PowerPoint.",
};
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
