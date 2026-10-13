import CloudUploadIcon from "@mui/icons-material/CloudUpload";
import DownloadIcon from "@mui/icons-material/Download";
import ReplayIcon from "@mui/icons-material/Replay";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Container,
  Grid,
  LinearProgress,
  MenuItem,
  Paper,
  Select,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from "@mui/material";
import axios from "axios";
import { useCallback, useEffect, useMemo, useState } from "react";

type UploadItem = {
  doc_id: string;
  file_name: string;
  job_id: string;
  status: string;
  stage: string;
  doc_type?: string;
  validation_status?: string;
};

type DashboardPayload = {
  metrics?: {
    documents_total: number;
    jobs_total: number;
    jobs_completed: number;
    jobs_failed: number;
    avg_processing_seconds: number;
  };
  quality?: {
    ocr_accuracy: number;
    classification_accuracy: number;
    avg_processing_seconds: number;
    concurrent_users_supported: number;
  };
};

const apiBase = import.meta.env.VITE_API_GATEWAY_URL || "http://localhost:8600";

async function fileToPayload(file: File) {
  const textSafe = file.type.startsWith("text/") || file.name.endsWith(".txt") || file.name.endsWith(".md");
  const fileText = textSafe ? await file.text() : undefined;
  const base64 = !textSafe
    ? await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => {
          const value = String(reader.result || "");
          resolve(value.split(",").pop() || "");
        };
        reader.onerror = reject;
        reader.readAsDataURL(file);
      })
    : undefined;

  return {
    file_name: file.name,
    content_type: file.type || "application/octet-stream",
    text_content: fileText,
    content_base64: base64,
    source: "drag_drop",
    language_hint: "ru",
    actor_id: "operator-ui",
    actor_role: "operator",
  };
}

export default function App() {
  const [items, setItems] = useState<UploadItem[]>([]);
  const [dashboard, setDashboard] = useState<DashboardPayload>({});
  const [error, setError] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [correctionDocId, setCorrectionDocId] = useState<string>("");
  const [correctionJson, setCorrectionJson] = useState('{"amount": "0.00"}');
  const [restartStage, setRestartStage] = useState<string>("ocr");

  const uploadFiles = useCallback(async (files: FileList | File[]) => {
    const arr = Array.from(files);
    if (!arr.length) {
      return;
    }
    setLoading(true);
    setError("");
    try {
      const requests = await Promise.all(arr.map(fileToPayload));
      const responses = await Promise.all(requests.map((payload) => axios.post(`${apiBase}/documents/upload`, payload)));
      const appended = responses.map((response) => ({
        doc_id: response.data.document.doc_id,
        file_name: response.data.document.file_name,
        job_id: response.data.job.job_id,
        status: response.data.job.status,
        stage: response.data.job.current_stage,
      }));
      setItems((prev) => [...appended, ...prev]);
      if (!correctionDocId && appended[0]) {
        setCorrectionDocId(appended[0].doc_id);
      }
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }, [correctionDocId]);

  useEffect(() => {
    const handle = setInterval(async () => {
      try {
        const updated = await Promise.all(
          items.map(async (item) => {
            const statusResp = await axios.get(`${apiBase}/pipeline/status/${item.job_id}`);
            const status = statusResp.data;
            let docType = item.doc_type;
            let validationStatus = item.validation_status;

            if (status.status === "completed") {
              const result = await axios.get(`${apiBase}/pipeline/document/${item.doc_id}`);
              docType = result.data.doc_type;
              validationStatus = result.data.validated?.status;
            }

            return {
              ...item,
              status: status.status,
              stage: status.current_stage,
              doc_type: docType,
              validation_status: validationStatus,
            };
          })
        );
        setItems(updated);
      } catch {
        // Ignore transient polling errors.
      }
    }, 2200);

    return () => clearInterval(handle);
  }, [items]);

  useEffect(() => {
    const loadDashboard = async () => {
      try {
        const response = await axios.get(`${apiBase}/dashboard`);
        setDashboard(response.data);
      } catch {
        // Ignore dashboard refresh errors.
      }
    };
    loadDashboard();
    const handle = setInterval(loadDashboard, 5000);
    return () => clearInterval(handle);
  }, []);

  const onDrop: React.DragEventHandler<HTMLDivElement> = async (event) => {
    event.preventDefault();
    await uploadFiles(event.dataTransfer.files);
  };

  const onRestart = async (docId: string) => {
    await axios.post(`${apiBase}/pipeline/restart/${docId}`, null, {
      params: {
        stage: restartStage,
        actor_id: "admin-ui",
        actor_role: "admin",
      },
    });
  };

  const onCorrection = async () => {
    if (!correctionDocId) {
      return;
    }
    try {
      const parsed = JSON.parse(correctionJson);
      await axios.post(`${apiBase}/review/${correctionDocId}`, {
        editor_id: "reviewer-ui",
        editor_role: "reviewer",
        corrected_fields: parsed,
        note: "manual adjustment from UI",
      });
    } catch (err) {
      setError(`Correction failed: ${String(err)}`);
    }
  };

  const onExport = async (docId: string, format: "json" | "xml" | "csv") => {
    const response = await axios.get(`${apiBase}/exports/${docId}`, {
      params: { format, actor_role: "operator" },
    });
    const content = response.data.content as string;
    const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${docId}.${format}`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const kpi = useMemo(() => {
    const quality = dashboard.quality;
    const metrics = dashboard.metrics;
    return [
      {
        label: "OCR Accuracy",
        value: quality ? `${(quality.ocr_accuracy * 100).toFixed(1)}%` : "-",
      },
      {
        label: "Classification",
        value: quality ? `${(quality.classification_accuracy * 100).toFixed(1)}%` : "-",
      },
      {
        label: "Avg Time",
        value: metrics ? `${metrics.avg_processing_seconds.toFixed(1)} sec` : "-",
      },
      {
        label: "Completed Jobs",
        value: metrics ? String(metrics.jobs_completed) : "-",
      },
    ];
  }, [dashboard]);

  return (
    <Container maxWidth="xl" sx={{ py: 4 }}>
      <Stack spacing={3}>
        <Paper elevation={0} sx={{ p: 3, border: "1px solid", borderColor: "divider", bgcolor: "rgba(255,255,255,0.88)" }}>
          <Typography component="h1" variant="h3" sx={{ mb: 1 }}>
            SmartDoc Processor
          </Typography>
          <Typography sx={{ color: "text.secondary", maxWidth: 860 }}>
            Intelligent OCR pipeline for passports, licenses, contracts, receipts, forms, and handwritten documents.
            Upload files, track pipeline status live, review corrections, and export structured results.
          </Typography>
        </Paper>

        <Grid container spacing={2}>
          {kpi.map((card) => (
            <Grid item xs={12} sm={6} md={3} key={card.label}>
              <Card sx={{ border: "1px solid", borderColor: "divider" }}>
                <CardContent>
                  <Typography variant="body2" color="text.secondary">
                    {card.label}
                  </Typography>
                  <Typography variant="h5">{card.value}</Typography>
                </CardContent>
              </Card>
            </Grid>
          ))}
        </Grid>

        {error ? <Alert severity="error">{error}</Alert> : null}

        <Paper
          onDragOver={(event) => event.preventDefault()}
          onDrop={onDrop}
          sx={{ p: 3, border: "2px dashed", borderColor: "primary.main", bgcolor: "rgba(13,110,110,0.05)" }}
        >
          <Stack direction={{ xs: "column", sm: "row" }} spacing={2} alignItems="center" justifyContent="space-between">
            <Stack direction="row" spacing={1} alignItems="center">
              <CloudUploadIcon color="primary" />
              <Typography>Drag and drop documents here, or select files for batch upload.</Typography>
            </Stack>
            <Button variant="contained" component="label" disabled={loading}>
              Select files
              <input
                hidden
                multiple
                type="file"
                onChange={(event) => {
                  if (event.target.files) {
                    void uploadFiles(event.target.files);
                  }
                }}
              />
            </Button>
          </Stack>
          {loading ? <LinearProgress sx={{ mt: 2 }} /> : null}
        </Paper>

        <Paper sx={{ p: 3, border: "1px solid", borderColor: "divider" }}>
          <Stack direction={{ xs: "column", md: "row" }} spacing={2} alignItems={{ xs: "stretch", md: "center" }}>
            <TextField
              label="Document ID for correction"
              value={correctionDocId}
              onChange={(event) => setCorrectionDocId(event.target.value)}
              size="small"
            />
            <TextField
              label="Correction JSON"
              value={correctionJson}
              onChange={(event) => setCorrectionJson(event.target.value)}
              size="small"
              fullWidth
            />
            <Button variant="outlined" onClick={onCorrection}>
              Apply correction
            </Button>
          </Stack>
        </Paper>

        <Paper sx={{ p: 2, border: "1px solid", borderColor: "divider", overflowX: "auto" }}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Document</TableCell>
                <TableCell>Job</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Stage</TableCell>
                <TableCell>Type</TableCell>
                <TableCell>Validation</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {items.map((item) => (
                <TableRow key={item.job_id} hover>
                  <TableCell>{item.file_name}</TableCell>
                  <TableCell>{item.job_id.slice(0, 8)}</TableCell>
                  <TableCell>
                    <Chip
                      size="small"
                      color={item.status === "completed" ? "success" : item.status === "failed" ? "error" : "primary"}
                      label={item.status}
                    />
                  </TableCell>
                  <TableCell>{item.stage}</TableCell>
                  <TableCell>{item.doc_type || "-"}</TableCell>
                  <TableCell>{item.validation_status || "-"}</TableCell>
                  <TableCell align="right">
                    <Stack direction="row" spacing={1} justifyContent="flex-end">
                      <Select
                        size="small"
                        value={restartStage}
                        onChange={(event) => setRestartStage(event.target.value)}
                        sx={{ minWidth: 110 }}
                      >
                        <MenuItem value="preprocess">preprocess</MenuItem>
                        <MenuItem value="classify">classify</MenuItem>
                        <MenuItem value="ocr">ocr</MenuItem>
                        <MenuItem value="extract">extract</MenuItem>
                        <MenuItem value="validate">validate</MenuItem>
                      </Select>
                      <Button size="small" variant="outlined" startIcon={<ReplayIcon />} onClick={() => void onRestart(item.doc_id)}>
                        Restart
                      </Button>
                      <Button size="small" variant="outlined" startIcon={<DownloadIcon />} onClick={() => void onExport(item.doc_id, "json")}>JSON</Button>
                      <Button size="small" variant="outlined" onClick={() => void onExport(item.doc_id, "xml")}>XML</Button>
                      <Button size="small" variant="outlined" onClick={() => void onExport(item.doc_id, "csv")}>CSV</Button>
                    </Stack>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          {!items.length ? <Typography sx={{ p: 2, color: "text.secondary" }}>No documents uploaded yet.</Typography> : null}
        </Paper>
      </Stack>
    </Container>
  );
}
