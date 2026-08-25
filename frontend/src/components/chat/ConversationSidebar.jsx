import { useMemo, useState } from "react";
import {
  MoreHorizontal,
  Pin,
  PinOff,
  Plus,
  Search,
  Trash2,
} from "lucide-react";

export default function ConversationSidebar({ conversation }) {
  const [query, setQuery] = useState("");
  const [menu, setMenu] = useState(null);
  const [renaming, setRenaming] = useState(null);

  const items = useMemo(
    () =>
      (Array.isArray(conversation.conversations) ? conversation.conversations : []).filter((item) =>
        String(item.title || "Untitled conversation").toLowerCase().includes(query.toLowerCase())
      ),
    [conversation.conversations, query]
  );

  const groups = [
    {
      title: "Pinned",
      items: items.filter((item) => item.is_pinned),
    },
    {
      title: "Recent",
      items: items.filter((item) => !item.is_pinned),
    },
  ];

  return (
    <aside
      className="
        hidden
        h-full
        min-h-0
        w-64
        shrink-0
        overflow-hidden
        border-r
        border-stone-300
        bg-[#f4f1ed]
        text-stone-900
        lg:flex
        lg:flex-col
      "
    >
      {/* Fixed header */}
      <div className="flex shrink-0 items-center justify-between border-b border-stone-300 bg-white p-4">
        <div>
          <h2 className="font-semibold">Conversations</h2>
          <p className="text-xs text-slate-500">Runtime history</p>
        </div>

        <button
          onClick={conversation.newChat}
          className="rounded-sm bg-[#a00028] p-2 text-white transition hover:bg-[#7d001f] focus:outline-none focus:ring-2 focus:ring-[#ffb600]"
          aria-label="New chat"
        >
          <Plus size={17} />
        </button>
      </div>

      {/* Fixed search */}
      <label className="m-3 flex shrink-0 items-center gap-2 border border-stone-300 bg-white px-3 py-2 focus-within:border-[#a00028]">
        <Search size={15} className="text-slate-500" />

        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="min-w-0 flex-1 bg-transparent text-sm text-stone-900 outline-none placeholder:text-stone-500"
          placeholder="Search conversations…"
        />
      </label>

      {/* Scrollable conversations */}
      <div
        className="
          min-h-0
          flex-1
          overflow-y-auto
          overflow-x-hidden
          px-2
          pb-3
        "
      >
        {conversation.loading && (
          <p className="p-3 text-sm text-slate-500">
            Loading conversations…
          </p>
        )}

        {conversation.error && (
          <p role="alert" className="m-2 border border-rose-300 bg-rose-50 p-3 text-sm text-rose-800">
            {conversation.error}
          </p>
        )}

        {!conversation.loading && !conversation.error && !items.length && (
          <p className="p-3 text-sm text-slate-500">
            No conversations found.
          </p>
        )}

        {groups.map(
          (group) =>
            group.items.length > 0 && (
              <section key={group.title}>
                <p className="px-3 pb-1 pt-3 text-[10px] font-medium uppercase tracking-widest text-slate-600">
                  {group.title}
                </p>

                {group.items.map((item) => (
                  <div
                    key={item.id}
                    className={`group relative mb-1 ${
                      conversation.conversationId === item.id
                        ? "bg-[#a00028] text-white"
                        : "hover:bg-white"
                    }`}
                  >
                    {renaming === item.id ? (
                      <form
                        className="p-2"
                        onSubmit={async (e) => {
                          e.preventDefault();

                          const title = new FormData(
                            e.currentTarget
                          ).get("title");

                          await conversation.renameConversation(
                            item.id,
                            String(title)
                          );

                          setRenaming(null);
                        }}
                      >
                        <input
                          name="title"
                          autoFocus
                          defaultValue={item.title}
                          className="w-full border border-[#a00028] bg-white px-2 py-1 text-sm text-stone-900 outline-none"
                          onBlur={() => setRenaming(null)}
                        />
                      </form>
                    ) : (
                      <button
                        onClick={() =>
                          conversation.selectConversation(item)
                        }
                        className="w-full px-3 py-3 pr-9 text-left"
                      >
                        <p className={`truncate text-sm font-medium ${conversation.conversationId === item.id ? "text-white" : "text-stone-800"}`}>
                          {item.title || "Untitled conversation"}
                        </p>

                        <p className={`mt-1 text-[10px] ${conversation.conversationId === item.id ? "text-white/70" : "text-stone-500"}`}>
                          {new Date(
                            item.updated_at
                          ).toLocaleString()}
                        </p>
                      </button>
                    )}

                    <button
                      aria-label={`Conversation actions for ${item.title || "Untitled conversation"}`}
                      onClick={() =>
                        setMenu(menu === item.id ? null : item.id)
                      }
                      className={`absolute right-2 top-3 hidden p-1 group-hover:block ${conversation.conversationId === item.id ? "text-white" : "text-stone-500"}`}
                    >
                      <MoreHorizontal size={15} />
                    </button>

                    {menu === item.id && (
                      <div className="absolute right-2 top-9 z-20 w-36 border border-stone-300 bg-white p-1 text-xs text-stone-800 shadow-xl">
                        <button
                          onClick={() => {
                            setRenaming(item.id);
                            setMenu(null);
                          }}
                          className="block w-full px-2 py-2 text-left hover:bg-stone-100"
                        >
                          Rename
                        </button>

                        <button
                          onClick={() => {
                            conversation.togglePinned(
                              item.id,
                              item.is_pinned
                            );
                            setMenu(null);
                          }}
                          className="flex w-full items-center gap-2 px-2 py-2 hover:bg-stone-100"
                        >
                          {item.is_pinned ? (
                            <PinOff size={13} />
                          ) : (
                            <Pin size={13} />
                          )}

                          {item.is_pinned ? "Unpin" : "Pin"}
                        </button>

                        <button
                          onClick={() =>
                            conversation.removeConversation(item.id)
                          }
                          className="flex w-full items-center gap-2 px-2 py-2 text-red-700 hover:bg-red-50"
                        >
                          <Trash2 size={13} />
                          Delete
                        </button>
                      </div>
                    )}
                  </div>
                ))}
              </section>
            )
        )}
      </div>
    </aside>
  );
}
