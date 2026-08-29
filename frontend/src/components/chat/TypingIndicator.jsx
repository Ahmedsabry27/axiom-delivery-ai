import Avatar from "./Avatar";

export default function TypingIndicator() {
  return (
    <div className="mb-10 flex animate-in fade-in slide-in-from-bottom-2 duration-300">
      <div className="flex w-full max-w-5xl gap-5">

        {/* AI Avatar */}
        <Avatar role="assistant" />

        {/* Thinking Bubble */}
        <div className="flex-1 rounded-sm border border-stone-200 bg-white px-8 py-6 shadow-sm">

          <div className="flex items-center gap-4">

            <div className="flex gap-2">
              <span
                className="h-2.5 w-2.5 animate-bounce rounded-full bg-[#a00028]"
                style={{ animationDelay: "0ms" }}
              />

              <span
                className="h-2.5 w-2.5 animate-bounce rounded-full bg-[#a00028]"
                style={{ animationDelay: "150ms" }}
              />

              <span
                className="h-2.5 w-2.5 animate-bounce rounded-full bg-[#a00028]"
                style={{ animationDelay: "300ms" }}
              />
            </div>

            <span className="text-sm text-muted-foreground animate-pulse">
              Axiom is thinking...
            </span>

          </div>
        </div>
      </div>
    </div>
  );
}
