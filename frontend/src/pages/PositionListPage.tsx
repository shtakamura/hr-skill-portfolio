import { useEffect, useState } from "react";
import { Box, Button, CircularProgress, Typography } from "@mui/material";
import { useNavigate } from "react-router-dom";
import { AppHeader } from "../components/layout/AppHeader";
import { DepartmentCard } from "../components/position/DepartmentCard";
import { EmptyPositionResult } from "../components/position/EmptyPositionResult";
import { PositionFilterPanel } from "../components/position/PositionFilterPanel";
import { PositionListHeader } from "../components/position/PositionListHeader";
import { usePositionSearch } from "../hooks/usePositionSearch";
import { getDepartments } from "../services/positionService";
import type { Department, Position } from "../types/position";

const findPositionById = (departments: Department[], positionId: string): Position | undefined => {
  for (const department of departments) {
    const position = department.positions.find((candidate) => candidate.positionId === positionId);
    if (position) {
      return position;
    }
  }
  return undefined;
};

export const PositionListPage = () => {
  const navigate = useNavigate();
  const [departments, setDepartments] = useState<Department[]>([]);
  const [selectedPositionId, setSelectedPositionId] = useState("");
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    let mounted = true;
    void getDepartments().then((items) => {
      if (mounted) {
        setDepartments(items);
        setSelectedPositionId(items[0]?.positions[0]?.positionId ?? "");
        setErrorMessage("");
        setLoading(false);
      }
    }).catch(() => {
      if (mounted) {
        setErrorMessage("ポジション一覧を取得できませんでした。時間をおいて再試行してください");
        setLoading(false);
      }
    });
    return () => {
      mounted = false;
    };
  }, []);

  const {
    inputCondition,
    filteredDepartments,
    visiblePositionCount,
    setConditionValue,
    applySearch,
    clearSearch,
  } = usePositionSearch(departments);
  const selectedPosition = findPositionById(departments, selectedPositionId);

  const handleOpenSearchChart = () => {
    if (!selectedPosition) {
      return;
    }
    void navigate(`/positions/${selectedPosition.positionId}/search-chart`, {
      state: { selectedPosition },
    });
  };

  return (
    <Box sx={{ minHeight: "100vh", backgroundColor: "background.default" }}>
      <AppHeader visiblePositionCount={visiblePositionCount} />
      <Box
        component="main"
        sx={{
          maxWidth: 1440,
          mx: "auto",
          px: { xs: 2, md: 4 },
          py: 2,
        }}
      >
        <Box
          sx={{
            display: "grid",
            gridTemplateColumns: { xs: "1fr", lg: "minmax(0, 3fr) minmax(280px, 1fr)" },
            gap: 3,
            alignItems: "start",
          }}
        >
          <Box sx={{ order: { xs: 2, lg: 1 } }}>
            <PositionListHeader departmentCount={filteredDepartments.length} positionCount={visiblePositionCount} />
            {loading ? (
              <Box sx={{ display: "flex", justifyContent: "center", py: 8 }}>
                <CircularProgress aria-label="ポジション一覧を読み込み中" />
              </Box>
            ) : errorMessage ? (
              <Box sx={{ py: 8, textAlign: "center" }}>
                <Typography sx={{ fontWeight: 700 }}>{errorMessage}</Typography>
              </Box>
            ) : filteredDepartments.length === 0 ? (
              <EmptyPositionResult />
            ) : (
              <Box
                sx={{
                  display: "grid",
                  gridTemplateColumns: { xs: "1fr", sm: "repeat(2, minmax(0, 1fr))", xl: "repeat(3, minmax(0, 1fr))" },
                  gap: 1.25,
                }}
              >
                {filteredDepartments.map((department) => (
                  <DepartmentCard
                    key={department.departmentId}
                    department={department}
                    selectedPositionId={selectedPositionId}
                    onSelectPosition={(position) => setSelectedPositionId(position.positionId)}
                  />
                ))}
              </Box>
            )}
            <Box
              sx={{
                mt: 2,
                display: "flex",
                justifyContent: "space-between",
                gap: 2,
                flexDirection: { xs: "column", sm: "row" },
              }}
            >
              <Typography color="text.secondary" sx={{ fontSize: "0.82rem" }}>
                ※ 部署から対象ポジションを選択し、詳細や類似ポジションを確認
              </Typography>
              <Typography color="primary" sx={{ fontSize: "0.82rem", fontWeight: 700 }}>
                選択中のポジションは赤枠で表示
              </Typography>
            </Box>
            <Box sx={{ mt: 1.5, display: "flex", justifyContent: "flex-end" }}>
              <Button
                variant="contained"
                color="primary"
                aria-label="選択したポジションの詳細画面へ進む"
                disabled={!selectedPosition}
                onClick={handleOpenSearchChart}
                sx={{ fontWeight: 700, minWidth: 180 }}
              >
                詳細画面へ進む
              </Button>
            </Box>
          </Box>
          <Box sx={{ order: { xs: 1, lg: 2 }, position: { lg: "sticky" }, top: { lg: 16 } }}>
            <PositionFilterPanel
              condition={inputCondition}
              visiblePositionCount={visiblePositionCount}
              selectedPosition={selectedPosition}
              onChange={setConditionValue}
              onSearch={applySearch}
              onClear={clearSearch}
            />
          </Box>
        </Box>
      </Box>
    </Box>
  );
};