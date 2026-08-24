import { useState, useEffect, useRef } from "react";
import { Paperclip, SendHorizontal } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

import { sendMessage } from "@/services/chat";
import { createConversation } from "@/services/conversationService";


export default function Composer({
  setMessages,
  loading,
  setLoading,
  conversationId,
  setConversationId,
  refreshConversations,
}) {


  const [message, setMessage] = useState("");

  const textareaRef = useRef(null);



  useEffect(() => {

    textareaRef.current?.focus();

  }, [conversationId]);



  const autoResize = (element) => {

    element.style.height = "auto";

    element.style.height =
      `${Math.min(element.scrollHeight, 220)}px`;

  };




  const handleSend = async () => {


    if (!message.trim() || loading) {
      return;
    }


    const prompt = message.trim();



    // -----------------------------
    // Add User Message Immediately
    // -----------------------------

    const userMessage = {

      id: crypto.randomUUID(),

      role: "user",

      content: prompt,
      text:prompt,

      timestamp:
        new Date().toISOString(),

    };


    setMessages(prev => [
      ...prev,
      userMessage,
    ]);



    setMessage("");



    if (textareaRef.current) {

      textareaRef.current.style.height =
        "70px";

    }



    setLoading(true);



    try {


      let currentConversationId =
        conversationId;



      // -----------------------------
      // Create Conversation
      // -----------------------------

      if (!currentConversationId) {


        const title =
          prompt
            .replace(/\s+/g, " ")
            .trim()
            .slice(0, 60);



        const conversation =
          await createConversation(
            title
          );



        currentConversationId =
          conversation.id;



        setConversationId(
          currentConversationId
        );


        if (refreshConversations) {

          await refreshConversations();

        }

      }




      // -----------------------------
      // Execute Runtime
      // -----------------------------

      const response =
        await sendMessage(
          prompt,
          currentConversationId
        );




      // -----------------------------
      // Axiom Response
      // -----------------------------

      const assistantMessage = {

        id:
          crypto.randomUUID(),


        role:
          "assistant",


        content:
          response.message ??
          response.output ??
          "Workflow completed successfully.",



        metadata: {

          conversationId:
            response.conversation_id,


          agent:
            response.agent ??
            "default-agent",


          actions:
            response.actions ?? [],


          status:
            response.status ??
            "completed",


          timestamp:
            response.timestamp,

        },

      };




      setMessages(prev => [

        ...prev,

        assistantMessage,

      ]);



      // Refresh sidebar with new conversation

      if (refreshConversations) {

        await refreshConversations();

      }



    } catch(error) {


      console.error(
        "Axiom runtime error:",
        error
      );



      setMessages(prev => [

        ...prev,


        {

          id:
            crypto.randomUUID(),


          role:
            "assistant",


          content:
            "❌ Axiom runtime failed. Please try again.",


          metadata: {

            status:
              "failed",

          },

        },

      ]);



    } finally {


      setLoading(false);


      textareaRef.current?.focus();


    }

  };





  const handleKeyDown = (event) => {


    if (
      event.key === "Enter" &&
      !event.shiftKey
    ) {

      event.preventDefault();

      handleSend();

    }

  };





  return (

    <div className="sticky bottom-0 z-20 border-t bg-background/80 backdrop-blur-xl">


      <div className="mx-auto max-w-6xl px-6 py-5">


        <div
          className="
            rounded-[28px]
            border
            bg-card
            shadow-lg
            transition-all
            duration-200
            focus-within:border-emerald-500
          "
        >


          <Textarea

            ref={textareaRef}

            value={message}

            rows={1}

            disabled={loading}

            placeholder="Message Axiom..."

            onKeyDown={handleKeyDown}


            onChange={(e)=>{

              setMessage(
                e.target.value
              );

              autoResize(
                e.target
              );

            }}


            className="
              min-h-[70px]
              max-h-[220px]
              resize-none
              overflow-y-auto
              border-0
              bg-transparent
              px-6
              pt-5
              pb-3
              text-base
              leading-7
              shadow-none
              focus-visible:ring-0
            "

          />



          <div className="flex items-center justify-between px-4 pb-4">


            <div className="flex items-center gap-2">


              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="rounded-xl"
              >

                <Paperclip className="h-5 w-5"/>

              </Button>



              <span className="hidden text-sm text-muted-foreground md:block">

                Press Enter to send • Shift + Enter for new line

              </span>


            </div>





            <div className="flex items-center gap-4">


              {loading && (

                <span className="animate-pulse text-sm text-muted-foreground">

                  Axiom is executing workflow...

                </span>

              )}



              <Button

                type="button"

                size="icon"

                onClick={handleSend}

                disabled={
                  !message.trim() ||
                  loading
                }


                className="
                  h-12
                  w-12
                  rounded-full
                  bg-emerald-600
                  shadow-md
                  hover:bg-emerald-700
                "

              >

                <SendHorizontal className="h-5 w-5"/>

              </Button>


            </div>


          </div>


        </div>


      </div>


    </div>

  );

}
