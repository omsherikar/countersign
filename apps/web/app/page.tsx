import { redirect } from "next/navigation";
import { getMe } from "@/lib/auth";
import { landingFor } from "@/lib/roles";

/** `/` sends a signed-in user to their landing route and everyone else to /login. */
export default async function Home() {
  const me = await getMe();
  redirect(me ? landingFor(me.role) : "/login");
}
