export default function WorkflowResultCard({
  metadata = {},
}) {


  const steps = [

    {
      title: "Request Received",
      status: "completed",
      description:
        "User goal captured",
    },


    {
      title: "Planner",
      status: "completed",
      description:
        "Execution plan generated",
    },


    {
      title: "Agent Execution",
      status: "completed",
      description:
        metadata.agent ||
        "default-agent",
    },


    {
      title: "Task Completion",
      status:
        metadata.tasks_failed > 0
          ? "failed"
          : "completed",

      description:
        `${metadata.tasks_completed || 0}/${metadata.tasks_total || 0} tasks completed`,
    },


    {
      title: "Final Result",
      status:
        metadata.status === "COMPLETED"
          ? "completed"
          : "failed",

      description:
        metadata.status,
    },

  ];



  return (

    <div
      className="
      mb-6
      rounded-2xl
      border
      bg-gray-50
      p-6
      "
    >



      {/* Header */}

      <div
        className="
        mb-6
        flex
        items-center
        justify-between
        "
      >

        <div>

          <h3
            className="
            font-semibold
            text-lg
            "
          >

            Axiom Runtime

          </h3>


          <p
            className="
            text-sm
            text-muted-foreground
            "
          >

            Workflow Execution Trace

          </p>


        </div>




        <span
          className={`
            rounded-full
            px-3
            py-1
            text-sm
            font-medium

            ${
              metadata.status === "COMPLETED"

              ?
              "bg-green-100 text-green-700"

              :

              "bg-red-100 text-red-700"

            }
          `}
        >

          {metadata.status || "UNKNOWN"}

        </span>


      </div>





      {/* Timeline */}

      <div
        className="
        space-y-5
        "
      >

        {
          steps.map(
            (step,index)=>(

              <div
                key={step.title}
                className="
                flex
                gap-4
                "
              >


                {/* Step Icon */}

                <div
                  className="
                  flex
                  flex-col
                  items-center
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
                    bg-green-100
                    text-green-700
                    "
                  >

                    ✓

                  </div>


                  {
                    index !== steps.length - 1 && (

                      <div
                        className="
                        h-full
                        w-px
                        bg-gray-300
                        "
                      />

                    )
                  }


                </div>





                {/* Step Content */}

                <div>

                  <p
                    className="
                    font-medium
                    "
                  >

                    {step.title}

                  </p>


                  <p
                    className="
                    text-sm
                    text-muted-foreground
                    "
                  >

                    {step.description}

                  </p>


                </div>



              </div>


            )
          )
        }


      </div>





      {/* Metrics */}

      <div
        className="
        mt-6
        grid
        grid-cols-3
        gap-4
        border-t
        pt-5
        text-sm
        "
      >


        <div>

          <p className="text-muted-foreground">
            Tasks
          </p>

          <p className="font-semibold">

            {metadata.tasks_completed || 0}

            /

            {metadata.tasks_total || 0}

          </p>

        </div>




        <div>

          <p className="text-muted-foreground">
            Duration
          </p>

          <p className="font-semibold">

            {metadata.duration_ms || 0} ms

          </p>

        </div>





        <div>

          <p className="text-muted-foreground">
            Agent
          </p>

          <p
            className="
            truncate
            font-semibold
            "
          >

            {metadata.agent || "default-agent"}

          </p>

        </div>


      </div>





      {/* Workflow ID */}

      {
        metadata.workflow_id && (

          <div
            className="
            mt-5
            rounded-lg
            bg-white
            p-3
            text-xs
            text-muted-foreground
            "
          >

            Workflow ID:

            <span
              className="
              ml-2
              break-all
              "
            >

              {metadata.workflow_id}

            </span>


          </div>

        )
      }


    </div>

  );

}
