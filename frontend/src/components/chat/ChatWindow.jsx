import { useEffect, useRef, useState } from "react";

import EmptyState from "./EmptyState";
import MessageList from "./MessageList";
import TypingIndicator from "./TypingIndicator";

export default function ChatWindow({
  messages = [],
  loading = false,
  onPromptClick,
}) {
  const bottomRef = useRef(null);
  const scrollRef = useRef(null);

  const [newActivity, setNewActivity] = useState(false);
  const hasInlineRuntime = messages.some((message) => message.metadata?.execution_id);

  // -----------------------------------------
  // Auto Scroll
  // -----------------------------------------

  useEffect(() => {
    const node = scrollRef.current;

    const nearBottom =
      !node ||
      node.scrollHeight -
        node.scrollTop -
        node.clientHeight <
        120;

    if (nearBottom) {
      bottomRef.current?.scrollIntoView({
        behavior: "smooth",
        block: "end",
      });
    } else {
      setNewActivity(true);
    }
  }, [messages, loading]);

  return (
    <div
      className="
        flex
        min-h-0
        flex-1
        flex-col
        overflow-hidden
      "
    >
      {/* -------------------------------------
          Conversation Area
      ------------------------------------- */}

      <div
        ref={scrollRef}
        onScroll={(e) => {
          const node = e.currentTarget;

          const nearBottom =
            node.scrollHeight -
              node.scrollTop -
              node.clientHeight <
            120;

          if (nearBottom) {
            setNewActivity(false);
          }
        }}
        className="
          min-h-0
          flex-1
          overflow-y-auto
          overflow-x-hidden
          px-4
          pb-8
          pt-8
          scrollbar-thin
          scrollbar-track-transparent
          bg-[#faf8f5]
          text-stone-900
          scrollbar-thumb-stone-300
        "
      >
        {messages.length === 0 ? (
          <div
            className="
              flex
              min-h-full
              items-center
              justify-center
              animate-in
              fade-in
              duration-500
            "
          >
            <EmptyState onPromptClick={onPromptClick} />
          </div>
        ) : (
          <div
            className="
              mx-auto
              w-full
              max-w-6xl
              space-y-6
            "
          >
            <MessageList messages={messages} />
          </div>
        )}

        {/* -------------------------------------
            Runtime Loading
        ------------------------------------- */}

        {loading && !hasInlineRuntime && (
          <div
            className="
              mx-auto
              mt-6
              w-full
              max-w-6xl
            "
          >
            <TypingIndicator />
          </div>
        )}

        {/* Scroll Anchor */}

        <div ref={bottomRef} />

        {newActivity && (
          <button
            onClick={() => {
              bottomRef.current?.scrollIntoView({
                behavior: "smooth",
                block: "end",
              });

              setNewActivity(false);
            }}
            className="
              sticky
              bottom-3
              mx-auto
              mt-3
              block
              rounded-full
              border
              border-violet-400/30
              bg-slate-900
              px-4
              py-2
              text-xs
              text-violet-200
              shadow-xl
            "
            aria-label="Scroll to new activity"
          >
            ↓ New activity
          </button>
        )}
      </div>
    </div>
  );
}
