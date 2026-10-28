import { NextResponse, type NextRequest } from "next/server";

/**
 * Role routes need a session cookie. Without cs_access the request goes to
 * /login with a back-link. Whether the cookie is still valid, and whether
 * its role may open the route, is decided by the route group layout.
 */
export function proxy(request: NextRequest) {
  if (request.cookies.has("cs_access")) return NextResponse.next();
  const url = request.nextUrl.clone();
  const next = `${request.nextUrl.pathname}${request.nextUrl.search}`;
  url.pathname = "/login";
  url.search = `?next=${encodeURIComponent(next)}`;
  return NextResponse.redirect(url);
}

export const config = {
  matcher: [
    "/aicte/:path*",
    "/ro/:path*",
    "/college/:path*",
    "/student/:path*",
    "/university/:path*",
    "/admin/:path*",
  ],
};
