/**
 * Pass-through loader — avoid Vercel Image Optimization billing wall.
 *
 * Production was returning HTTP 402 OPTIMIZED_IMAGE_REQUEST_PAYMENT_REQUIRED
 * for `/_next/image?url=…` (TCGPlayer / Scrydex / TCGdex CDNs), so card and
 * sealed art disappeared even when the origin CDN URLs were fine.
 */
export default function imageLoader({ src }: { src: string }): string {
  return src;
}
