import Avatar from "./Avatar";
import CopyButton from "./CopyButton";
import MarkdownRenderer from "./MarkdownRenderer";
import RuntimeExecutionCard from "./RuntimeExecutionCard";
import { formatRuntimeDuration, runtimeStatusPresentation } from "../../utils/runtimePresentation";
import StructuredDeliveryResponse from "../copilot/StructuredDeliveryResponse";
import MessageFeedback from "../copilot/MessageFeedback";



export default function AssistantMessage({
  message,
}) {


  const metadata =
    message.metadata || {};



  const content =
    message.content ||
    message.text ||
    "";



  const isWorkflow = Boolean(metadata.execution_id);

  const presentation=runtimeStatusPresentation[metadata.status]||{label:"Unknown",badge:"border-slate-400/20 bg-slate-400/10 text-slate-300"};
  const statusClass=presentation.badge;
  const structured=metadata.structured_response;





  return (

    <div
      className="
        group
        mb-10
        flex

        animate-in
        fade-in
        slide-in-from-bottom-2

        duration-300
      "
    >




      <div
        className="
          flex
          w-full
          max-w-6xl
          gap-5
        "
      >




        {/* AI Avatar */}

        <div
          className="
            mt-2
          "
        >

          <Avatar />

        </div>








        <div
          className="
            relative
            flex-1
          "
        >







          {/* Copy */}

          {
            content && (


              <div
                className="
                  absolute
                  right-4
                  top-4
                  z-10

                  opacity-0

                  transition

                  group-hover:opacity-100
                "
              >

                <CopyButton
                  text={content}
                />


              </div>


            )
          }










          {/* AI Response */}

          <div
            className="
              rounded-3xl

              border
              border-stone-300

              bg-white


              p-6


              shadow-sm


              text-stone-900


              ring-1

              ring-stone-200

            "
          >







            {/* Header */}


            <div
              className="
                mb-5

                flex

                items-center

                justify-between

              "
            >


              <div
                className="
                  flex
                  items-center
                  gap-3
                "
              >



                <div
                  className="
                    flex
                    h-8
                    w-8
                    items-center
                    justify-center

                    rounded-full

                    bg-gradient-to-br

                    from-blue-500

                    to-purple-500
                  "
                >

                  🤖

                </div>




                <div>


                  <p
                    className="
                      font-semibold
                    "
                  >

                    Axiom Delivery AI

                  </p>


                  <p
                    className="
                      text-xs
                      text-slate-400
                    "
                  >

                    AI Runtime Response

                  </p>


                </div>


              </div>







              {
                metadata.status && (


                  <span
                    className={`
                      rounded-full
                      border
                      px-3
                      py-1
                      text-xs
                      ${statusClass}
                    `}
                  >

                    ● {presentation.label}

                  </span>


                )
              }



            </div>









            {/* Runtime Execution */}

            {
              isWorkflow && (


                <div
                  className="
                    mb-6
                  "
                >

                  <RuntimeExecutionCard

                    metadata={
                      metadata
                    }

                  />

                </div>


              )
            }









            {/* Message Content */}


            {
              content && (!isWorkflow || metadata.status === "COMPLETED") && (


                <div
                  className={

                    isWorkflow

                    ?

                    "border-t border-stone-200 pt-6"

                    :

                    ""

                  }
                >


                  <MarkdownRenderer>

                    {content}

                  </MarkdownRenderer>


                </div>


              )
            }









            {/* Execution Summary */}

            {
              isWorkflow && (


                <div
                  className="
                    mt-6

                    grid

                    grid-cols-3

                    gap-4

                    rounded-2xl

                    border

                    border-stone-200

                    bg-[#faf8f5]

                    p-4
                  "
                >



                  <div>

                    <p
                      className="
                        text-xs
                        text-slate-400
                      "
                    >
                      Agent
                    </p>


                    <p>
                      {
                        metadata.agent ||
                        "AI Agent"
                      }
                    </p>

                  </div>





                  <div>

                    <p
                      className="
                        text-xs
                        text-slate-400
                      "
                    >
                      Duration
                    </p>


                    <p>
                      {
                        formatRuntimeDuration(metadata.duration_ms)
                      }
                    </p>

                  </div>





                  <div>

                    <p
                      className="
                        text-xs
                        text-slate-400
                      "
                    >
                      Workflow
                    </p>


                    <p
                      className="
                        truncate
                      "
                    >
                      {
                        metadata.workflow_id
                      }
                    </p>

                  </div>




                </div>


              )
            }





            <StructuredDeliveryResponse response={structured} onPropose={(action)=>globalThis.dispatchEvent(new CustomEvent("axiom:propose-action",{detail:{action,response:structured}}))}/>
            {content&&<MessageFeedback messageId={message.id}/>}
          </div>




        </div>




      </div>




    </div>


  );

}
