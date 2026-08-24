import { useEffect, useRef } from "react";

import Message from "./Message";


export default function MessageList({
  messages = [],
}) {


  const messagesEndRef =
    useRef(null);



  // ---------------------------------------------
  // Auto scroll
  // ---------------------------------------------

  useEffect(() => {

    messagesEndRef.current?.scrollIntoView({
      behavior: "smooth",
      block: "end",
    });

  }, [
    messages,
  ]);



  // ---------------------------------------------
  // Empty State
  // ---------------------------------------------

  if (messages.length === 0) {

    return (

      <div
        className="
          flex
          h-full
          items-center
          justify-center
          px-8
        "
      >

        <div
          className="
            max-w-3xl
            text-center
          "
        >


          <h1
            className="
              mb-4
              text-4xl
              font-bold
              tracking-tight
            "
          >

            Axiom Delivery AI

          </h1>



          <p
            className="
              mb-10
              text-lg
              text-muted-foreground
            "
          >

            How can I help you today?

          </p>




          <div
            className="
              grid
              gap-4
              sm:grid-cols-2
            "
          >


            {[
              {
                title:"📄 Summarize Documents",
                text:
                "Upload files and receive concise summaries and key insights."
              },

              {
                title:"💻 Generate Code",
                text:
                "Create, explain, and improve code in multiple languages."
              },

              {
                title:"📊 Analyze Data",
                text:
                "Understand trends, metrics, reports, and dashboards."
              },

              {
                title:"✨ Generate Content",
                text:
                "Draft emails, user stories, PRDs, presentations, and more."
              }

            ].map((item)=>(

              <div
                key={item.title}
                className="
                  rounded-2xl
                  border
                  bg-card
                  p-5
                  text-left
                  transition
                  hover:shadow-md
                "
              >

                <h3
                  className="
                    mb-2
                    font-semibold
                  "
                >

                  {item.title}

                </h3>


                <p
                  className="
                    text-sm
                    text-muted-foreground
                  "
                >

                  {item.text}

                </p>


              </div>


            ))}


          </div>


        </div>


      </div>

    );

  }




  // ---------------------------------------------
  // Messages
  // ---------------------------------------------

  return (

    <div
      className="
        mx-auto
        flex
        w-full
        max-w-6xl
        flex-col
        gap-2
        px-6
        py-8
      "
    >


      {
        messages.map(
          (message)=>(

            <Message

              key={
                message.id || crypto.randomUUID()
              }

              message={
                message
              }

            />

          )
        )
      }



      <div
        ref={messagesEndRef}
      />


    </div>

  );

}
