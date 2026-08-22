import { useState } from 'react'
import { FileSpreadsheet, FileText, History, RefreshCw } from 'lucide-react'
import { AppShell } from '../shell/AppShell'
import { api, errorCopy } from '../api/client'
import { useRequest } from '../lib/useRequest'
import { formatBytes } from '../lib/format'
import { INGESTION } from '../lib/severity'
import { Card, SectionTitle } from '../ui/Card'
import { Button } from '../ui/Button'
import { DropZone } from '../ui/DropZone'
import { StatusDot } from '../ui/Badge'
import { Table, Td, Th, Tr } from '../ui/Table'
import { EmptyState, ErrorState } from '../ui/States'
import { Skeleton } from '../ui/Skeleton'

export function SetupScreen() {
  const assets = useRequest(() => api.assets(), [])
  const documents = useRequest(() => api.documents(), [])
  const [busy, setBusy] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [error, setError] = useState<unknown>(null)

  async function guard(key: string, work: () => Promise<string>) {
    setBusy(key)
    setError(null)
    setNotice(null)
    try {
      setNotice(await work())
    } catch (err) {
      setError(err)
    } finally {
      setBusy(null)
    }
  }

  return (
    <AppShell
      title="Setup"
      subtitle="Daftar mesin, SOP, dan histori maintenance — dasar yang bisa dikutip analisis."
    >
      <div className="grid grid-cols-12 gap-3">
        <Card className="col-span-12 md:col-span-4">
          <SectionTitle>Daftar mesin</SectionTitle>
          <p className="mt-2 text-xs text-faint">
            {assets.data ? `${assets.data.length} mesin terdaftar` : 'Memuat…'}
          </p>
          <div className="mt-4">
            <DropZone
              label="Unggah daftar mesin"
              hint="CSV atau JSON · kolom name, asset_type, criticality"
              icon={<FileSpreadsheet size={20} />}
              accept=".csv,.json"
              disabled={busy === 'assets'}
              onFiles={([file]) =>
                guard('assets', async () => {
                  const result = await api.importAssets(file)
                  assets.reload()
                  const failed = result.errors.length
                  return `${result.imported} mesin diimpor${failed ? `, ${failed} baris ditolak` : ''}.`
                })
              }
            />
          </div>
        </Card>

        <Card className="col-span-12 md:col-span-4">
          <SectionTitle>SOP & manual</SectionTitle>
          <p className="mt-2 text-xs text-faint">Masuk ke knowledge base sebagai rujukan.</p>
          <div className="mt-4">
            <DropZone
              label="Unggah SOP"
              hint=".txt .md .pdf · maks 10 MB"
              icon={<FileText size={20} />}
              accept=".txt,.md,.pdf,.json,.csv"
              multiple
              disabled={busy === 'sop'}
              onFiles={(files) =>
                guard('sop', async () => {
                  for (const file of files) await api.uploadDocument(file, 'sop')
                  documents.reload()
                  return `${files.length} dokumen diunggah. Klik "Indeks" agar bisa dikutip.`
                })
              }
            />
          </div>
        </Card>

        <Card className="col-span-12 md:col-span-4">
          <SectionTitle>Histori maintenance</SectionTitle>
          <p className="mt-2 text-xs text-faint">Dibaca sebagai referensi kegagalan berulang.</p>
          <div className="mt-4">
            <DropZone
              label="Unggah histori"
              hint=".csv .txt .md · maks 10 MB"
              icon={<History size={20} />}
              accept=".txt,.md,.csv,.json"
              multiple
              disabled={busy === 'log'}
              onFiles={(files) =>
                guard('log', async () => {
                  for (const file of files) await api.uploadDocument(file, 'log')
                  documents.reload()
                  return `${files.length} berkas histori diunggah.`
                })
              }
            />
          </div>
        </Card>
      </div>

      {notice && <p className="mt-3 text-[13px] text-ok-text">{notice}</p>}
      {error != null && <p className="mt-3 text-[13px] text-crit-text">{errorCopy(error)}</p>}

      <Card className="mt-3">
        <SectionTitle>Dokumen</SectionTitle>

        {documents.loading && <Skeleton className="mt-4 h-32" />}
        {documents.error != null && (
          <ErrorState error={documents.error} onRetry={documents.reload} />
        )}

        {documents.data?.length === 0 && (
          <EmptyState>
            Belum ada dokumen. Unggah SOP dan histori agar analisis punya dasar yang bisa
            dikutip.
          </EmptyState>
        )}

        {documents.data && documents.data.length > 0 && (
          <div className="mt-4">
            <Table>
              <thead>
                <tr>
                  <Th>Nama</Th>
                  <Th>Jenis</Th>
                  <Th align="right">Ukuran</Th>
                  <Th>Status</Th>
                  <Th align="right">Aksi</Th>
                </tr>
              </thead>
              <tbody>
                {documents.data.map((document) => {
                  const state = INGESTION[document.ingestion_status]
                  return (
                    <Tr key={document.id}>
                      <Td tone="primary">{document.title}</Td>
                      <Td tone="muted">{document.kind}</Td>
                      <Td align="right">{formatBytes(document.size_bytes)}</Td>
                      <Td>
                        <StatusDot tone={state.tone}>
                          <span title={document.ingestion_error ?? state.hint}>{state.label}</span>
                        </StatusDot>
                      </Td>
                      <Td align="right">
                        {document.ingestion_status !== 'ready' && (
                          <Button
                            size="sm"
                            variant="ghost"
                            icon={<RefreshCw size={13} />}
                            disabled={busy === document.id}
                            onClick={() =>
                              guard(document.id, async () => {
                                const updated = await api.reindexDocument(document.id)
                                documents.reload()
                                return updated.ingestion_status === 'ready'
                                  ? `${updated.title} terindeks.`
                                  : `Pengindeksan gagal: ${updated.ingestion_error ?? 'tidak diketahui'}`
                              })
                            }
                          >
                            {document.ingestion_status === 'failed' ? 'Ulangi' : 'Indeks'}
                          </Button>
                        )}
                      </Td>
                    </Tr>
                  )
                })}
              </tbody>
            </Table>

            <p className="mt-4 text-xs leading-5 text-faint">
              Dokumen berstatus “Belum diindeks” belum masuk knowledge base dan tidak akan
              muncul pada daftar sumber di hasil analisis.
            </p>
          </div>
        )}
      </Card>
    </AppShell>
  )
}
