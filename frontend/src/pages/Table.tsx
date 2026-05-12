import { Navigate } from "react-router-dom";

export default function Table() {
  const sessionId = localStorage.getItem("ph_session_id");
  return <Navigate to={sessionId ? "/session" : "/games"} replace />;
}
