import { useCallback, useEffect, useState } from "react";

import {
    currentUser,
    getSession,
    logout,
    login,
} from "../services/auth";

export default function useAuth() {
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);

    const refresh = useCallback(async () => {
        try {
            const cognitoUser = await currentUser();
            const session = await getSession();

            const claims = session.tokens?.idToken?.payload ?? {};

            setUser({
                id: cognitoUser.userId,
                username: cognitoUser.username,

                email: claims.email,
                name: claims.name,
                givenName: claims.given_name,
                familyName: claims.family_name,

                initials:
                    (
                        (claims.given_name?.[0] ?? "") +
                        (claims.family_name?.[0] ?? "")
                    ).toUpperCase(),
            });
        } catch {
            setUser(null);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        const task = window.setTimeout(() => void refresh(), 0);
        return () => window.clearTimeout(task);
    }, [refresh]);

    return {
        user,
        loading,
        authenticated: !!user,
        login,
        logout,
        refresh,
    };
}
