import {useState} from "react";
import {ShieldCheck,X} from "lucide-react";
import {useIntegrationActions} from "../../hooks/useIntegrations";

const steps=["Connector","Details","Authentication","Test","Discover","Capabilities","Governance","Agents","Review"];

function apiMessage(error){
  const detail=error.response?.data?.detail;
  if(Array.isArray(detail)) return detail.map(item=>item.msg).join(". ");
  return detail?.message||detail?.code||error.message||"Request failed";
}

export default function AddIntegrationWizard({connector,onClose,onComplete}){
  const [step,setStep]=useState(0),[created,setCreated]=useState(null),[message,setMessage]=useState("");
  const [form,setForm]=useState({connector_type:connector.type,display_name:`${connector.name} Production`,description:"",base_url:"",auth_type:"api_token",credential_email:"",credential_token:"",configuration:{},enabled:false});
  const actions=useIntegrationActions(created?.id),update=(key,value)=>setForm(current=>({...current,[key]:value}));
  const next=async()=>{setMessage("");try{if(step===2&&!created){const value=await actions.create.mutateAsync(form);setCreated(value);setForm(current=>({...current,credential_token:""}))}else if(step===3)await actions.test.mutateAsync(created.id);else if(step===4)await actions.discover.mutateAsync(created.id);if(step===8){onComplete(created);return}setStep(current=>current+1)}catch(error){setMessage(apiMessage(error))}};
  const pending=actions.create.isPending||actions.test.isPending||actions.discover.isPending;
  return <div className="drawer-backdrop"><aside className="integration-wizard"><button className="drawer-close" onClick={onClose}><X/></button><h2>Add {connector.name}</h2><div className="integration-stepper">{steps.map((name,index)=><span key={name} className={index===step?"active":index<step?"done":""}>{index+1}<small>{name}</small></span>)}</div><div className="wizard-body">
    {step===0&&<><h3>Connector selected</h3><div className="connector-choice"><strong>{connector.name}</strong><span>{connector.description}</span></div></>}
    {step===1&&<><h3>Connection details</h3><label>Display name<input value={form.display_name} onChange={event=>update("display_name",event.target.value)}/></label><label>Jira site URL<input value={form.base_url} onChange={event=>update("base_url",event.target.value)} placeholder="https://company.atlassian.net"/><small>Include https:// and use your Atlassian site hostname.</small></label><label>Description<textarea value={form.description} onChange={event=>update("description",event.target.value)}/></label></>}
    {step===2&&<><h3>Jira API-token authentication</h3><label>Atlassian account email<input type="email" autoComplete="username" value={form.credential_email} onChange={event=>update("credential_email",event.target.value)} placeholder="automation@company.com"/></label><label>Jira API token<input type="password" autoComplete="new-password" value={form.credential_token} onChange={event=>update("credential_token",event.target.value)} placeholder="Paste a newly generated Jira API token"/><small>The token is sent once to the backend and stored in AWS Secrets Manager. It is never returned or stored in the integration database.</small></label><p className="secure-note"><ShieldCheck size={15}/> OAuth 2.0 3LO is not enabled yet.</p></>}
    {step===3&&<Status title="Test connection" text="This makes a real authenticated Jira REST API request." pending={actions.test.isPending}/>}{step===4&&<Status title="Discover capabilities" text="Retrieve accessible Jira projects and executable capabilities." pending={actions.discover.isPending}/>}{step===5&&<Status title="Select capabilities" text="Enable and provision capabilities from the connection detail workspace."/>}{step===6&&<Status title="Governance defaults" text="Read tools default to low risk. Write actions carry governed risk and approvals."/>}{step===7&&<Status title="Agent assignment" text="Assign enabled capabilities to tenant-scoped agents from the detail workspace."/>}{step===8&&<div className="wizard-review"><h3>Review & enable</h3><p><strong>{form.display_name}</strong></p><p>{form.base_url}</p><p>API token · stored in AWS Secrets Manager</p></div>}
    {message&&<p className="integration-error" role="alert">{message}</p>}
  </div><div className="wizard-actions"><button className="outline-button" disabled={step===0||!!created} onClick={()=>setStep(current=>current-1)}>Back</button><button className="primary-button" disabled={(step===1&&!form.base_url)||(step===2&&(!form.credential_email||!form.credential_token))||pending} onClick={next}>{step===8?"Open connection":step===2?"Save securely":step===3?"Run test":step===4?"Discover":"Continue"}</button></div></aside></div>
}

function Status({title,text,pending}){return <div className="status-step"><h3>{pending?`${title}…`:title}</h3><p>{text}</p></div>}
