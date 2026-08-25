import {fireEvent,render,screen} from "@testing-library/react";
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

  it("tolerates an unavailable conversation collection",()=>{
    render(<ConversationSidebar conversation={conversation({conversations:undefined})}/>);
    expect(screen.getByText("No conversations found.")).toBeInTheDocument();
  });

  it("supports untitled records, filtering, selection, and new chat",()=>{
    const state=conversation({
      conversations:[
        {id:"one",title:null,updated_at:"2026-08-25T08:00:00Z",is_pinned:false},
        {id:"two",title:"Release readiness",updated_at:"2026-08-25T09:00:00Z",is_pinned:true},
      ],
    });
    render(<ConversationSidebar conversation={state}/>);
    fireEvent.click(screen.getByRole("button",{name:"New chat"}));
    expect(state.newChat).toHaveBeenCalledOnce();
    fireEvent.click(screen.getByText("Release readiness").closest("button"));
    expect(state.selectConversation).toHaveBeenCalledWith(expect.objectContaining({id:"two"}));
    fireEvent.change(screen.getByPlaceholderText("Search conversations…"),{target:{value:"untitled"}});
    expect(screen.getByText("Untitled conversation")).toBeInTheDocument();
    expect(screen.queryByText("Release readiness")).not.toBeInTheDocument();
  });
});
