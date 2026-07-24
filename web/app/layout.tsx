import "./globals.css";
import { AuthProvider } from "@/lib/auth";
import { QueryProvider } from "@/lib/queryProvider";
import { NavBar } from "@/components/NavBar";

export const metadata = {
  title: "VerifyVault",
  description: "Political Communication Analyzer",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-neutral-50 text-neutral-900 antialiased" suppressHydrationWarning>
        <QueryProvider>
          <AuthProvider>
            <NavBar />
            {children}
          </AuthProvider>
        </QueryProvider>
      </body>
    </html>
  );
}
