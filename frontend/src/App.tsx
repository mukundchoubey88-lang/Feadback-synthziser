import { Route, Routes } from "react-router-dom";
import { LandingPage } from "./pages/LandingPage";
import { ConsoleLayout } from "./pages/console/ConsoleLayout";
import { OverviewPage } from "./pages/console/OverviewPage";
import { FeedbackPage } from "./pages/console/FeedbackPage";
import { IngestionPage } from "./pages/console/IngestionPage";
import { QualityPage } from "./pages/console/QualityPage";
import { PlannedPage } from "./pages/console/ui";

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
        <Route
          path="themes"
          element={
            <PlannedPage
              kicker="Part 6"
              title="Themes are not served by the API yet."
              body="Theme discovery is part of the product story on the landing page. There is no themes endpoint in the current backend, so this screen does not invent clusters, volumes, or sentiment."
            />
          }
        />
        <Route
          path="insights"
          element={
            <PlannedPage
              kicker="Part 7"
              title="Insights stay unpublished until they can cite records."
              body="Evidence-backed recommendations require an insights API that can point at feedback identifiers. That route is specified and not implemented, so nothing here is presented as a live recommendation."
            />
          }
        />
        <Route
          path="memory"
          element={
            <PlannedPage
              kicker="Part 9"
              title="Hindsight memory is designed, not connected."
              body="The memory layer is meant to retain episodic events, semantic themes, and temporal change with provenance. The Hindsight client is still a placeholder, and no memory search route is available."
            />
          }
        />
        <Route
          path="reports"
          element={
            <PlannedPage
              kicker="Later"
              title="Reports are not generated yet."
              body="Release correlation and exportable intelligence reports depend on product-change and insight endpoints that do not exist yet. Quality and ingestion results in this console are the live reports today."
            />
          }
        />
      </Route>
    </Routes>
  );
}
