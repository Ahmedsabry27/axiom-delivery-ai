import { useEffect, useState } from "react";

import {
  RouterProvider
} from "react-router-dom";

import {
  router
} from "./app/router";

import {
  currentUser,
  login
} from "./services/auth";
import { productConfig } from "./config/product";


function App() {

  const [loading, setLoading] = useState(true);


  useEffect(() => {

    const checkAuthentication = async () => {

      try {

        await currentUser();

        setLoading(false);

      } catch {

        console.log(
          "User not authenticated. Redirecting..."
        );


        try {

          await login();

        } catch (loginError) {

          console.error(
            "Login failed:",
            loginError
          );

          setLoading(false);

        }

      }

    };


    checkAuthentication();

  }, []);



  if (loading) {

    return (

      <div className="flex h-screen items-center justify-center">

        <div className="text-center">

          <h1 className="text-2xl font-semibold">
            {productConfig.name}
          </h1>


          <p className="mt-4">
            {productConfig.tagline}
          </p>


        </div>

      </div>

    );

  }



  return (
    <RouterProvider router={router}/>
  );

}


export default App;
