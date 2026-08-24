import {CheckCircle2,Clock3,Cloud} from "lucide-react";
import {Link} from "react-router-dom";

export default function IntegrationCatalog({items=[],onConfigure}){
  return <div className="integration-grid">{items.map(item=>{
    const configurable=["available","beta"].includes(item.implementation_status)&&item.type!=="mcp";
    return <article className="integration-card catalog" key={item.type}><div className="integration-title"><span className="tool-icon"><Cloud/></span><div><h2>{item.name}</h2><small>{item.category}</small></div></div><p>{item.description}</p><p><strong>{item.availability||"PLANNED"}</strong> · {item.maturity||"Definition only"}</p><p className="catalog-auth">Auth: {(item.auth_methods||[]).join(", ").replaceAll("_"," ")}</p><p>Direction: {(item.supported_direction||[]).join(", ")||"Not implemented"}</p>{item.read_capabilities!=null&&<p>{item.read_capabilities} read · {item.write_capabilities} write capabilities</p>}{item.setup_route?<Link className="primary-button" to={item.setup_route}><CheckCircle2 size={14}/> Open MCP workspace</Link>:<button className={configurable?"primary-button":"outline-button"} disabled={!configurable} onClick={()=>onConfigure(item)}>{configurable?<><CheckCircle2 size={14}/> Configure {item.availability==="BETA"?"beta":""}</>:<><Clock3 size={14}/> {item.availability||"PLANNED"}</>}</button>}</article>})}</div>;
}
