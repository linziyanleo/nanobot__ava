import { useEffect, useState } from 'react'
import {
  ImageIcon, ChevronLeft, ChevronRight, Search, X, AlertCircle, Pencil,
} from 'lucide-react'
import { api } from '../api/client'

interface MediaRecord {
  id: string
  timestamp: string
  prompt: string
  reference_image: string | null
  output_images: string[]
  output_text: string
  model: string
  status: string
  error: string | null
}

interface MediaResponse {
  records: MediaRecord[]
  total: number
  page: number
  size: number
}

function extractFilename(path: string): string {
  return path.split('/').pop() || path
}

function imageUrl(path: string): string {
  const token = localStorage.getItem('token')
  const base = `/api/media/images/${extractFilename(path)}`
  return token ? `${base}?token=${token}` : base
}

export default function MediaPage() {
  const [data, setData] = useState<MediaResponse | null>(null)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const [selected, setSelected] = useState<MediaRecord | null>(null)

  const loadRecords = async () => {
    const params = new URLSearchParams({ page: String(page), size: '18' })
    if (search) params.set('search', search)
    const res = await api<MediaResponse>(`/media/records?${params}`)
    setData(res)
  }

  useEffect(() => { loadRecords() }, [page, search])

  const totalPages = data ? Math.ceil(data.total / data.size) : 0

  const handleSearch = () => {
    setSearch(searchInput)
    setPage(1)
  }

  const clearSearch = () => {
    setSearchInput('')
    setSearch('')
    setPage(1)
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <ImageIcon className="w-6 h-6 text-[var(--accent)]" />
          媒体
        </h1>
        <div className="flex items-center gap-2">
          <div className="relative">
            <input
              type="text"
              placeholder="搜索 prompt..."
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              className="pl-9 pr-8 py-1.5 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border)] text-sm text-[var(--text-primary)] w-56"
            />
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-secondary)]" />
            {searchInput && (
              <button onClick={clearSearch} className="absolute right-2 top-1/2 -translate-y-1/2">
                <X className="w-3.5 h-3.5 text-[var(--text-secondary)] hover:text-[var(--text-primary)]" />
              </button>
            )}
          </div>
          <span className="text-sm text-[var(--text-secondary)]">
            {data?.total ?? 0} 条记录
          </span>
        </div>
      </div>

      {/* Gallery Grid */}
      {data?.records.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-[var(--text-secondary)]">
          <ImageIcon className="w-12 h-12 mb-3 opacity-30" />
          <p className="text-sm">{search ? '没有匹配的记录' : '暂无图片生成记录'}</p>
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-4">
          {data?.records.map((record) => (
            <div
              key={record.id}
              onClick={() => setSelected(record)}
              className="group cursor-pointer bg-[var(--bg-secondary)] border border-[var(--border)] rounded-xl overflow-hidden hover:border-[var(--accent)] transition-all duration-200"
            >
              {/* Image thumbnail */}
              <div className="aspect-square bg-[var(--bg-tertiary)] relative overflow-hidden">
                {record.output_images.length > 0 ? (
                  <img
                    src={imageUrl(record.output_images[0])}
                    alt={record.prompt}
                    className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                    loading="lazy"
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center">
                    <AlertCircle className="w-8 h-8 text-[var(--danger)] opacity-50" />
                  </div>
                )}
                {record.reference_image && (
                  <div className="absolute top-2 right-2 bg-[var(--accent)] text-white rounded-full p-1" title="编辑模式">
                    <Pencil className="w-3 h-3" />
                  </div>
                )}
                {record.status === 'error' && (
                  <div className="absolute inset-0 bg-black/50 flex items-center justify-center">
                    <span className="text-xs text-[var(--danger)] font-medium px-2 py-1 bg-black/60 rounded">失败</span>
                  </div>
                )}
              </div>
              {/* Info */}
              <div className="p-3">
                <p className="text-xs text-[var(--text-primary)] line-clamp-2 leading-relaxed">{record.prompt}</p>
                <p className="text-[10px] text-[var(--text-secondary)] mt-1.5">
                  {new Date(record.timestamp).toLocaleString()}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-6">
          <p className="text-sm text-[var(--text-secondary)]">
            共 {data?.total} 条记录
          </p>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage(Math.max(1, page - 1))}
              disabled={page <= 1}
              className="p-2 rounded-lg bg-[var(--bg-secondary)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] disabled:opacity-30"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <span className="text-sm">{page} / {totalPages}</span>
            <button
              onClick={() => setPage(Math.min(totalPages, page + 1))}
              disabled={page >= totalPages}
              className="p-2 rounded-lg bg-[var(--bg-secondary)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] disabled:opacity-30"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* Detail Modal */}
      {selected && (
        <div
          className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-6"
          onClick={() => setSelected(null)}
        >
          <div
            className="bg-[var(--bg-primary)] border border-[var(--border)] rounded-2xl max-w-3xl w-full max-h-[90vh] overflow-y-auto shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Image */}
            {selected.output_images.length > 0 && (
              <div className="bg-[var(--bg-tertiary)] flex items-center justify-center p-4">
                <img
                  src={imageUrl(selected.output_images[0])}
                  alt={selected.prompt}
                  className="max-h-[50vh] rounded-lg object-contain"
                />
              </div>
            )}
            {/* Details */}
            <div className="p-6 space-y-4">
              <div>
                <label className="text-xs font-medium text-[var(--text-secondary)] uppercase">Prompt</label>
                <p className="mt-1 text-sm text-[var(--text-primary)] leading-relaxed">{selected.prompt}</p>
              </div>
              {selected.reference_image && (
                <div>
                  <label className="text-xs font-medium text-[var(--text-secondary)] uppercase">参考图片</label>
                  <p className="mt-1 text-xs text-[var(--text-secondary)] font-mono break-all">{selected.reference_image}</p>
                </div>
              )}
              {selected.output_text && (
                <div>
                  <label className="text-xs font-medium text-[var(--text-secondary)] uppercase">模型输出文本</label>
                  <p className="mt-1 text-sm text-[var(--text-primary)]">{selected.output_text}</p>
                </div>
              )}
              {selected.error && (
                <div>
                  <label className="text-xs font-medium text-[var(--danger)] uppercase">错误</label>
                  <p className="mt-1 text-sm text-[var(--danger)]">{selected.error}</p>
                </div>
              )}
              <div className="flex items-center gap-6 text-xs text-[var(--text-secondary)]">
                <span>模型: {selected.model}</span>
                <span>状态: <span className={selected.status === 'success' ? 'text-[var(--success)]' : 'text-[var(--danger)]'}>{selected.status}</span></span>
                <span>{new Date(selected.timestamp).toLocaleString()}</span>
              </div>
              <div className="flex justify-end pt-2">
                <button
                  onClick={() => setSelected(null)}
                  className="px-4 py-2 rounded-lg bg-[var(--bg-secondary)] text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-tertiary)] transition-colors"
                >
                  关闭
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
