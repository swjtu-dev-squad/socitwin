import React, { useState, useRef, useCallback } from 'react'
import { Upload, CheckCircle, XCircle, AlertTriangle, FileText, Database } from 'lucide-react'

interface User {
  id: string
  [key: string]: unknown
}

interface Relationship {
  source: string
  target: string
  [key: string]: unknown
}

interface Post {
  id: string
  [key: string]: unknown
}

interface ValidationResult {
  status: 'valid' | 'invalid' | 'error'
  valid?: boolean
  errors: string[]
  warnings: string[]
  stats: { users: number; relationships: number; posts: number }
  preview?: {
    users: User[]
    relationships: Relationship[]
    posts: Post[]
  }
  format?: string
  message?: string
}

interface ImportResult {
  status: 'success' | 'error'
  message: string
  stats?: { users: number; relationships: number; posts: number }
  warnings?: string[]
  agentConfig?: Record<string, unknown>[]
  analytics?: Record<string, unknown>
}

export function DatasetImport() {
  const [file, setFile] = useState<File | null>(null)
  const [validating, setValidating] = useState(false)
  const [importing, setImporting] = useState(false)
  const [validation, setValidation] = useState<ValidationResult | null>(null)
  const [importResult, setImportResult] = useState<ImportResult | null>(null)
  const [dragOver, setDragOver] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleFile = useCallback(async (f: File) => {
    setFile(f)
    setValidation(null)
    setImportResult(null)
    setValidating(true)
    try {
      const formData = new FormData()
      formData.append('file', f)
      const res = await fetch('/api/dataset/validate', { method: 'POST', body: formData })
      const data = await res.json()
      setValidation(data)
    } catch (e: unknown) {
      const errorMessage = e instanceof Error ? e.message : 'Unknown error'
      setValidation({
        status: 'error',
        errors: [errorMessage],
        warnings: [],
        stats: { users: 0, relationships: 0, posts: 0 },
        message: errorMessage,
      })
    } finally {
      setValidating(false)
    }
  }, [])

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      setDragOver(false)
      const f = e.dataTransfer.files[0]
      if (f) handleFile(f)
    },
    [handleFile]
  )

  const handleImport = async () => {
    if (!file || !validation?.valid) return
    setImporting(true)
    try {
      const formData = new FormData()
      formData.append('file', file)
      const res = await fetch('/api/dataset/import', { method: 'POST', body: formData })
      const data = await res.json()
      setImportResult(data)
    } catch (e: unknown) {
      const errorMessage = e instanceof Error ? e.message : 'Unknown error'
      setImportResult({ status: 'error', message: errorMessage })
    } finally {
      setImporting(false)
    }
  }

  const reset = () => {
    setFile(null)
    setValidation(null)
    setImportResult(null)
    if (inputRef.current) inputRef.current.value = ''
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Upload Zone */}
      {!file && (
        <div
          className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors ${
            dragOver
              ? 'border-accent bg-accent/5'
              : 'border-border-default hover:border-border-strong'
          }`}
          onDragOver={e => {
            e.preventDefault()
            setDragOver(true)
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          onClick={() => inputRef.current?.click()}
        >
          <Upload className="w-8 h-8 mx-auto mb-3 text-text-tertiary" />
          <p className="text-sm font-medium text-text-secondary">拖拽文件到此处，或点击上传</p>
          <p className="text-xs text-text-tertiary mt-1">支持 JSON / CSV 格式，最大 10MB</p>
          <input
            ref={inputRef}
            type="file"
            accept=".json,.csv"
            className="hidden"
            onChange={e => {
              const f = e.target.files?.[0]
              if (f) handleFile(f)
            }}
          />
        </div>
      )}

      {/* File Selected */}
      {file && (
        <div className="flex items-center gap-3 bg-bg-primary rounded-lg p-3">
          <FileText className="w-5 h-5 text-accent flex-shrink-0" />
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium truncate">{file.name}</p>
            <p className="text-xs text-text-tertiary">{(file.size / 1024).toFixed(1)} KB</p>
          </div>
          <button
            onClick={reset}
            className="text-text-tertiary hover:text-text-primary text-xs px-2 py-1 rounded hover:bg-bg-secondary"
          >
            重新选择
          </button>
        </div>
      )}

      {/* Validating */}
      {validating && (
        <div className="flex items-center gap-2 text-xs text-text-tertiary">
          <div className="w-4 h-4 border-2 border-accent border-t-transparent rounded-full animate-spin" />
          正在校验文件格式...
        </div>
      )}

      {/* Validation Result */}
      {validation && !validating && (
        <div
          className={`rounded-lg p-4 text-xs ${
            validation.status === 'valid'
              ? 'bg-emerald-500/10 border border-emerald-500/20'
              : validation.status === 'invalid'
                ? 'bg-rose-500/10 border border-rose-500/20'
                : 'bg-amber-500/10 border border-amber-500/20'
          }`}
        >
          <div className="flex items-center gap-2 mb-2">
            {validation.status === 'valid' ? (
              <CheckCircle className="w-4 h-4 text-emerald-500" />
            ) : validation.status === 'invalid' ? (
              <XCircle className="w-4 h-4 text-rose-500" />
            ) : (
              <AlertTriangle className="w-4 h-4 text-amber-500" />
            )}
            <span className="font-bold">
              {validation.status === 'valid'
                ? '校验通过'
                : validation.status === 'invalid'
                  ? '校验失败'
                  : '校验出错'}
            </span>
            {validation.format && (
              <span className="ml-auto text-text-tertiary uppercase">{validation.format}</span>
            )}
          </div>

          {/* Stats */}
          {validation.stats && (
            <div className="flex gap-4 mb-2">
              <span>
                用户: <strong>{validation.stats.users}</strong>
              </span>
              <span>
                关系: <strong>{validation.stats.relationships}</strong>
              </span>
              <span>
                帖子: <strong>{validation.stats.posts}</strong>
              </span>
            </div>
          )}

          {/* Errors */}
          {validation.errors?.length > 0 && (
            <div className="mt-2">
              <p className="font-bold text-rose-400 mb-1">错误 ({validation.errors.length}):</p>
              {validation.errors.slice(0, 5).map((e, i) => (
                <p key={i} className="text-rose-300">
                  • {e}
                </p>
              ))}
              {validation.errors.length > 5 && (
                <p className="text-rose-300">...还有 {validation.errors.length - 5} 条错误</p>
              )}
            </div>
          )}

          {/* Warnings */}
          {validation.warnings?.length > 0 && (
            <div className="mt-2">
              <p className="font-bold text-amber-400 mb-1">警告 ({validation.warnings.length}):</p>
              {validation.warnings.slice(0, 3).map((w, i) => (
                <p key={i} className="text-amber-300">
                  • {w}
                </p>
              ))}
            </div>
          )}

          {/* Preview Table */}
          {validation.preview?.users && validation.preview.users.length > 0 && (
            <div className="mt-3">
              <p className="font-bold text-text-secondary mb-1">
                用户预览（前 {validation.preview.users.length} 条）:
              </p>
              <div className="overflow-x-auto">
                <table className="w-full text-[10px] border-collapse">
                  <thead>
                    <tr className="text-text-tertiary">
                      {Object.keys(validation.preview.users[0])
                        .slice(0, 5)
                        .map(k => (
                          <th key={k} className="text-left pr-3 pb-1">
                            {k}
                          </th>
                        ))}
                    </tr>
                  </thead>
                  <tbody>
                    {validation.preview.users.map((u, i) => (
                      <tr key={i} className="border-t border-border-default/30">
                        {Object.values(u)
                          .slice(0, 5)
                          .map((v: unknown, j) => (
                            <td key={j} className="pr-3 py-0.5 max-w-[120px] truncate">
                              {String(v ?? '')}
                            </td>
                          ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Import Button */}
      {validation?.status === 'valid' && !importResult && (
        <button
          onClick={handleImport}
          disabled={importing}
          className="flex items-center justify-center gap-2 bg-accent hover:bg-accent-hover text-white rounded-lg px-4 py-2 text-sm font-bold transition-colors disabled:opacity-50"
        >
          {importing ? (
            <>
              <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
              导入中...
            </>
          ) : (
            <>
              <Database className="w-4 h-4" />
              导入并生成图表
            </>
          )}
        </button>
      )}

      {/* Import Result */}
      {importResult && (
        <div
          className={`rounded-lg p-4 text-xs ${
            importResult.status === 'success'
              ? 'bg-emerald-500/10 border border-emerald-500/20'
              : 'bg-rose-500/10 border border-rose-500/20'
          }`}
        >
          <div className="flex items-center gap-2 mb-2">
            {importResult.status === 'success' ? (
              <CheckCircle className="w-4 h-4 text-emerald-500" />
            ) : (
              <XCircle className="w-4 h-4 text-rose-500" />
            )}
            <span className="font-bold">
              {importResult.status === 'success' ? '导入成功' : '导入失败'}
            </span>
          </div>
          <p className="text-text-secondary">{importResult.message}</p>
          {importResult.analytics && (
            <div className="mt-2 flex gap-4">
              <span>
                总 Agents: <strong>{String(importResult.analytics.totalAgents ?? '0')}</strong>
              </span>
              <span>
                总帖子: <strong>{String(importResult.analytics.totalPosts ?? '0')}</strong>
              </span>
              <span>
                总关系: <strong>{String(importResult.analytics.totalRelationships ?? '0')}</strong>
              </span>
            </div>
          )}
          {importResult.warnings && importResult.warnings.length > 0 && (
            <div className="mt-2">
              {importResult.warnings.slice(0, 3).map((w, i) => (
                <p key={i} className="text-amber-300">
                  ⚠ {w}
                </p>
              ))}
            </div>
          )}
          <button
            onClick={reset}
            className="mt-3 text-text-tertiary hover:text-text-primary underline"
          >
            重新导入
          </button>
        </div>
      )}
    </div>
  )
}
