import { NextRequest, NextResponse } from "next/server";

// UX-only redirect: checks that a refresh cookie is present, not that it's
// valid. The real security boundary is the backend's per-request ownership
// checks - this just avoids flashing a protected page at a logged-out visitor.
export function middleware(request: NextRequest) {
  const hasRefreshCookie = request.cookies.has("refresh_token");
  if (!hasRefreshCookie) {
    const url = new URL("/login", request.url);
    url.searchParams.set("next", request.nextUrl.pathname);
    return NextResponse.redirect(url);
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/dashboard/:path*"],
};
