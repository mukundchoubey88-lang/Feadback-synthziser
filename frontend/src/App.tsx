import { Route, Routes } from "react-router-dom";
import { LandingPage } from "./pages/LandingPage";
import { ConsoleLayout } from "./pages/console/ConsoleLayout";
import { OverviewPage } from "./pages/console/OverviewPage";
import { FeedbackPage } from "./pages/console/FeedbackPage";
import { IngestionPage } from "./pages/console/IngestionPage";
import { QualityPage } from "./pages/console/QualityPage";
import { ThemesPage } from "./pages/console/ThemesPage";
import { InsightsPage } from "./pages/console/InsightsPage";
import { MemoryPage } from "./pages/console/MemoryPage";
import { ReportsPage } from "./pages/console/ReportsPage";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/console" element={<ConsoleLayout />}>
        <Route index element={<OverviewPage />} />
        <Route path="feedback" element={<FeedbackPage />} />
        <Route path="feedback/:feedbackId" element={<FeedbackPage />} />
        <Route path="ingestion" element={<IngestionPage />} />
        <Route path="quality" element={<QualityPage />} />
        <Route path="themes" element={<ThemesPage />} />
        <Route path="insights" element={<InsightsPage />} />
        <Route path="memory" element={<MemoryPage />} />
        <Route path="reports" element={<ReportsPage />} />
      </Route>
    </Routes>
  );
}
