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

          rounded-xl

          border
          border-stone-300

          bg-white

          px-5
          py-4

          shadow-lg

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

            text-stone-900

            placeholder:text-stone-500

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

                rounded-lg

                bg-red-50

                text-red-700

                border
                border-red-300

                transition

                hover:bg-red-100

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

                rounded-lg

                bg-[#a00028]


                text-white


                shadow-lg


                transition


                disabled:
                opacity-40


                hover:bg-[#7d001f]

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
