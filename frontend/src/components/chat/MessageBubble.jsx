import {
  Box,
  Paper,
  Typography,
  Chip,
  Divider,
} from "@mui/material";


import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";


import {
  Prism as SyntaxHighlighter
} from "react-syntax-highlighter";


import {
  oneDark
} from "react-syntax-highlighter/dist/esm/styles/prism";


import CopyButton from "../common/CopyButton";
import MessageHeader from "./MessageHeader";



function MessageBubble({
  role,
  text,
  timestamp,
  streaming = false,
  metadata,
}) {


  const isUser =
    role === "user";



  const isWorkflowResult =
    metadata &&
    metadata.agent;



  return (

    <Box
      sx={{
        display:"flex",

        justifyContent:
          isUser
            ? "flex-end"
            : "flex-start",

        mb:3,

        px:2,

      }}
    >


      <Paper

        elevation={0}

        sx={{

          maxWidth:{
            xs:"95%",
            md:"78%",
          },


          p:3,


          borderRadius:2,


          bgcolor:
            isUser
              ? "primary.main"
              : "#fff",


          color:
            isUser
              ? "#fff"
              : "#222",


          border:
            isUser
              ? "none"
              : "1px solid rgba(0,0,0,.08)",


          boxShadow:
            "0 8px 25px rgba(0,0,0,.06)"

        }}

      >


        <MessageHeader

          isUser={isUser}

          timestamp={timestamp}

          text={text}

        />



        {/* ---------------------------------
            Enterprise Workflow Card
        ---------------------------------- */}


        {
          isWorkflowResult && !isUser && (

            <Box
              sx={{
                mt:2,
                mb:3,
                p:2,
                borderRadius:2,
                bgcolor:"#F8FAFC",
                border:"1px solid #E2E8F0",
              }}
            >


              <Typography
                fontWeight={700}
                mb={2}
              >

                ✅ Workflow Completed

              </Typography>



              <Divider />



              <Box mt={2}>


                <Typography variant="body2">

                  <b>Agent:</b>{" "}
                  {metadata.agent}

                </Typography>



                <Typography variant="body2">

                  <b>Status:</b>{" "}

                  <Chip

                    size="small"

                    label={
                      metadata.status
                    }

                    color="success"

                  />

                </Typography>



                <Typography variant="body2">

                  <b>Actions:</b>{" "}

                  {
                    metadata.actions?.length
                    ||
                    0
                  }

                  {" "}executed

                </Typography>


              </Box>



            </Box>

          )
        }





        {/* ---------------------------------
            Message Content
        ---------------------------------- */}


        <Box
          sx={{

            fontSize:16,

            lineHeight:2,


            "& code":{
              background:"#F5F5F5",
              padding:"3px 7px",
              borderRadius:1,
            }

          }}

        >



          <ReactMarkdown

            remarkPlugins={[
              remarkGfm
            ]}

            components={{

              code({
                className,
                children,
              }){


                const match =
                  /language-(\w+)/
                  .exec(
                    className || ""
                  );



                if(match){


                  const code =
                    String(children)
                    .replace(
                      /\n$/,
                      ""
                    );



                  return (

                    <Box
                      sx={{
                        my:3,
                        borderRadius:2,
                        overflow:"hidden",
                      }}
                    >


                      <Box

                        sx={{
                          bgcolor:"#2D2D2D",
                          color:"#fff",
                          px:2,
                          py:1,
                          display:"flex",
                          justifyContent:
                            "space-between",
                        }}

                      >

                        <Typography>
                          {match[1]}
                        </Typography>


                        <CopyButton
                          text={code}
                        />

                      </Box>



                      <SyntaxHighlighter

                        language={
                          match[1]
                        }

                        style={
                          oneDark
                        }

                      >

                        {code}

                      </SyntaxHighlighter>


                    </Box>

                  );


                }



                return (
                  <code>
                    {children}
                  </code>
                );

              }

            }}

          >

            {
              isWorkflowResult
              ?
              ""
              :
              text
            }


          </ReactMarkdown>


        </Box>




        {
          streaming && !isUser && (

            <Box

              component="span"

              sx={{

                display:"inline-block",

                width:8,

                height:"1.2em",

                bgcolor:
                  "primary.main",

                animation:
                  "cursorBlink 1s infinite"

              }}

            />

          )
        }



      </Paper>


    </Box>

  );

}


export default MessageBubble;