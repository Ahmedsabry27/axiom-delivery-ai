import api from "./api";



/**
 * ==================================================
 * Start Runtime Execution
 * ==================================================
 *
 * POST /api/chat/start
 *
 * Response:
 *
 * {
 *   execution_id,
 *   workflow_id
 * }
 *
 */


export async function startExecution(
  payload
) {


  try {


    const { data } =
      await api.post(
        "/api/chat/start",
        payload
      );


    return data;


  }
  catch(error){


    console.error(
      "Failed starting runtime execution",
      error
    );


    throw error;


  }


}









/**
 * ==================================================
 * Runtime Event Stream
 * ==================================================
 *
 * GET /api/runtime/events/{execution_id}
 *
 */


export function subscribeRuntime(
  executionId,
  {
    onEvent,
    onComplete,
    onError,
  } = {}
) {



  const baseUrl =
    import.meta.env.VITE_API_URL || "";





  const url =
    `${baseUrl}/api/runtime/events/${executionId}`;





  const source =
    new EventSource(url);





  console.log(
    "Runtime stream opened:",
    executionId
  );







  source.onopen = ()=>{


    console.log(
      "Runtime connected"
    );


  };









  source.onmessage =
    (event)=>{


      handleEvent(
        event.data
      );


    };









  function handleEvent(
    raw
  ){


    try{


      const data =
        JSON.parse(
          raw
        );



      console.log(
        "Runtime Event",
        data
      );





      /*
        Send every event
        to useChat
      */


      onEvent?.(
        data
      );





      if(
        data.type === "COMPLETED"
        ||
        data.type === "ERROR"
      ){

        source.close();

        onComplete?.(data);


      }




    }
    catch {


      console.error(
        "Invalid SSE event",
        raw
      );


    }


  }









  source.onerror =
    (error)=>{


      console.error(
        "Runtime stream failed",
        error
      );


      onError?.(
        error
      );


      source.close();


    };









  return ()=>{


    console.log(
      "Closing runtime stream"
    );


    source.close();


  };


}









/**
 * ==================================================
 * Legacy Chat
 * ==================================================
 *
 * Keep temporarily
 *
 */


export async function sendMessage(
  payload
){

  const {data} =
    await api.post(
      "/api/chat",
      payload
    );


  return data;

}
