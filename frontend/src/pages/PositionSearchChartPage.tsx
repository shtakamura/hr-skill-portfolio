import { useEffect, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { Box, Button, CircularProgress, Typography } from "@mui/material";
import { SearchChartFooter } from "../components/searchChart/SearchChartFooter";
import { SearchChartHeader } from "../components/searchChart/SearchChartHeader";
import { SelectedPositionPanel } from "../components/searchChart/SelectedPositionPanel";
import { SimilarPositionGrid } from "../components/searchChart/SimilarPositionGrid";
import { getPositionById } from "../services/positionService";
import { getPositionSkillProfile, getSimilarPositions } from "../services/skillProfileService";
import type { Position } from "../types/position";
import type { PositionSkillProfile, SimilarPosition } from "../types/skillProfile";

type SearchChartLocationState = {
  selectedPosition?: Position;
};

export const PositionSearchChartPage = () => {
  const { positionId } = useParams<{ positionId: string }>();
  const location = useLocation();
  const navigate = useNavigate();
  const routeState = location.state as SearchChartLocationState | null;
  const [profile, setProfile] = useState<PositionSkillProfile | undefined>(() => {
    const selectedPosition = routeState?.selectedPosition;
    if (!selectedPosition) {
      return undefined;
    }
    return {
      positionId: selectedPosition.positionId,
      positionName: selectedPosition.positionName,
      departmentName: selectedPosition.departmentName,
      businessUnitName: selectedPosition.businessUnitName,
      skills: [],
      dataSource: "sample",
    };
  });
  const [similarPositions, setSimilarPositions] = useState<SimilarPosition[]>([]);
  const [selectedRank, setSelectedRank] = useState(1);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");

  const handleBack = () => {
    void navigate("/positions");
  };

  useEffect(() => {
    let mounted = true;

    const loadSearchChart = async () => {
      if (!positionId) {
        setErrorMessage("対象ポジションが見つかりません");
        setLoading(false);
        return;
      }

      try {
        const position = await getPositionById(positionId);
        if (!position) {
          throw new Error("Position not found");
        }
        const [skillProfile, positions] = await Promise.all([getPositionSkillProfile(position), getSimilarPositions(positionId)]);
        if (mounted) {
          setProfile(skillProfile);
          setSimilarPositions(positions);
          setSelectedRank(1);
          setErrorMessage("");
        }
      } catch {
        if (mounted) {
          setErrorMessage("対象ポジションが見つかりません");
        }
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    };

    void loadSearchChart();

    return () => {
      mounted = false;
    };
  }, [positionId]);

  if (loading) {
    return (
      <Box sx={{ minHeight: "100vh", backgroundColor: "background.default" }}>
        <SearchChartHeader selectedPosition={profile} onBack={handleBack} />
        <Box sx={{ minHeight: 420, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <Box sx={{ textAlign: "center" }}>
            <CircularProgress aria-label="スキルデータを読み込み中" />
            <Typography sx={{ mt: 2, fontWeight: 700 }}>スキルデータを読み込んでいます</Typography>
          </Box>
        </Box>
      </Box>
    );
  }

  if (errorMessage || !profile) {
    return (
      <Box sx={{ minHeight: "100vh", backgroundColor: "background.default" }}>
        <SearchChartHeader selectedPosition={profile} onBack={handleBack} />
        <Box sx={{ maxWidth: 1600, mx: "auto", px: { xs: 2, md: 4 }, py: 8, textAlign: "center" }}>
          <Typography sx={{ mb: 2, fontWeight: 700 }}>{errorMessage || "スキルデータを取得できませんでした。時間をおいて再試行してください"}</Typography>
          <Button variant="contained" color="primary" aria-label="ポジション一覧へ戻る" onClick={handleBack}>
            ポジション一覧へ戻る
          </Button>
        </Box>
      </Box>
    );
  }

  return (
    <Box sx={{ minHeight: "100vh", backgroundColor: "background.default" }}>
      <SearchChartHeader selectedPosition={profile} onBack={handleBack} />
      <Box component="main" sx={{ maxWidth: 1600, mx: "auto", px: { xs: 2, md: 4 }, py: 2 }}>
        <Box
          sx={{
            display: "grid",
            gridTemplateColumns: { xs: "1fr", lg: "minmax(320px, 1fr) minmax(0, 2fr)" },
            gap: 3,
            alignItems: "start",
          }}
        >
          <SelectedPositionPanel profile={profile} />
          <SimilarPositionGrid positions={similarPositions} selectedRank={selectedRank} onSelectRank={setSelectedRank} />
        </Box>
        {/* TODO: 類似ポジション詳細画面実装後に遷移処理を追加する。 */}
        <SearchChartFooter />
      </Box>
    </Box>
  );
};