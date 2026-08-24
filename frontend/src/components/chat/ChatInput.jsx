import { useState } from "react";

import {
  Send,
  Square,
} from "lucide-react";


export default function ChatInput({
  onSend,
  onStop,
  loading,
  disabled = false,
}) {


  const [message, setMessage] = useState("");



  async function send() {

    const text = message.trim();

    if (!text) return;


    setMessage("");

    await onSend?.(text);

  }



  function handleKeyDown(e){

    if(
      e.key === "Enter" &&
      !e.shiftKey
    ){

      e.preventDefault();

      send();

    }

  }



  return (

    <div
      className="
        relative
        shrink-0
        z-50
        mx-auto
        mb-4
        w-[calc(100%-2rem)]
        max-w-4xl
      "
    >


      <div
        className="
          flex
          items-end
          gap-4

          rounded-3xl

          border
          border-white/10

          bg-white/10

          px-5
          py-4

          backdrop-blur-2xl

          shadow-2xl

        "
      >



        {/* Input */}


        <textarea

          rows={1}

          value={message}

          disabled={loading || disabled}
          aria-label="Message Axiom Delivery AI"

          onChange={(e)=>
            setMessage(e.target.value)
          }

          onKeyDown={handleKeyDown}

          placeholder={disabled ? "Complete the required runtime interaction above…" : "Ask Axiom Delivery AI…"}

          className="
            flex-1

            resize-none

            bg-transparent

            outline-none

            text-white

            placeholder:text-slate-400

            max-h-32

            text-sm

          "

        />






        {/* Action Button */}


        {
          loading ? (


            <button

              onClick={onStop}
              aria-label="Cancel runtime execution"

              className="
                flex
                h-11
                w-11
                items-center
                justify-center

                rounded-full

                bg-red-500/20

                text-red-300

                border
                border-red-400/20

                transition

                hover:bg-red-500/30

              "

            >

              <Square
                size={18}
                fill="currentColor"
              />


            </button>



          ) : (


            <button

              disabled={disabled || !message.trim()}

              onClick={send}
              aria-label="Send message"


              className="
                flex
                h-11
                w-11
                items-center
                justify-center

                rounded-full

                bg-gradient-to-br

                from-blue-500

                to-purple-500


                text-white


                shadow-lg


                transition


                disabled:
                opacity-40


                hover:
                scale-105

              "

            >


              <Send size={20}/>


            </button>



          )
        }



      </div>



    </div>

  );

}
