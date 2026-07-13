import axios, { AxiosInstance, AxiosError } from 'axios';

const request: AxiosInstance = axios.create({
  baseURL: '/api/v1',
  timeout: 180000,
  headers: {
    'Content-Type': 'application/json',
  },
});

request.interceptors.response.use(
  (response) => {
    return response.data;
  },
  (error: AxiosError<any>) => {
    if (error.response?.data) {
      const detail = error.response.data.detail;
      const msg = typeof detail === 'string' ? detail : (detail?.message || `请求错误: ${error.response.status}`);
      console.error('[API Error]', msg);
    } else if (error.request) {
      console.error('[Network Error] 请检查后端服务是否启动');
    } else {
      console.error('[Request Error]', error.message);
    }
    return Promise.reject(error);
  }
);

export default request;
