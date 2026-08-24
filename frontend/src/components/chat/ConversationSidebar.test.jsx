import {render,screen} from "@testing-library/react";
import {describe,expect,it,vi} from "vitest";

import ConversationSidebar from "./ConversationSidebar";

const conversation=(changes={})=>({
  conversations:[],loading:false,error:null,conversationId:null,
  newChat:vi.fn(),selectConversation:vi.fn(),renameConversation:vi.fn(),
  togglePinned:vi.fn(),removeConversation:vi.fn(),...changes,
});

describe("ConversationSidebar states",()=>{
  it("shows an empty state only after a successful empty response",()=>{
    render(<ConversationSidebar conversation={conversation()}/>);
    expect(screen.getByText("No conversations found.")).toBeInTheDocument();
  });

  it("does not present an API failure as an empty successful list",()=>{
    render(<ConversationSidebar conversation={conversation({
      error:"Conversations could not be loaded.",
    })}/>);
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Conversations could not be loaded.",
    );
    expect(screen.queryByText("No conversations found.")).not.toBeInTheDocument();
  });
});
