import { Download, LoaderCircle, Paperclip, Trash2, Upload } from 'lucide-react'
import { useEffect, useState } from 'react'
import { apiClient } from '../api/client.js'
import { formatDateTime, formatFileSize } from '../lib/formatters.js'
import { canDeleteAttachment, canEditRecord, isForbiddenError } from '../lib/rbac.js'

const ACCEPTED_FILES = '.jpg,.jpeg,.png,.webp,.pdf,.doc,.docx,.xls,.xlsx,.csv'

function uploaderLabel(attachment) {
  if (attachment.uploaded_by_name) {
    return attachment.uploaded_by_name
  }

  if (attachment.uploaded_by_user_id) {
    return `User #${attachment.uploaded_by_user_id}`
  }

  return 'Unknown uploader'
}

export function AttachmentsPanel({ resource, item, token, user }) {
  const [attachments, setAttachments] = useState([])
  const [description, setDescription] = useState('')
  const [selectedFile, setSelectedFile] = useState(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isUploading, setIsUploading] = useState(false)
  const [downloadingId, setDownloadingId] = useState(null)
  const [deletingId, setDeletingId] = useState(null)
  const [error, setError] = useState('')
  const [successMessage, setSuccessMessage] = useState('')

  const canUpload = canEditRecord(resource.key, user, item)

  useEffect(() => {
    let ignore = false

    async function loadAttachments() {
      setIsLoading(true)
      setError('')

      try {
        const response = await apiClient.listAttachments(
          token,
          resource.attachmentEntityType,
          item.id,
        )
        if (!ignore) {
          setAttachments(response)
        }
      } catch (requestError) {
        if (!ignore) {
          setError(requestError)
        }
      } finally {
        if (!ignore) {
          setIsLoading(false)
        }
      }
    }

    loadAttachments()

    return () => {
      ignore = true
    }
  }, [item.id, resource.attachmentEntityType, token])

  async function handleUpload(event) {
    event.preventDefault()
    if (!selectedFile) {
      setError(new Error('Choose a file to upload.'))
      return
    }

    setIsUploading(true)
    setError('')
    setSuccessMessage('')

    try {
      const uploaded = await apiClient.uploadAttachment(
        token,
        resource.attachmentEntityType,
        item.id,
        { file: selectedFile, description },
      )
      setAttachments((current) => [uploaded, ...current])
      setDescription('')
      setSelectedFile(null)
      event.currentTarget.reset()
      setSuccessMessage('Attachment uploaded successfully.')
    } catch (requestError) {
      setError(requestError)
    } finally {
      setIsUploading(false)
    }
  }

  async function handleDownload(attachment) {
    setDownloadingId(attachment.id)
    setError('')
    setSuccessMessage('')

    try {
      const { blob, filename } = await apiClient.downloadAttachment(token, attachment.id)
      const objectUrl = window.URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = objectUrl
      anchor.download = filename
      document.body.append(anchor)
      anchor.click()
      anchor.remove()
      window.URL.revokeObjectURL(objectUrl)
    } catch (requestError) {
      setError(requestError)
    } finally {
      setDownloadingId(null)
    }
  }

  async function handleDelete(attachment) {
    setDeletingId(attachment.id)
    setError('')
    setSuccessMessage('')

    try {
      await apiClient.deleteAttachment(token, attachment.id)
      setAttachments((current) => current.filter((entry) => entry.id !== attachment.id))
      setSuccessMessage('Attachment deleted successfully.')
    } catch (requestError) {
      setError(requestError)
    } finally {
      setDeletingId(null)
    }
  }

  return (
    <section className="rounded-xl border border-stone-200 bg-white p-5 shadow-sm shadow-stone-200/60">
      <div className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
        <div>
          <h2 className="text-lg font-semibold tracking-tight text-stone-950">Attachments & Evidence</h2>
          <p className="mt-1 text-sm text-stone-600">
            Access-controlled uploads for supporting evidence and related documents.
          </p>
        </div>
        <div className="inline-flex items-center gap-2 rounded-full bg-stone-100 px-3 py-1 text-xs font-semibold uppercase tracking-[0.08em] text-stone-600">
          <Paperclip className="size-3.5" />
          {attachments.length} file{attachments.length === 1 ? '' : 's'}
        </div>
      </div>

      {successMessage ? (
        <div className="mt-4 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
          {successMessage}
        </div>
      ) : null}

      {error ? (
        <div className="mt-4 rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">
          {isForbiddenError(error)
            ? 'You do not have permission to perform that attachment action.'
            : error.message ?? 'Unable to manage attachments.'}
        </div>
      ) : null}

      {canUpload ? (
        <form onSubmit={handleUpload} className="mt-5 grid gap-4 rounded-xl border border-dashed border-stone-300 bg-stone-50 p-4 md:grid-cols-[1.2fr_1fr_auto]">
          <label className="space-y-2 text-sm text-stone-700">
            <span className="block font-medium text-stone-900">Select file</span>
            <input
              type="file"
              accept={ACCEPTED_FILES}
              onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
              className="block w-full rounded-md border border-stone-300 bg-white px-3 py-2 text-sm text-stone-700 file:mr-3 file:rounded-md file:border-0 file:bg-stone-900 file:px-3 file:py-2 file:text-sm file:font-medium file:text-white hover:file:bg-stone-700"
            />
          </label>
          <label className="space-y-2 text-sm text-stone-700">
            <span className="block font-medium text-stone-900">Description</span>
            <input
              type="text"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="Optional evidence note"
              className="w-full rounded-md border border-stone-300 bg-white px-3 py-2 text-sm text-stone-700 outline-none transition focus:border-stone-500"
            />
          </label>
          <div className="flex items-end">
            <button
              type="submit"
              disabled={isUploading}
              className="inline-flex w-full items-center justify-center gap-2 rounded-md bg-stone-950 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-stone-800 disabled:cursor-not-allowed disabled:bg-stone-400"
            >
              {isUploading ? <LoaderCircle className="size-4 animate-spin" /> : <Upload className="size-4" />}
              Upload
            </button>
          </div>
        </form>
      ) : (
        <div className="mt-5 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          You can view existing evidence here, but your role cannot upload new files for this record.
        </div>
      )}

      <div className="mt-5">
        {isLoading ? (
          <div className="rounded-lg border border-stone-200 bg-stone-50 px-4 py-6 text-sm text-stone-600">
            Loading attachments...
          </div>
        ) : attachments.length ? (
          <div className="space-y-3">
            {attachments.map((attachment) => (
              <div
                key={attachment.id}
                className="rounded-xl border border-stone-200 bg-stone-50 p-4"
              >
                <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                  <div className="space-y-2">
                    <p className="font-medium text-stone-950">{attachment.original_filename}</p>
                    <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-stone-600">
                      <span>{attachment.content_type}</span>
                      <span>{formatFileSize(attachment.file_size)}</span>
                      <span>{uploaderLabel(attachment)}</span>
                      <span>{formatDateTime(attachment.created_at)}</span>
                    </div>
                    {attachment.description ? (
                      <p className="text-sm leading-6 text-stone-700">{attachment.description}</p>
                    ) : null}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={() => handleDownload(attachment)}
                      disabled={downloadingId === attachment.id}
                      className="inline-flex items-center gap-2 rounded-md border border-stone-300 bg-white px-3 py-2 text-sm font-medium text-stone-700 transition hover:bg-stone-100 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {downloadingId === attachment.id ? (
                        <LoaderCircle className="size-4 animate-spin" />
                      ) : (
                        <Download className="size-4" />
                      )}
                      Download
                    </button>
                    {canDeleteAttachment(user, attachment) ? (
                      <button
                        type="button"
                        onClick={() => handleDelete(attachment)}
                        disabled={deletingId === attachment.id}
                        className="inline-flex items-center gap-2 rounded-md border border-rose-200 bg-white px-3 py-2 text-sm font-medium text-rose-700 transition hover:bg-rose-50 disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        {deletingId === attachment.id ? (
                          <LoaderCircle className="size-4 animate-spin" />
                        ) : (
                          <Trash2 className="size-4" />
                        )}
                        Delete
                      </button>
                    ) : null}
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="rounded-lg border border-stone-200 bg-stone-50 px-4 py-6 text-sm text-stone-600">
            No uploaded evidence files yet.
          </div>
        )}
      </div>
    </section>
  )
}
