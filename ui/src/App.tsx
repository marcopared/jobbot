import { Routes, Route, Navigate } from "react-router-dom";
import Layout from "./components/Layout";
import ReadyToApplyPage from "./pages/ReadyToApplyPage";
import JobsPage from "./pages/JobsPage";
import JobDetailPage from "./pages/JobDetailPage";
import RunsPage from "./pages/RunsPage";
import RunDetailPage from "./pages/RunDetailPage";

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Navigate to="/ready" replace />} />
        <Route path="/ready" element={<ReadyToApplyPage />} />
        <Route path="/jobs" element={<JobsPage />} />
        <Route path="/jobs/:id" element={<JobDetailPage />} />
        <Route path="/runs" element={<RunsPage />} />
        <Route path="/runs/:id" element={<RunDetailPage />} />
      </Routes>
    </Layout>
  );
}
