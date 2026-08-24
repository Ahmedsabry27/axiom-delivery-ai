import {
  Avatar,
  Box,
  Typography,
} from "@mui/material";

import SmartToyIcon from "@mui/icons-material/SmartToy";
import PersonIcon from "@mui/icons-material/Person";

import CopyButton from "../common/CopyButton";

function MessageHeader({
  isUser,
  timestamp,
  text,
}) {
  return (
    <Box
      sx={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        mb: 2,
      }}
    >
      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          gap: 1.5,
        }}
      >
        <Avatar
          sx={{
            width: 36,
            height: 36,
            bgcolor: isUser ? "primary.main" : "#10A37F",
            boxShadow: "0 2px 8px rgba(0,0,0,.15)",
          }}
        >
          {isUser ? (
            <PersonIcon fontSize="small" />
          ) : (
            <SmartToyIcon fontSize="small" />
          )}
        </Avatar>

        <Box>
          <Box
            sx={{
              display: "flex",
              alignItems: "center",
              gap: 1,
            }}
          >
            <Typography
              sx={{
                fontWeight: 700,
                fontSize: "0.95rem",
              }}
            >
              {isUser ? "You" : "Axiom Delivery AI"}
            </Typography>

            {timestamp && (
              <Typography
                variant="caption"
                sx={{
                  color: "text.secondary",
                  fontSize: "0.75rem",
                }}
              >
                {timestamp}
              </Typography>
            )}
          </Box>
        </Box>
      </Box>

      {!isUser && (
        <CopyButton text={text} />
      )}
    </Box>
  );
}

export default MessageHeader;
