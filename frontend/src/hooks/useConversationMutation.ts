import { useMutation } from "@tanstack/react-query";

import {
    sendMessage
} from "../services/chat.service";


export function useConversationMutation(){


    return useMutation({

        mutationFn:
            sendMessage

    });


}