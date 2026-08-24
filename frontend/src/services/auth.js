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

const OAUTH_COMPLETION_ATTEMPTS = 50;
const OAUTH_COMPLETION_INTERVAL_MS = 200;

function isOAuthRedirectCallback() {
    const parameters = new URLSearchParams(window.location.search);
    return parameters.has("code") && parameters.has("state");
}

async function getAuthenticatedCognitoUser() {
    const [user, session] = await Promise.all([
        getCurrentUser(),
        fetchAuthSession(),
    ]);
    if (!session.tokens?.accessToken) {
        throw new Error("Cognito session does not contain an access token");
    }
    return user;
}

async function waitForOAuthCompletion() {
    let lastError;
    for (let attempt = 0; attempt < OAUTH_COMPLETION_ATTEMPTS; attempt += 1) {
        try {
            return await getAuthenticatedCognitoUser();
        } catch (error) {
            lastError = error;
            await new Promise(resolve => window.setTimeout(resolve, OAUTH_COMPLETION_INTERVAL_MS));
        }
    }
    throw lastError ?? new Error("Cognito authorization did not complete");
}

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
    try {
        return await getAuthenticatedCognitoUser();
    } catch (error) {
        // Amplify completes the authorization-code exchange asynchronously after
        // Cognito redirects back to this SPA. Do not begin a second redirect while
        // that exchange is still persisting the access token.
        if (isOAuthRedirectCallback()) return await waitForOAuthCompletion();
        throw error;
    }
}
