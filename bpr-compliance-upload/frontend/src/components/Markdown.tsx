"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export default function Markdown({ children }: { children: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        p: ({ children }) => <p className="mb-2 leading-relaxed last:mb-0">{children}</p>,
        strong: ({ children }) => <strong className="font-semibold text-bpr-navy">{children}</strong>,
        ul: ({ children }) => <ul className="mb-2 ml-4 list-disc space-y-0.5 last:mb-0">{children}</ul>,
        ol: ({ children }) => <ol className="mb-2 ml-4 list-decimal space-y-0.5 last:mb-0">{children}</ol>,
        li: ({ children }) => <li className="leading-relaxed">{children}</li>,
        h1: ({ children }) => <h3 className="mb-1.5 mt-2 font-display text-[15px] text-bpr-navy first:mt-0">{children}</h3>,
        h2: ({ children }) => <h3 className="mb-1.5 mt-2 font-display text-[14px] text-bpr-navy first:mt-0">{children}</h3>,
        h3: ({ children }) => <h4 className="mb-1 mt-2 text-[13px] font-semibold text-bpr-navy first:mt-0">{children}</h4>,
        code: ({ children }) => (
          <code className="rounded bg-bpr-navy/10 px-1 py-0.5 font-mono text-[0.9em]">{children}</code>
        ),
        table: ({ children }) => (
          <div className="mb-2 overflow-x-auto">
            <table className="w-full border-collapse text-left">{children}</table>
          </div>
        ),
        thead: ({ children }) => <thead className="border-b border-bpr-hairline">{children}</thead>,
        th: ({ children }) => <th className="px-2 py-1.5 font-medium text-bpr-ink2/70">{children}</th>,
        td: ({ children }) => <td className="border-t border-bpr-hairline/60 px-2 py-1.5">{children}</td>,
        a: ({ children, href }) => (
          <a href={href} target="_blank" rel="noreferrer" className="text-bpr-brass underline">
            {children}
          </a>
        ),
      }}
    >
      {children}
    </ReactMarkdown>
  );
}
