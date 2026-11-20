/** Instant Soft Nav shell while card detail SSR resolves (T1.1). */

export default function CardDetailLoading() {
  return (
    <article
      className="detail-page detail-page-desk detail-page-loading"
      aria-busy="true"
      aria-label="Loading card"
    >
      <div className="detail-back detail-back-skel" />
      <section className="detail-hero-band">
        <div className="detail-hero-art">
          <div className="card-skeleton-art detail-lcp-skel" />
        </div>
        <div className="detail-hero-copy">
          <div className="card-skeleton-line" style={{ width: "70%" }} />
          <div
            className="card-skeleton-line is-short"
            style={{ width: "45%", marginTop: "0.5rem" }}
          />
          <div
            className="card-skeleton-line"
            style={{ width: "38%", marginTop: "1rem", height: "1.6rem" }}
          />
        </div>
      </section>
    </article>
  );
}
