import api from "./api";


export function subscribeRuntime(
  executionId,
  onEvent
) {


  const baseURL =
    api.defaults.baseURL ||
    "http://127.0.0.1:8000";


  const url =
    `${baseURL}/api/runtime/events/${executionId}`;



  const eventSource =
    new EventSource(url);




  eventSource.onmessage = (event)=>{


    try {


      const data =
        JSON.parse(event.data);


      console.log(
        "Runtime event:",
        data
      );


      onEvent(data);


    }
    catch(error){


      console.error(
        "Invalid runtime event",
        error
      );


    }


  };





  eventSource.onerror = (error)=>{


    console.error(
      "Runtime stream error",
      error
    );


    eventSource.close();


  };





  return ()=>{


    eventSource.close();


  };


}