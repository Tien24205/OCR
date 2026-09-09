import { useEffect, useState } from 'react'
import { api, type HealthResponse } from '../api/client'

/**
 * Hien thi trang thai ket noi backend va cau hinh dich vu.
 *
 * Day cung la checklist Ngay 2 nhin thay duoc: khi nao hai dong OCR va
 * Gemini chuyen sang mau xanh thi phu thuoc rui ro cao nhat da duoc go bo.
 */
export function HealthBanner() {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api
      .health()
      .then(setHealth)
      .catch((e: Error) => setError(e.message))
  }, [])

  if (error) {
    return (
      <div className="panel">
        <strong className="warn">Không kết nối được backend.</strong>
        <p className="muted">
          {error}. Kiểm tra đã chạy <code>uvicorn app.main:app --reload</code> trong
          thư mục <code>backend/</code> chưa.
        </p>
      </div>
    )
  }

  if (!health) return <div className="panel muted">Đang kiểm tra backend…</div>

  const c = health.config
  const flag = (ok: boolean) =>
    ok ? <span className="ok">sẵn sàng</span> : <span className="warn">chưa cấu hình</span>

  return (
    <div className="panel">
      <strong className="ok">Backend đang chạy</strong>{' '}
      <span className="muted">({health.env})</span>
      <table className="kv" style={{ marginTop: '0.75rem' }}>
        <tbody>
          <tr>
            <td>Nhà cung cấp OCR</td>
            <td>
              <code>{c.ocr_provider}</code> — {flag(c.ocr_credentials_present)}
            </td>
          </tr>
          <tr>
            <td>Bộ trích xuất trường</td>
            <td>
              <code>{c.extractor}</code> —{' '}
              {flag(c.gemini_key_present && c.gemini_model_set)}
            </td>
          </tr>
          <tr>
            <td>Tra cứu doanh nghiệp</td>
            <td>{c.enrich_enabled ? 'bật' : 'tắt'}</td>
          </tr>
        </tbody>
      </table>
    </div>
  )
}
