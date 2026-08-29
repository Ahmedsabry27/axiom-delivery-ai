import Avatar from "./Avatar";
import CopyButton from "./CopyButton";
import MarkdownRenderer from "./MarkdownRenderer";
import InlineRuntimeActivity from "./InlineRuntimeActivity";
import StructuredDeliveryResponse from "../copilot/StructuredDeliveryResponse";
import MessageFeedback from "../copilot/MessageFeedback";

export default function AssistantMessage({message}){
 const metadata=message.metadata||{};
 const content=message.content||message.text||"";
 const structured=metadata.structured_response;
 return <article className="group mb-8 flex" aria-label="Axiom Delivery AI message">
  <div className="flex w-full max-w-6xl gap-3">
   <div className="mt-0.5 shrink-0"><Avatar/></div>
   <div className="min-w-0 flex-1">
    <header className="mb-2 flex items-center justify-between gap-3">
     <div><p className="text-sm font-semibold text-stone-900">Axiom Delivery AI</p>{metadata.execution_id&&<p className="text-xs text-stone-500">Governed delivery assistant</p>}</div>
     {content&&<div className="opacity-0 transition group-hover:opacity-100 focus-within:opacity-100"><CopyButton text={content}/></div>}
    </header>
    <InlineRuntimeActivity metadata={metadata}/>
    {content&&(!metadata.execution_id||metadata.status==="COMPLETED")&&<div className="rounded-lg border border-stone-200 bg-white p-5 text-stone-900 shadow-sm"><MarkdownRenderer>{content}</MarkdownRenderer></div>}
    <StructuredDeliveryResponse response={structured} onPropose={(action)=>globalThis.dispatchEvent(new CustomEvent("axiom:propose-action",{detail:{action,response:structured}}))}/>
    {content&&<MessageFeedback messageId={message.id}/>}
   </div>
  </div>
 </article>;
}
