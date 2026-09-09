import { useParams } from 'react-router-dom'

/** Ngay 5: anh goc ben trai, form sua ben phai, co mau cho tung truong. */
export function ReviewPage() {
  const { scanId } = useParams()
  return (
    <div className="panel">
      <h2>Kiểm tra và chỉnh sửa</h2>
      <p className="muted">
        Bản quét <code>{scanId}</code>. Ngày 4 hiển thị kết quả trích xuất, ngày 5
        thêm form sửa và cờ “cần kiểm tra”.
      </p>
    </div>
  )
}
