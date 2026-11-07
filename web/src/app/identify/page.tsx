import { IdentifyView } from "@/components/IdentifyView";

export const metadata = {
  title: "Scan card — Kestrel",
  description:
    "Photograph a Pokémon TCG card — Kestrel OCR matches it to the desk for fair / edge calls.",
};

export default function IdentifyPage() {
  return <IdentifyView />;
}
