"use client";

import { EntityDetail } from "@/lib/api";

export function EntityDetails({ entities }: { entities: EntityDetail[] }) {
  if (!entities || entities.length === 0) {
    return null;
  }

  return (
    <section className="space-y-6">
      <h2 className="text-lg font-semibold">Entity Information</h2>
      <div className="grid gap-4 md:grid-cols-1 lg:grid-cols-2">
        {entities.map((entity) => (
          <div
            key={entity.name}
            className="rounded-lg border border-neutral-200 bg-white p-4 space-y-3"
          >
            <div>
              <h3 className="font-semibold text-base">{entity.name}</h3>
              <p className="text-xs text-neutral-500 capitalize">{entity.type}</p>
            </div>

            {entity.description && (
              <div>
                <p className="text-sm text-neutral-700 leading-relaxed">
                  {entity.description}
                </p>
              </div>
            )}

            {entity.related_claims && entity.related_claims.length > 0 && (
              <div>
                <p className="text-xs font-medium text-neutral-600 mb-2">
                  Related Claims:
                </p>
                <ul className="space-y-1">
                  {entity.related_claims.map((claim, idx) => (
                    <li
                      key={idx}
                      className="text-xs text-neutral-600 bg-neutral-50 rounded p-1.5 border-l-2 border-neutral-300"
                    >
                      {claim}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {entity.related_sources && entity.related_sources.length > 0 && (
              <div>
                <p className="text-xs font-medium text-neutral-600 mb-2">
                  Related News & Speeches:
                </p>
                <ul className="space-y-2">
                  {entity.related_sources.map((source, idx) => (
                    <li key={idx} className="text-xs">
                      <div className="flex items-center gap-2">
                        {source.category && (
                          <span className="inline-block text-xs px-2 py-0.5 rounded bg-neutral-100 text-neutral-700">
                            {source.category}
                          </span>
                        )}
                        <a
                          href={source.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="font-medium text-blue-600 hover:text-blue-800 hover:underline block truncate"
                          title={source.title}
                        >
                          {source.title}
                        </a>
                      </div>
                      {source.summary ? (
                        <p className="text-neutral-700 leading-relaxed mt-1 text-sm">{source.summary}</p>
                      ) : source.snippet ? (
                        <p className="text-neutral-600 line-clamp-2 mt-1">{source.snippet}</p>
                      ) : null}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}
