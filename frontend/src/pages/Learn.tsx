import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { getTrainingContent, type TrainingContent } from "../api/client";

/**
 * Learn page: browses the educational content bundle.
 *
 * The backend ships four content kinds:
 *  - tips             quick, category-tagged one-liners
 *  - vocabulary       term/definition/example
 *  - strategy_guides  markdown-ish longform
 *  - cheat_sheets     lookup tables (preflop, pot odds, draws, etc.)
 *
 * The page exposes all of them with category + difficulty filters
 * so a user can drill down by what they want to learn. Links flow
 * back to Training/Analytics for practical follow-ups.
 */
type Tab = "tips" | "vocabulary" | "guides" | "cheat-sheets";

const TABS: { id: Tab; label: string }[] = [
  { id: "tips", label: "Tips" },
  { id: "vocabulary", label: "Glossary" },
  { id: "guides", label: "Strategy Guides" },
  { id: "cheat-sheets", label: "Cheat Sheets" },
];

const DIFFICULTIES = ["all", "beginner", "intermediate", "advanced"] as const;

function uniqueCategories(items: { category?: string }[]): string[] {
  const set = new Set<string>();
  for (const item of items) {
    if (item.category) set.add(item.category);
  }
  return Array.from(set).sort();
}

/** Render a single tip / strategy guide card with title + body. */
function ContentCard({
  title,
  body,
  category,
  difficulty,
  bodyAsMarkdown,
}: {
  title: string;
  body: string;
  category?: string;
  difficulty?: string;
  bodyAsMarkdown?: boolean;
}) {
  // We don't pull in a markdown library; the strategy guides use
  // simple bold (**word**) markers we can render inline by splitting
  // on **. For full markdown we'd swap in marked / react-markdown.
  const rendered = bodyAsMarkdown
    ? body.split(/(\*\*[^*]+\*\*)/g).map((segment, i) => {
        if (segment.startsWith("**") && segment.endsWith("**")) {
          return <strong key={i}>{segment.slice(2, -2)}</strong>;
        }
        return <span key={i}>{segment}</span>;
      })
    : body;

  return (
    <div className="learn-card panel">
      <div className="learn-card-header">
        <h3>{title}</h3>
        <div className="learn-card-tags">
          {difficulty && <span className={`tag tag-${difficulty}`}>{difficulty}</span>}
          {category && <span className="tag">{category}</span>}
        </div>
      </div>
      <div className="learn-card-body">
        {bodyAsMarkdown ? (
          <pre className="learn-card-pre">{rendered}</pre>
        ) : (
          <p>{body}</p>
        )}
      </div>
    </div>
  );
}

export default function Learn() {
  const [content, setContent] = useState<TrainingContent | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("tips");
  const [categoryFilter, setCategoryFilter] = useState<string>("all");
  const [difficultyFilter, setDifficultyFilter] =
    useState<(typeof DIFFICULTIES)[number]>("all");
  const [search, setSearch] = useState("");

  useEffect(() => {
    let cancelled = false;
    getTrainingContent()
      .then((data) => {
        if (!cancelled) setContent(data);
      })
      .catch((err) => {
        if (cancelled) return;
        setStatus(err instanceof Error ? err.message : "Failed to load content");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const tipsCategories = useMemo(
    () => (content ? uniqueCategories(content.tips) : []),
    [content]
  );
  const guidesCategories = useMemo(
    () => (content ? uniqueCategories(content.strategy_guides) : []),
    [content]
  );

  const activeCategories =
    tab === "tips" ? tipsCategories : tab === "guides" ? guidesCategories : [];

  function matchSearch(text: string): boolean {
    if (!search.trim()) return true;
    return text.toLowerCase().includes(search.trim().toLowerCase());
  }

  return (
    <>
      <section className="section">
        <div className="section-header">
          <div>
            <h2>Learn</h2>
            <p>
              Tips, vocabulary, strategy guides, and quick-reference cheat
              sheets — all in one place. Filter by topic or difficulty.
            </p>
          </div>
          <div className="toolbar-row">
            <Link className="btn ghost" to="/training">
              Practice drills
            </Link>
            <Link className="btn ghost" to="/analytics">
              See your stats
            </Link>
          </div>
        </div>

        <div className="learn-tabs">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              className={`tab-button ${tab === t.id ? "active" : ""}`}
              onClick={() => {
                setTab(t.id);
                setCategoryFilter("all");
              }}
            >
              {t.label}
            </button>
          ))}
        </div>

        <div className="learn-filters">
          <input
            type="text"
            placeholder="Search…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          {activeCategories.length > 0 && (
            <select
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
            >
              <option value="all">All categories</option>
              {activeCategories.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          )}
          {(tab === "tips" || tab === "guides") && (
            <select
              value={difficultyFilter}
              onChange={(e) =>
                setDifficultyFilter(e.target.value as typeof difficultyFilter)
              }
            >
              {DIFFICULTIES.map((d) => (
                <option key={d} value={d}>
                  {d === "all" ? "Any level" : d}
                </option>
              ))}
            </select>
          )}
        </div>

        {status && <div className="form-status">{status}</div>}

        {!content && !status && <div className="muted">Loading…</div>}

        {content && (
          <div className="learn-grid">
            {tab === "tips" &&
              content.tips
                .filter(
                  (t) =>
                    (categoryFilter === "all" || t.category === categoryFilter) &&
                    (difficultyFilter === "all" ||
                      t.difficulty === difficultyFilter) &&
                    (matchSearch(t.title) || matchSearch(t.content))
                )
                .map((t) => (
                  <ContentCard
                    key={t.title}
                    title={t.title}
                    body={t.content}
                    category={t.category}
                    difficulty={t.difficulty}
                  />
                ))}

            {tab === "vocabulary" &&
              content.vocabulary
                .filter(
                  (v) =>
                    matchSearch(v.term) ||
                    matchSearch(v.definition) ||
                    matchSearch(v.example ?? "")
                )
                .map((v) => (
                  <div key={v.term} className="learn-card panel">
                    <div className="learn-card-header">
                      <h3>{v.term}</h3>
                    </div>
                    <div className="learn-card-body">
                      <p>{v.definition}</p>
                      {v.example && (
                        <p className="muted small">e.g. {v.example}</p>
                      )}
                    </div>
                  </div>
                ))}

            {tab === "guides" &&
              content.strategy_guides
                .filter(
                  (g) =>
                    (categoryFilter === "all" || g.category === categoryFilter) &&
                    (difficultyFilter === "all" ||
                      g.difficulty === difficultyFilter) &&
                    (matchSearch(g.title) || matchSearch(g.content))
                )
                .map((g) => (
                  <ContentCard
                    key={g.title}
                    title={g.title}
                    body={g.content}
                    category={g.category}
                    difficulty={g.difficulty}
                    bodyAsMarkdown
                  />
                ))}

            {tab === "cheat-sheets" &&
              Object.entries(content.cheat_sheets || {}).map(([name, value]) => (
                <div key={name} className="learn-card panel">
                  <div className="learn-card-header">
                    <h3>{name.replace(/_/g, " ")}</h3>
                  </div>
                  <div className="learn-card-body">
                    <pre className="learn-card-pre">
                      {JSON.stringify(value, null, 2)}
                    </pre>
                  </div>
                </div>
              ))}
          </div>
        )}
      </section>
    </>
  );
}
