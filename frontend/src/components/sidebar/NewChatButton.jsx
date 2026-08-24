import AddIcon from "@mui/icons-material/Add";

import { Button } from "@mui/material";

function NewChatButton({

  onClick,

}) {

  return (

    <Button

      variant="contained"

      startIcon={<AddIcon />}

      onClick={onClick}

      sx={{
        m: 2,
      }}

    >

      New Chat

    </Button>

  );

}

export default NewChatButton;