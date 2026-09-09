// Lop goi API duy nhat cua frontend.
//
// QUY TAC: file nay khong bao gio chua API key. Frontend chi noi chuyen voi
// backend cua chinh minh; moi khoa dich vu (Google Vision, Gemini) nam o backend.

const BASE = import.meta.env.VITE_API_BASE_URL ?? ''

export interface ApiErrorBody {
  error: { code: string; message: string; retryable: boolean }
}

export class ApiError extends Error {
  // Khai bao truong tuong minh: TypeScript 6 bat `erasableSyntaxOnly`,
  // khong cho phep khai bao truong ngay trong tham so constructor.
  readonly code: string
  readonly retryable: boolean
  readonly status: number

  constructor(code: string, message: string, retryable: boolean, status: number) {
    super(message)
    this.code = code
    this.retryable = retryable
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, init)
  if (!res.ok) {
    let body: Partial<ApiErrorBody> = {}
    try {
      body = await res.json()
    } catch {
      // backend tra ve HTML hoac rong -> giu thong bao mac dinh
    }
    throw new ApiError(
      body.error?.code ?? 'UNKNOWN',
      body.error?.message ?? `Loi ${res.status}`,
      body.error?.retryable ?? false,
      res.status,
    )
  }
  return res.json() as Promise<T>
}

// --- Kieu du lieu dung chung voi backend ---

export interface HealthResponse {
  status: string
  env: string
  config: {
    ocr_provider: string
    ocr_credentials_present: boolean
    extractor: string
    gemini_key_present: boolean
    gemini_model_set: boolean
    enrich_enabled: boolean
  }
}

export const api = {
  health: () => request<HealthResponse>('/api/health'),
}
