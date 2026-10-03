import { initializeApp } from "firebase/app";
import { getAuth } from "firebase/auth";

const firebaseConfig = {
  apiKey: "AIzaSyBkjuPeOTBE82ZDJkFcN9aonFdnpGhR90I",
  authDomain: "roundtable-78095.firebaseapp.com",
  projectId: "roundtable-78095",
  storageBucket: "roundtable-78095.firebasestorage.app",
  messagingSenderId: "96873946216",
  appId: "1:96873946216:web:d304fffe1bdf7c963f2fdd",
  measurementId: "G-H8488FRZ5N"
};

const app = initializeApp(firebaseConfig);

export const auth = getAuth(app);