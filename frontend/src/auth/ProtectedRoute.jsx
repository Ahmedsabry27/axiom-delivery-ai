import { useEffect, useState } from "react";
import { getCurrentUser, signInWithRedirect } from "aws-amplify/auth";

export default function ProtectedRoute({ children }) {
    const [loading, setLoading] = useState(true);
    const [authenticated, setAuthenticated] = useState(false);

    useEffect(() => {
        async function checkAuth() {
            try {
                await getCurrentUser();
                setAuthenticated(true);
            } catch {
                await signInWithRedirect();
            } finally {
                setLoading(false);
            }
        }

        checkAuth();
    }, []);

    if (loading) {
        return <div>Loading...</div>;
    }

    return authenticated ? children : null;
}