import { MessageSquare } from "lucide-react";


export default function ConversationItem({
  conversation,
  onClick,
  isActive,
}) {


  return (

    <button

      onClick={() =>
        onClick?.(conversation)
      }


      className={`
        group
        flex
        w-full
        items-center
        gap-3
        rounded-xl
        px-3
        py-3
        text-sm
        transition

        ${
          isActive
            ? "bg-accent font-semibold"
            : "hover:bg-accent"
        }
      `}

    >


      <MessageSquare

        className="
          h-4
          w-4
          shrink-0
          text-muted-foreground
        "

      />



      <span

        className="
          truncate
          text-left
        "

      >

        {
          conversation.title ||
          "New Conversation"
        }


      </span>


    </button>

  );

}