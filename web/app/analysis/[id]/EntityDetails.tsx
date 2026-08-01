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
            className="rounded-md p-4 glass-entity-blue space-y-3"
          >
            <div>
              <h3 className="font-semibold text-base text-black">{entity.name}</h3>
              <p className="text-xs text-blueberry-600 capitalize">{entity.type}</p>
            </div>

            {entity.description && (
              <div>
                <p className="text-sm text-stone-700 leading-relaxed">
                  {entity.description}
                </p>
              </div>
            )}

            {entity.related_claims && entity.related_claims.length > 0 && (
              <div>
                <p className="text-xs font-medium text-blueberry-700 mb-2">
                  Related Claims:
                </p>
                <ul className="space-y-1">
                  {entity.related_claims.map((claim, idx) => (
                    <li
                      key={idx}
                      className="text-xs text-black bg-blueberry-50 rounded-sm p-1.5 border-l-2 border-blueberry-300"
                    >
                      {claim}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {entity.related_sources && entity.related_sources.length > 0 && (
              <div>
                <p className="text-xs font-medium text-blueberry-700 mb-2">
                  Related News & Speeches:
                </p>
                <ul className="space-y-2">
                  {entity.related_sources.map((source, idx) => (
                    <li key={idx} className="text-xs">
                      <div className="flex items-center gap-2">
                        {source.category && (
                          <span className="inline-block text-xs px-2 py-0.5 rounded-sm bg-blueberry-100 text-blueberry-700">
                            {source.category}
                          </span>
                        )}
                        <a
                          href={source.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="font-medium text-blueberry-600 hover:text-blueberry-700 hover:underline block truncate"
                          title={source.title}
                        >
                          {source.title}
                        </a>
                      </div>
                      {source.summary ? (
                        <p className="text-stone-700 leading-relaxed mt-1 text-sm">{source.summary}</p>
                      ) : source.snippet ? (
                        <p className="text-stone-600 line-clamp-2 mt-1">{source.snippet}</p>
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
