import {
    signOut,
    signInWithRedirect,
    fetchAuthSession,
    getCurrentUser,
} from "aws-amplify/auth";
import { isLocalAuthBypass } from "../config/amplify";

const localUser = {
    username: "ahmed.sabry",
    userId: "local-developer",
};

const localSession = {
    tokens: {
        idToken: {
            payload: {
                email: "ahmedsabry27@outlook.com",
                name: "Ahmed Sabry",
                given_name: "Ahmed",
                family_name: "Sabry",
            },
        },
    },
};

export async function logout() {
    if (isLocalAuthBypass) return;
    await signOut();
}

export async function login() {
    if (isLocalAuthBypass) return;
    await signInWithRedirect();
}

export async function getAccessToken() {
    if (import.meta.env.MODE === "e2e") {
        return window.sessionStorage.getItem("e2e_access_token");
    }
    if (isLocalAuthBypass) return null;
    const session = await fetchAuthSession();
    const token = session.tokens?.accessToken?.toString();

    if (import.meta.env.DEV) {
        console.log("[auth] Cognito access token present?", !!token);
        if (!token) {
            console.warn("No Cognito access token available from auth session");
        }
    }

    return token;
}

export async function getSession() {
    if (isLocalAuthBypass) return localSession;
    return await fetchAuthSession();
}

export async function currentUser() {
    if (import.meta.env.MODE === "e2e" && window.sessionStorage.getItem("e2e_access_token")) {
        return { username: "e2e-user", userId: "e2e-user" };
    }
    if (isLocalAuthBypass) return localUser;
    return await getCurrentUser();
}
