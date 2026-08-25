import { Navigate, Route, Routes } from "react-router-dom";
import { PositionListPage } from "./pages/PositionListPage";
import { PositionSearchChartPage } from "./pages/PositionSearchChartPage";

const App = () => (
	<Routes>
		<Route path="/" element={<Navigate to="/positions" replace />} />
		<Route path="/positions" element={<PositionListPage />} />
		<Route path="/positions/:positionId/search-chart" element={<PositionSearchChartPage />} />
	</Routes>
);

export default App;