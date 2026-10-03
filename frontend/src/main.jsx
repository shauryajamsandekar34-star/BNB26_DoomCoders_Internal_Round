import React from "react";
import ReactDOM from "react-dom/client";
import { onAuthStateChanged } from "firebase/auth";

import App from "./App";
import AuthGate from "./AuthGate";
import { auth } from "./firebase";
import "./styles.css";

function Root() {
  const [user, setUser] = React.useState(undefined);

  React.useEffect(() => {
    return onAuthStateChanged(auth, setUser);
  }, []);

  if (user === undefined) {
    return (
      <div
        style={{
          minHeight: "100vh",
          display: "grid",
          placeItems: "center",
          fontFamily: "system-ui, sans-serif",
        }}
      >
        Loading Roundtable...
      </div>
    );
  }

  return (
    <AuthGate>
      <App />
    </AuthGate>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <Root />
  </React.StrictMode>
);