import { Amplify } from "aws-amplify";

const localHosts = new Set(["localhost", "127.0.0.1", "::1"]);
const isLocal = localHosts.has(window.location.hostname);
const localRedirect = window.location.origin;
const productionRedirect = import.meta.env.VITE_AUTH_REDIRECT_URI;
const userPoolId = import.meta.env.VITE_COGNITO_USER_POOL_ID;
const userPoolClientId = import.meta.env.VITE_COGNITO_CLIENT_ID;
const oauthDomain = import.meta.env.VITE_COGNITO_DOMAIN;
export const isCognitoConfigured = Boolean(userPoolId && userPoolClientId && oauthDomain);
export const isLocalAuthBypass = isLocal && !isCognitoConfigured;

if (!isLocal && (!productionRedirect || !isCognitoConfigured)) {
  throw new Error("Production Cognito configuration is incomplete");
}

if (isCognitoConfigured) Amplify.configure({
  Auth: {
    Cognito: {
      userPoolId,
      userPoolClientId,
      loginWith: {
        oauth: {
          domain: oauthDomain,
          scopes: ["openid", "email"],
          redirectSignIn: [
            isLocal
              ? localRedirect
              : productionRedirect,
          ],
          redirectSignOut: [
            isLocal
              ? localRedirect
              : productionRedirect,
          ],
          responseType: "code",
        },
      },
    },
  },
});

if (isLocalAuthBypass) {
  console.info("[auth] Cognito is not configured; using the localhost development identity.");
}
