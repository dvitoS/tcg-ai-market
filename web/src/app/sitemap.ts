import type { MetadataRoute } from "next";

const SITE = "https://www.kestreltcg.app";

export default function sitemap(): MetadataRoute.Sitemap {
  const now = new Date();
  const paths = [
    { path: "/", priority: 1, changeFrequency: "daily" as const },
    { path: "/browse", priority: 0.9, changeFrequency: "daily" as const },
    { path: "/pro", priority: 0.85, changeFrequency: "weekly" as const },
    { path: "/radar", priority: 0.8, changeFrequency: "daily" as const },
    { path: "/trade", priority: 0.8, changeFrequency: "weekly" as const },
    { path: "/portfolio", priority: 0.6, changeFrequency: "weekly" as const },
    { path: "/binder", priority: 0.55, changeFrequency: "weekly" as const },
    { path: "/scanner", priority: 0.5, changeFrequency: "weekly" as const },
    { path: "/identify", priority: 0.5, changeFrequency: "weekly" as const },
    { path: "/dealer", priority: 0.45, changeFrequency: "weekly" as const },
  ];

  return paths.map(({ path, priority, changeFrequency }) => ({
    url: `${SITE}${path === "/" ? "" : path}`,
    lastModified: now,
    changeFrequency,
    priority,
  }));
}
