/** Stats bar + pager for the association graph's paged views (an entity
 *  expansion or a district/station area listing). Extracted so GraphView stays
 *  under the source-size gate. */

interface PageInfo {
  total: number;
  offset: number;
  count: number;
}

/** "District X · 240 cases (showing 1–60)" — the current page's coordinates. */
export function GraphStats({
  focusLabel,
  pageInfo,
  pageSize,
}: {
  focusLabel: string;
  pageInfo: PageInfo;
  pageSize: number;
}) {
  return (
    <div className="graph-stats" role="status">
      {focusLabel ? `${focusLabel} · ` : ""}
      {pageInfo.total} case{pageInfo.total === 1 ? "" : "s"}
      {pageInfo.total > pageSize
        ? ` (showing ${pageInfo.offset + 1}–${pageInfo.offset + pageInfo.count})`
        : ""}
    </div>
  );
}

/** Prev / page-of / Next. Renders nothing when everything fits on one page. */
export function GraphPager({
  page,
  loading,
  pageInfo,
  pageSize,
  onGoto,
}: {
  page: number;
  loading: boolean;
  pageInfo: PageInfo;
  pageSize: number;
  onGoto: (pg: number) => void;
}) {
  if (pageInfo.total <= pageSize) return null;
  return (
    <div className="graph-pager" role="navigation" aria-label="Case pages">
      <button disabled={page === 0 || loading} onClick={() => onGoto(page - 1)}>
        &#8249; Prev
      </button>
      <span>
        Page {page + 1} / {Math.ceil(pageInfo.total / pageSize)}
      </span>
      <button
        disabled={(page + 1) * pageSize >= pageInfo.total || loading}
        onClick={() => onGoto(page + 1)}
      >
        Next &#8250;
      </button>
    </div>
  );
}
