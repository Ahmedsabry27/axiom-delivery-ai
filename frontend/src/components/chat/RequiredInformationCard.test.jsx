import {fireEvent,render,screen} from "@testing-library/react";
import {describe,expect,it,vi} from "vitest";
import RequiredInformationCard from "./RequiredInformationCard";

const request={continuation_id:"continuation-1",title:"Additional information required",description:"I need details.",fields:[{name:"project_name",label:"Project",type:"text",required:true},{name:"environment",label:"Environment",type:"select",required:true,options:["staging","production"]}]};

describe("RequiredInformationCard",()=>{
  it("renders schema fields and blocks invalid submission",async()=>{
    const submit=vi.fn();render(<RequiredInformationCard request={request} onSubmit={submit} onCancel={()=>{}}/>);
    expect(screen.getByRole("heading",{name:"Additional information required"})).toHaveFocus();
    fireEvent.click(screen.getByRole("button",{name:/submit details/i}));
    expect(await screen.findByRole("alert")).toHaveTextContent("Complete the marked required fields");
    expect(submit).not.toHaveBeenCalled();
  });

  it("submits values to resume the same continuation",async()=>{
    const submit=vi.fn().mockResolvedValue(undefined);render(<RequiredInformationCard request={request} onSubmit={submit} onCancel={()=>{}}/>);
    fireEvent.change(screen.getByLabelText(/Project/),{target:{value:"Phoenix"}});
    fireEvent.change(screen.getByLabelText(/Environment/),{target:{value:"production"}});
    fireEvent.click(screen.getByRole("button",{name:/submit details/i}));
    expect(submit).toHaveBeenCalledWith({project_name:"Phoenix",environment:"production"});
  });

  it("renders durable server feedback when input remains unresolved",()=>{
    render(<RequiredInformationCard request={{
      continuation_id:"continuation-2",fields:[{name:"issue_type",label:"Issue Type",type:"text",required:true}],
      validation_feedback:{invalid_fields:["issue_type"],unresolved_fields:[],warnings:["Use a supported issue type."]},
    }} onSubmit={()=>{}} onCancel={()=>{}}/>);
    expect(screen.getByText("Enter a valid value for this field.")).toBeInTheDocument();
    expect(screen.getByText("Use a supported issue type.")).toBeInTheDocument();
  });

  it("renders canonical Jira-create fields identically for SSE and refresh snapshots",()=>{
    const fields=[
      {name:"project_key",label:"Project Key",type:"text",required:true},
      {name:"issue_type",label:"Issue Type",type:"text",required:true},
      {name:"summary",label:"Summary",type:"text",required:true},
    ];
    const initial={
      continuation_id:"jira-create-1",intent:"jira.issue.create",fields,
      title:"Jira Issue details required",
    };
    const {rerender}=render(
      <RequiredInformationCard request={initial} onSubmit={()=>{}} onCancel={()=>{}}/>,
    );
    expect(screen.getByLabelText(/Project Key/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Issue Type/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Summary/)).toBeInTheDocument();
    expect(screen.queryByText(/Jira report scope/i)).not.toBeInTheDocument();

    const restored={...initial,requested_fields:["project_key","issue_type","summary"]};
    rerender(
      <RequiredInformationCard request={restored} onSubmit={()=>{}} onCancel={()=>{}}/>,
    );
    expect(screen.getAllByRole("textbox")).toHaveLength(3);
    expect(screen.queryByText(/Jira report scope/i)).not.toBeInTheDocument();
  });
});
