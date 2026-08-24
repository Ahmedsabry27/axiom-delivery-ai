"""Create Jira-native portfolio hubs, programme categories, and delivery projects."""
from __future__ import annotations
import httpx
from app.database.models.integration import IntegrationConnection
from app.database.session import SessionLocal
from app.integrations.secrets import secret_provider

HIERARCHY=[
 {"portfolio":{"key":"DGPORT","name":"Digital Growth Portfolio","theme":"Revenue growth and differentiated digital customer experiences"},"programmes":[
   {"name":"Commerce Modernisation Programme","projects":[("COMAI","Commerce AI","AI-assisted product discovery and conversion"),("DPAY","Digital Payments","Modern resilient payment journeys")]},
   {"name":"Customer Engagement Programme","projects":[("PERS","Personalisation Engine","Real-time governed personalisation"),("LOYAI","Loyalty Intelligence","Predictive loyalty and retention intelligence")]},
 ]},
 {"portfolio":{"key":"EOPORT","name":"Enterprise Operations Portfolio","theme":"Operational resilience, productivity, and intelligent automation"},"programmes":[
   {"name":"Cloud and Data Platform Programme","projects":[("CLDFN","Cloud Foundation","Secure cloud landing zones and platform services"),("DATINT","Data Intelligence Platform","Trusted data products and analytics foundation")]},
   {"name":"Intelligent Operations Programme","projects":[("SOAI","Service Operations AI","AI-assisted IT service operations"),("FINAUT","Finance Automation","Governed finance workflow automation")]},
 ]},
]
def require(response,operation,accepted=(200,201,204)):
    if response.status_code not in accepted:
        try: body=response.json();messages=body.get("errorMessages") or list((body.get("errors") or {}).values())
        except ValueError: messages=[]
        raise RuntimeError(f"{operation} failed ({response.status_code}): {'; '.join(map(str,messages)) or 'Provider rejected request'}")
    return response.json() if response.content else {}
def main():
 db=SessionLocal()
 try:
  connection=db.query(IntegrationConnection).filter_by(tenant_id="axiom-demo",connector_type="jira").one();credential=secret_provider.resolve(connection.secret_ref)
  with httpx.Client(base_url=connection.base_url,auth=(credential["email"],credential["api_token"]),headers={"Accept":"application/json","Content-Type":"application/json"},timeout=30,follow_redirects=False) as client:
   me=require(client.get("/rest/api/3/myself"),"Account lookup");categories=require(client.get("/rest/api/3/projectCategory"),"Category lookup");category_map={x["name"]:x for x in categories}
   created={"portfolios":0,"programmes":0,"projects":0}
   for group in HIERARCHY:
    portfolio=group["portfolio"]
    response=client.get(f"/rest/api/3/project/{portfolio['key']}")
    if response.status_code==404:
     require(client.post("/rest/api/3/project",json={"key":portfolio["key"],"name":portfolio["name"],"projectTypeKey":"software","projectTemplateKey":"com.pyxis.greenhopper.jira:gh-kanban-template","description":portfolio["theme"],"leadAccountId":me["accountId"],"assigneeType":"PROJECT_LEAD"}),f"Create portfolio hub {portfolio['key']}");created["portfolios"]+=1
    require(client.put(f"/rest/api/3/project/{portfolio['key']}/properties/axiom-hierarchy",json={"entityType":"PORTFOLIO","portfolioKey":portfolio["key"],"portfolioName":portfolio["name"],"strategicTheme":portfolio["theme"]}),f"Set portfolio property {portfolio['key']}")
    for programme in group["programmes"]:
     category=category_map.get(programme["name"])
     if not category:
      category=require(client.post("/rest/api/3/projectCategory",json={"name":programme["name"],"description":f"Programme within {portfolio['name']}"}),f"Create programme {programme['name']}");category_map[programme["name"]]=category;created["programmes"]+=1
     for key,name,description in programme["projects"]:
      response=client.get(f"/rest/api/3/project/{key}")
      if response.status_code==404:
       require(client.post("/rest/api/3/project",json={"key":key,"name":name,"projectTypeKey":"software","projectTemplateKey":"com.pyxis.greenhopper.jira:gh-scrum-template","description":description,"categoryId":int(category["id"]),"leadAccountId":me["accountId"],"assigneeType":"PROJECT_LEAD"}),f"Create project {key}");created["projects"]+=1
      require(client.put(f"/rest/api/3/project/{key}/properties/axiom-hierarchy",json={"entityType":"PROJECT","portfolioKey":portfolio["key"],"portfolioName":portfolio["name"],"programmeId":str(category["id"]),"programmeName":programme["name"],"projectKey":key,"projectName":name,"strategicTheme":portfolio["theme"]}),f"Set hierarchy property {key}")
      print(f"Ready: {portfolio['name']} > {programme['name']} > {name} ({key})")
   print(f"Jira portfolio hierarchy ready: {created}")
 finally:db.close()
if __name__=="__main__":main()
