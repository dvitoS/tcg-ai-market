import type { MetadataRoute } from "next";

const SITE = "https://www.kestreltcg.app";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        disallow: ["/offline", "/auth/", "/pro/success"],
      },
    ],
    sitemap: `${SITE}/sitemap.xml`,
    host: SITE,
  };
}
