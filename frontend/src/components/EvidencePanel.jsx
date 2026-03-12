import React from "react";

function EvidencePanel({ retrieval }) {
  const papers = retrieval?.papers ?? [];
  return (
    <div className="evidence-panel">
      <h3 className="evidence-title">Related papers</h3>
      {papers.length === 0 && (
        <p className="evidence-empty">No related papers.</p>
      )}
      {papers.map((paper, idx) => (
        <div key={paper.paper_key ?? idx} className="paper-card">
          <h4>{paper.title || "(untitled)"}</h4>
          <p className="paper-meta">
            {paper.journal && <span>{paper.journal}</span>}
            {paper.year && <span> · {paper.year}</span>}
            {paper.doi && (
              <span>
                {" "}
                ·{" "}
                <a
                  href={`https://doi.org/${paper.doi}`}
                  target="_blank"
                  rel="noreferrer"
                >
                  DOI
                </a>
              </span>
            )}
          </p>
          <p className="paper-score">
            Score sum: {paper.score_sum?.toFixed?.(3) ?? paper.score_sum} · Max:{" "}
            {paper.score_max?.toFixed?.(3) ?? paper.score_max}
          </p>

          <div className="paper-chunks-inline">
            {(paper.top_chunks || []).length === 0 && <p>No chunks.</p>}
            {(paper.top_chunks || []).map((chunk, cidx) => {
              const urls = chunk.figure_urls || [];
              const captions = chunk.figure_captions || [];
              return (
                <div key={chunk.faiss_id ?? cidx} className="chunk-row">
                  <div className="chunk-row-text">
                    <p className="chunk-meta">
                      {chunk.section && <span>{chunk.section}</span>}
                      {typeof chunk.score === "number" && (
                        <span> · score {chunk.score.toFixed(3)}</span>
                      )}
                    </p>
                    <p className="chunk-text">{chunk.text}</p>
                  </div>
                  {urls.length > 0 && (
                    <div className="chunk-row-figs">
                      {urls.map((url, i) => (
                        <figure key={url} className="figure-inline">
                          <img src={url} alt="figure" loading="lazy" />
                          {captions[i] && (
                            <figcaption>{captions[i]}</figcaption>
                          )}
                        </figure>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}

export default EvidencePanel;
