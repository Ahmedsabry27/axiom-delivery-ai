import Avatar from "./Avatar";

export default function UserMessage({ message }) {

  const content =
    message.content ||
    message.text ||
    "";


  return (

    <div
      className="
      mb-8
      flex
      justify-end
      animate-in
      fade-in
      slide-in-from-bottom-2
      duration-300
      "
    >

      <div
        className="
        flex
        max-w-6xl
        items-end
        gap-4
        "
      >


        {/* Message Bubble */}

        <div
          className="
          rounded-sm
          bg-[#a00028]
          px-6
          py-4
          text-white
          shadow-md
          "
        >

          <p
            className="
            whitespace-pre-wrap
            break-words
            leading-7
            "
          >

            {content}

          </p>


        </div>




        {/* User Avatar */}

        <Avatar role="user" />


      </div>


    </div>

  );

}
