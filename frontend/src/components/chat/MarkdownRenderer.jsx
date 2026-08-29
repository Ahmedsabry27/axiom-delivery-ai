import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import CodeBlock from "./CodeBlock";

export default function MarkdownRenderer({ children }) {
  return (
    <article
      className="
        prose
        prose-lg
        text-stone-800
        max-w-none

        prose-headings:font-bold
        prose-headings:tracking-tight
        prose-headings:text-stone-950

        prose-h1:text-4xl
        prose-h1:mt-2
        prose-h1:mb-8

        prose-h2:text-3xl
        prose-h2:mt-10
        prose-h2:mb-5

        prose-h3:text-2xl
        prose-h3:mt-8
        prose-h3:mb-4

        prose-h4:text-xl
        prose-h4:mt-6
        prose-h4:mb-3

        prose-p:text-[17px]
        prose-p:leading-9
        prose-p:my-5

        prose-strong:text-stone-950
        prose-strong:font-semibold

        prose-ul:my-6
        prose-ol:my-6
        prose-li:my-2
        prose-li:leading-8

        prose-table:my-8

        prose-code:before:hidden
        prose-code:after:hidden
      "
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1({ children }) {
            return (
              <h1 className="mb-8 text-4xl font-bold tracking-tight">
                {children}
              </h1>
            );
          },

          h2({ children }) {
            return (
              <h2 className="mt-10 mb-5 border-l-4 border-[#a00028] pl-4 text-3xl font-bold">
                {children}
              </h2>
            );
          },

          h3({ children }) {
            return (
              <h3 className="mt-8 mb-4 text-2xl font-semibold">
                {children}
              </h3>
            );
          },

          h4({ children }) {
            return (
              <h4 className="mt-6 mb-3 text-xl font-semibold">
                {children}
              </h4>
            );
          },

          p({ children }) {
            return (
              <p className="my-5 text-[17px] leading-9">
                {children}
              </p>
            );
          },

          strong({ children }) {
            return (
              <strong className="font-semibold text-stone-950">
                {children}
              </strong>
            );
          },

          a({ href, children }) {
            return (
              <a
                href={href}
                target="_blank"
                rel="noopener noreferrer"
                className="font-medium text-[#a00028] underline decoration-[#d8a4b1] underline-offset-4 transition hover:text-[#7d001f]"
              >
                {children}
              </a>
            );
          },

          code({ className, children }) {
            const match = /language-(\w+)/.exec(className || "");

            if (!match) {
              return (
                <code className="rounded-md bg-muted px-1.5 py-1 font-mono text-sm text-[#a00028]">
                  {children}
                </code>
              );
            }

            return (
              <CodeBlock
                language={match[1]}
                code={String(children).replace(/\n$/, "")}
              />
            );
          },

          table({ children }) {
            return (
              <div className="my-8 overflow-x-auto rounded-2xl border shadow-sm">
                <table className="w-full border-collapse">
                  {children}
                </table>
              </div>
            );
          },

          thead({ children }) {
            return (
              <thead className="bg-muted/60">
                {children}
              </thead>
            );
          },

          th({ children }) {
            return (
              <th className="border-b px-4 py-3 text-left font-semibold">
                {children}
              </th>
            );
          },

          td({ children }) {
            return (
              <td className="border-b px-4 py-3 align-top">
                {children}
              </td>
            );
          },

          blockquote({ children }) {
            return (
              <blockquote className="my-8 border-l-4 border-[#a00028] bg-[#f7ecef] py-4 pl-6 italic">
                {children}
              </blockquote>
            );
          },

          hr() {
            return (
              <hr className="my-10 border-border" />
            );
          },

          img({ src, alt }) {
            return (
              <img
                src={src}
                alt={alt}
                className="my-8 rounded-2xl border shadow-md"
              />
            );
          },
        }}
      >
        {children}
      </ReactMarkdown>
    </article>
  );
}
