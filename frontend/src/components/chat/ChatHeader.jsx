export default function ChatHeader({runtime}){
 return <header className="flex items-center gap-3 border-b border-stone-300 bg-white px-5 py-3 text-stone-900">
  <div className="mr-auto">
   <p className="text-[10px] font-bold uppercase tracking-[.18em] text-[#a00028]">Evidence-led delivery</p>
   <h1 className="font-display text-xl font-bold">Axiom AI Delivery Copilot</h1>
   <p className="text-xs text-stone-500">Ask, investigate, and prepare controlled actions</p>
  </div>
  {runtime?.selectedAgent&&<p className="hidden text-xs text-stone-500 lg:block">Using <span className="font-medium text-stone-800">{runtime.selectedAgent.name}</span></p>}
  <div className="border border-emerald-700/20 bg-emerald-50 px-3 py-2 text-xs font-medium text-emerald-800"><span aria-hidden="true">●</span> Runtime online</div>
 </header>;
}
