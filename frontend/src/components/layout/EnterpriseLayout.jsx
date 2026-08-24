import { useEffect, useState } from "react";
import { Link, Outlet, useLocation } from "react-router-dom";
import { Bell, CircleHelp, Menu, Search, Settings } from "lucide-react";
import Sidebar from "./Sidebar";
import useAuth from "../../hooks/useAuth";
import { pageTitle as titleForPage } from "../../config/product";
import api from "../../services/api";

export default function EnterpriseLayout() {
  const [sidebarCollapsed,setSidebarCollapsed]=useState(()=>window.localStorage.getItem("axiom.sidebar.collapsed")==="true"); const [mobileOpen,setMobileOpen]=useState(false); const location=useLocation();
  const [demoWorkspace,setDemoWorkspace]=useState(false);
  const {user}=useAuth();
  const displayName=user?.name||user?.givenName||user?.username||"Signed-in user";
  const initials=user?.initials||displayName.split(/\s+/).map(part=>part[0]).join("").slice(0,2).toUpperCase();
  const isChatPage=["/chat","/copilot"].some(path=>location.pathname===path||location.pathname.startsWith(`${path}/`));
  const pageName=location.pathname.includes("releases")?"Releases":location.pathname.includes("raid")?"RAID Intelligence":location.pathname.includes("copilot")||location.pathname.includes("chat")?"AI Copilot":location.pathname.includes("command")||location.pathname.includes("dashboard")?"Command Center":"Axiom Delivery AI";
  useEffect(()=>{document.title=titleForPage(pageName==="Axiom Delivery AI"?undefined:pageName);},[pageName]);
  useEffect(()=>{window.localStorage.setItem("axiom.sidebar.collapsed",String(sidebarCollapsed));},[sidebarCollapsed]);
  useEffect(()=>{const controller=new AbortController();api.get("/api/delivery/metadata",{signal:controller.signal}).then(response=>setDemoWorkspace(response.data?.workspace?.is_demo===true)).catch(()=>setDemoWorkspace(false));return()=>controller.abort();},[]);
  return <div className="flex h-screen min-h-0 w-full overflow-hidden bg-[#202020] text-stone-100">
    <div className="hidden h-screen shrink-0 lg:flex"><Sidebar collapsed={sidebarCollapsed} onCollapsedChange={setSidebarCollapsed}/></div>
    {mobileOpen&&<div className="fixed inset-0 z-50 flex bg-slate-950/50 lg:hidden" onMouseDown={(e)=>{if(e.target===e.currentTarget)setMobileOpen(false)}}><Sidebar mobile onNavigate={()=>setMobileOpen(false)} collapsed={false} onCollapsedChange={()=>{}}/></div>}
    <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden bg-slate-100">
      <header className="flex h-16 shrink-0 items-center justify-between border-b border-stone-300 bg-white px-4 text-stone-800 sm:px-6 lg:px-8"><div className="flex items-center gap-4"><button type="button" onClick={()=>setMobileOpen(true)} aria-label="Open navigation" className="rounded-sm p-2 text-stone-600 hover:bg-stone-100 focus:outline-none focus:ring-2 focus:ring-[#e0301e] lg:hidden"><Menu className="h-5 w-5"/></button><strong className="hidden font-display text-lg lg:block">{pageName}</strong>{demoWorkspace&&<span role="status" title="This workspace contains fictional demonstration data." className="border border-amber-400 bg-amber-50 px-2 py-1 text-xs font-semibold text-amber-900">Demo workspace</span>}<div className="hidden w-[min(340px,35vw)] items-center gap-2 border-b border-stone-300 px-1 py-2 sm:flex"><Search className="h-4 w-4 text-stone-400"/><input aria-label="Search Axiom Delivery AI" placeholder="Search delivery intelligence…" className="w-full bg-transparent text-sm outline-none placeholder:text-stone-400"/></div></div>
        <div className="flex items-center gap-1 sm:gap-2"><button type="button" aria-label="Help" className="rounded-sm p-2.5 text-stone-500 hover:bg-stone-100 focus:ring-2 focus:ring-[#e0301e]"><CircleHelp className="h-5 w-5"/></button><button type="button" aria-label="Notifications" className="rounded-sm p-2.5 text-stone-500 hover:bg-stone-100 focus:ring-2 focus:ring-[#e0301e]"><Bell className="h-5 w-5"/></button><Link to="/settings" aria-label="Profile settings" className="hidden items-center gap-3 border-l border-stone-300 pl-3 sm:flex"><div className="flex h-9 w-9 items-center justify-center bg-[#a00028] text-xs font-semibold text-white">{initials}</div><span className="text-left text-xs"><strong className="block text-stone-800">{displayName}</strong><span className="text-stone-500">Delivery lead</span></span><Settings className="h-4 w-4 text-stone-400"/></Link></div>
      </header>
      <main className={`min-h-0 min-w-0 flex-1 overflow-x-hidden bg-[#faf8f5] ${isChatPage?"overflow-hidden":"overflow-y-auto"}`}><div className={isChatPage?"h-full min-h-0":"min-h-full"}><Outlet/></div></main>
    </div>
  </div>;
}
