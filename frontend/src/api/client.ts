import axios, { AxiosError, AxiosResponse } from "axios";
import type { APIResponse } from "./types";

export async function request<T>(config: {
  method?: string;
  url: string;
  data?: unknown;
}): Promise<T> {
  const resp: AxiosResponse<APIResponse<T>> = await client.request<
    APIResponse<T>
  >({
    method: config.method ?? "POST",
    url: config.url,
    data: config.data,
  });
  if (resp.data.code !== 0) {
    throw new Error(resp.data.message ?? "业务错误");
  }
  return resp.data.data;
}

const client = axios.create({
  baseURL: "/api",
  timeout: 60_000,
});

client.interceptors.request.use((cfg) => {
  const token = localStorage.getItem("access_token");
  if (token) {
    cfg.headers.Authorization = `Bearer ${token}`;
  }
  return cfg;
});

client.interceptors.response.use(
  (resp: AxiosResponse) => resp,
  (err: AxiosError) => {
    if (err.response?.status === 401) {
      localStorage.removeItem("access_token");
      localStorage.removeItem("username");
      window.location.href = "/login";
    }
    return Promise.reject(err);
  },
);

export default client;