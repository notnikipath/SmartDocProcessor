import http from "k6/http";
import { sleep } from "k6";

export const options = {
  vus: 100,
  duration: "45s",
};

export default function () {
  http.get("http://localhost:8600/health");
  http.get("http://localhost:8600/services/health");
  sleep(1);
}
