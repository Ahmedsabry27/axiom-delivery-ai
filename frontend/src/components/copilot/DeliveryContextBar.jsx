import { X } from "lucide-react";
import { deliveryContexts } from "./deliveryContexts";

export default function DeliveryContextBar({selected,onChange}){
  const active=deliveryContexts.find(item=>item.id===selected);
  return <div className="flex flex-wrap items-center gap-3 border-b border-stone-300 bg-[#f4f1ed] px-4 py-2.5 text-stone-800"><label className="text-xs font-bold uppercase tracking-[.12em] text-stone-500">Delivery context <select aria-label="Delivery context" value={selected} onChange={event=>onChange(event.target.value)} className="ml-2 border border-stone-300 bg-white px-3 py-2 text-sm font-medium normal-case tracking-normal"><option value="">Organization-wide</option>{deliveryContexts.map(item=><option key={item.id} value={item.id}>{item.type}: {item.name}</option>)}</select></label>{active&&<span className="inline-flex items-center gap-2 border border-[#a00028]/20 bg-white px-3 py-1.5 text-xs font-semibold text-[#a00028]">{active.type}: {active.name}<button type="button" onClick={()=>onChange("")} aria-label="Clear delivery context"><X className="h-3.5 w-3.5"/></button></span>}<p className="ml-auto hidden text-xs text-stone-500 md:block">Context is retained with follow-up questions</p></div>;
}
