import type { Metadata } from "next";
import { WalletPage } from "@/components/student/wallet-page";
import { t } from "@/lib/copy";

export const metadata: Metadata = { title: t("wallet.heading") };

export default function Wallet() {
  return <WalletPage />;
}
