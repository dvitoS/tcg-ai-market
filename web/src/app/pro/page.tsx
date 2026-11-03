import { ProView } from "@/components/ProView";
import { fetchBillingStatus } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function ProPage() {
  let checkoutUrl: string | null = null;
  let proOpen = true;
  let error: string | null = null;
  try {
    const status = await fetchBillingStatus();
    checkoutUrl = status.checkout_url;
    proOpen = status.pro_open;
  } catch (err) {
    error = err instanceof Error ? err.message : "Could not load billing status";
  }

  return <ProView checkoutUrl={checkoutUrl} proOpen={proOpen} error={error} />;
}
