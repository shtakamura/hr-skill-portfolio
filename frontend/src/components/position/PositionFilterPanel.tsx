import SearchIcon from "@mui/icons-material/Search";
import {
  Box,
  Button,
  Divider,
  FormControl,
  FormHelperText,
  InputAdornment,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  TextField,
  Typography,
} from "@mui/material";
import type { Position, PositionSearchCondition } from "../../types/position";

const jobGradeOptions = ["すべて", "担当", "主任", "課長", "副部長", "部長", "マネージャー", "ディレクター"];
const jobCategoryOptions = ["すべて", "マネジメント", "スペシャリスト", "エンジニア", "コンサルタント", "企画", "営業", "管理"];
const organizationLevelOptions = [
  { value: "company", label: "全社" },
  { value: "cxo", label: "CXO" },
  { value: "bu", label: "BU" },
  { value: "department", label: "部" },
];

type PositionFilterPanelProps = {
  condition: PositionSearchCondition;
  visiblePositionCount: number;
  selectedPosition: Position | undefined;
  onChange: <Field extends keyof PositionSearchCondition>(
    field: Field,
    value: PositionSearchCondition[Field],
  ) => void;
  onSearch: () => void;
  onClear: () => void;
};

export const PositionFilterPanel = ({
  condition,
  visiblePositionCount,
  selectedPosition,
  onChange,
  onSearch,
  onClear,
}: PositionFilterPanelProps) => (
  <Paper variant="outlined" sx={{ p: 1.5, borderRadius: 0, borderColor: "#d8dadd", backgroundColor: "background.paper" }}>
    <Typography variant="h2" sx={{ mb: 1.5 }}>
      検索・絞り込み
    </Typography>
    <Box sx={{ display: "grid", gap: 1.35 }}>
      <TextField
        label="組織名"
        placeholder="部署名を入力"
        value={condition.organizationName}
        onChange={(event) => onChange("organizationName", event.target.value)}
        fullWidth
      />
      <TextField
        label="ポジション名"
        placeholder="ポジション名を入力"
        value={condition.positionName}
        onChange={(event) => onChange("positionName", event.target.value)}
        fullWidth
      />
      <FormControl fullWidth size="small">
        <InputLabel id="job-grade-label">職位</InputLabel>
        <Select
          labelId="job-grade-label"
          label="職位"
          value={condition.jobGrade}
          onChange={(event) => onChange("jobGrade", event.target.value)}
        >
          {jobGradeOptions.map((option) => (
            <MenuItem key={option} value={option}>
              {option}
            </MenuItem>
          ))}
        </Select>
      </FormControl>
      <FormControl fullWidth size="small">
        <InputLabel id="job-category-label">職種区分</InputLabel>
        <Select
          labelId="job-category-label"
          label="職種区分"
          value={condition.jobCategory}
          onChange={(event) => onChange("jobCategory", event.target.value)}
        >
          {jobCategoryOptions.map((option) => (
            <MenuItem key={option} value={option}>
              {option}
            </MenuItem>
          ))}
        </Select>
      </FormControl>
      <FormControl fullWidth size="small">
        <InputLabel id="organization-level-label">組織階層</InputLabel>
        <Select
          labelId="organization-level-label"
          label="組織階層"
          value={condition.organizationLevel}
          onChange={(event) => onChange("organizationLevel", event.target.value)}
        >
          {organizationLevelOptions.map((option) => (
            <MenuItem key={option.value} value={option.value}>
              {option.label}
            </MenuItem>
          ))}
        </Select>
        <FormHelperText>全社 ＞ CXO ＞ BU ＞ 部</FormHelperText>
      </FormControl>
      <TextField
        label="キーワード検索"
        placeholder="キーワードを入力"
        value={condition.keyword}
        onChange={(event) => onChange("keyword", event.target.value)}
        slotProps={{
          input: {
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon fontSize="small" color="action" />
              </InputAdornment>
            ),
          },
        }}
        fullWidth
      />
      <Box sx={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 1, mt: 0.5 }}>
        <Button
          variant="contained"
          color="primary"
          aria-label="検索条件を適用"
          onClick={onSearch}
          sx={{ fontWeight: 700, "&:hover": { backgroundColor: "primary.dark" } }}
        >
          検索
        </Button>
        <Button variant="outlined" color="inherit" aria-label="検索条件をクリア" onClick={onClear}>
          クリア
        </Button>
      </Box>
    </Box>
    <Divider sx={{ my: 2 }} />
    <Typography sx={{ fontWeight: 700, mb: 1 }}>表示件数：{visiblePositionCount}件</Typography>
    <Typography color="primary" sx={{ fontSize: "0.76rem", fontWeight: 700, textAlign: "right" }}>
      選択中のポジションは赤枠で表示
    </Typography>
    {selectedPosition ? (
      <Typography sx={{ mt: 1, fontWeight: 700 }}>
        選択中：{selectedPosition.departmentName} ＞ {selectedPosition.positionName}
      </Typography>
    ) : null}
  </Paper>
);