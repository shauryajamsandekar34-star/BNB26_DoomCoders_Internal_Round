import { useState } from "react";
import { GoogleAuthProvider, signInWithPopup, signOut } from "firebase/auth";
import { auth } from "./firebase";

export default function AuthGate({ children }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [profileOpen, setProfileOpen] = useState(false);

  const signInWithGoogle = async () => {
    setLoading(true);
    setError("");

    try {
      const provider = new GoogleAuthProvider();
      await signInWithPopup(auth, provider);
    } catch (err) {
      console.error("Google sign-in error:", err);
      setError(err.message || "Google sign-in failed.");
    } finally {
      setLoading(false);
    }
  };

  const handleSignOut = async () => {
    await signOut(auth);
    setProfileOpen(false);
  };

  const user = auth.currentUser;

  if (user) {
    const initials = (user.displayName || user.email || "U")
      .split(" ")
      .map((part) => part[0])
      .join("")
      .slice(0, 2)
      .toUpperCase();

    return (
      <div style={{ minHeight: "100vh" }}>
        {/* Profile */}
        <div
          style={{
            position: "fixed",
            top: "16px",
            right: "20px",
            zIndex: 1000,
          }}
        >
          <button
            type="button"
            onClick={() => setProfileOpen(!profileOpen)}
            aria-label="Open profile"
            style={{
              width: "44px",
              height: "44px",
              padding: 0,
              borderRadius: "50%",
              border: "2px solid #ffffff",
              background: "#e0eee9",
              boxShadow: "0 4px 18px rgba(22,34,29,.16)",
              overflow: "hidden",
              cursor: "pointer",
            }}
          >
            {user.photoURL ? (
              <img
                src={user.photoURL}
                alt="Profile"
                style={{
                  width: "100%",
                  height: "100%",
                  objectFit: "cover",
                }}
              />
            ) : (
              <span
                style={{
                  color: "#1d5146",
                  fontWeight: "800",
                  fontSize: "13px",
                }}
              >
                {initials}
              </span>
            )}
          </button>

          {/* Dropdown */}
          {profileOpen && (
            <div
              style={{
                position: "absolute",
                top: "54px",
                right: 0,
                width: "260px",
                background: "#ffffff",
                border: "1px solid #dce2dd",
                borderRadius: "14px",
                padding: "10px",
                boxShadow: "0 16px 40px rgba(22,34,29,.15)",
              }}
            >
              {/* User information */}
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "11px",
                  padding: "10px",
                  marginBottom: "6px",
                }}
              >
                {user.photoURL ? (
                  <img
                    src={user.photoURL}
                    alt=""
                    style={{
                      width: "40px",
                      height: "40px",
                      borderRadius: "50%",
                      objectFit: "cover",
                    }}
                  />
                ) : (
                  <div
                    style={{
                      width: "40px",
                      height: "40px",
                      borderRadius: "50%",
                      display: "grid",
                      placeItems: "center",
                      background: "#e0eee9",
                      color: "#1d5146",
                      fontWeight: "800",
                    }}
                  >
                    {initials}
                  </div>
                )}

                <div style={{ minWidth: 0 }}>
                  <div
                    style={{
                      fontWeight: "700",
                      fontSize: "14px",
                      color: "#18211e",
                      whiteSpace: "nowrap",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                    }}
                  >
                    {user.displayName || "Roundtable user"}
                  </div>

                  <div
                    style={{
                      fontSize: "11px",
                      color: "#63706b",
                      marginTop: "3px",
                      whiteSpace: "nowrap",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                    }}
                  >
                    {user.email}
                  </div>
                </div>
              </div>

              <div
                style={{
                  height: "1px",
                  background: "#e8ece9",
                  margin: "4px 2px 7px",
                }}
              />

              {/* Sign out */}
              <button
                type="button"
                onClick={handleSignOut}
                style={{
                  width: "100%",
                  display: "flex",
                  alignItems: "center",
                  gap: "11px",
                  padding: "11px 10px",
                  border: "0",
                  borderRadius: "9px",
                  background: "transparent",
                  color: "#9a3f36",
                  fontSize: "13px",
                  fontWeight: "650",
                  textAlign: "left",
                  cursor: "pointer",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = "#f8ebe9";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = "transparent";
                }}
              >
                <span style={{ fontSize: "17px" }}>↪</span>
                <span>Sign out</span>
              </button>
            </div>
          )}
        </div>

        {children}
      </div>
    );
  }

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "grid",
        placeItems: "center",
        background: "#f6f7f5",
        padding: "24px",
      }}
    >
      <div
        style={{
          width: "100%",
          maxWidth: "420px",
          background: "#ffffff",
          border: "1px solid #dce2dd",
          borderRadius: "16px",
          padding: "36px",
          textAlign: "center",
          boxShadow: "0 18px 50px rgba(22,34,29,.08)",
        }}
      >
        <div
          style={{
            width: "48px",
            height: "48px",
            margin: "0 auto 20px",
            display: "grid",
            placeItems: "center",
            borderRadius: "12px",
            background: "#1d5146",
            color: "#ffffff",
            fontSize: "22px",
            fontWeight: "700",
          }}
        >
          R
        </div>

        <h1
          style={{
            margin: "0 0 8px",
            fontSize: "30px",
            color: "#18211e",
          }}
        >
          Welcome to Roundtable
        </h1>

        <p
          style={{
            margin: "0 0 28px",
            color: "#63706b",
            fontSize: "15px",
          }}
        >
          Sign in to join shared live-caption sessions.
        </p>

        <button
          type="button"
          onClick={signInWithGoogle}
          disabled={loading}
          style={{
            width: "100%",
            height: "48px",
            border: "1px solid #dce2dd",
            borderRadius: "9px",
            background: "#ffffff",
            color: "#18211e",
            fontWeight: "600",
            cursor: loading ? "wait" : "pointer",
            fontSize: "15px",
          }}
        >
          {loading ? "Signing in..." : "Continue with Google"}
        </button>

        {error && (
          <p
            style={{
              marginTop: "16px",
              color: "#9a3f36",
              fontSize: "13px",
            }}
          >
            {error}
          </p>
        )}
      </div>
    </div>
  );
}