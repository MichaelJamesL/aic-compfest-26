import { Link } from 'react-router'
import { SlidersHorizontal } from 'lucide-react'
import { AppShell } from '../shell/AppShell'
import { api } from '../api/client'
import { useRequest } from '../lib/useRequest'
import { formatDateTime } from '../lib/format'
import { WORK_ORDER, priorityLabel, priorityTone } from '../lib/severity'
import { Card, SectionTitle } from '../ui/Card'
import { Badge, StatusDot } from '../ui/Badge'
import { Button } from '../ui/Button'
import { Table, Td, Th, Tr } from '../ui/Table'
import { EmptyState, ErrorState } from '../ui/States'
import { Skeleton } from '../ui/Skeleton'

export function WorkOrdersScreen() {
  const { data, error, loading, reload } = useRequest(() => api.workOrders(), [])

  return (
    <AppShell title="Work order" subtitle="Usulan AI yang menunggu keputusan coordinator.">
      <Card>
        <div className="flex items-center gap-3">
          <SectionTitle>Semua work order</SectionTitle>
          <Button size="sm" className="ml-auto" icon={<SlidersHorizontal size={14} />} disabled>
            Filter
          </Button>
        </div>

        {loading && <Skeleton className="mt-4 h-40" />}
        {error != null && <ErrorState error={error} onRetry={reload} />}
        {data?.length === 0 && (
          <EmptyState
            action={
              <Link to="/analyze">
                <Button variant="primary">Jalankan analisis</Button>
              </Link>
            }
          >
            Belum ada work order. Work order dibuat dari hasil analisis.
          </EmptyState>
        )}

        {data && data.length > 0 && (
          <div className="mt-4">
            <Table>
              <thead>
                <tr>
                  <Th>No</Th>
                  <Th>Judul</Th>
                  <Th>Prioritas</Th>
                  <Th>Status</Th>
                  <Th align="right">Dibuat</Th>
                </tr>
              </thead>
              <tbody>
                {data.map((order, index) => {
                  const state = WORK_ORDER[order.status]
                  return (
                    <Tr key={order.id}>
                      <Td tone="muted">{index + 1}</Td>
                      <Td tone="primary">
                        <Link to={`/work-orders/${order.id}`} className="hover:underline">
                          {order.title}
                        </Link>
                      </Td>
                      <Td>
                        <Badge tone={priorityTone(order.priority)}>
                          {priorityLabel(order.priority)}
                        </Badge>
                      </Td>
                      <Td>
                        <StatusDot tone={state.tone}>{state.label}</StatusDot>
                      </Td>
                      <Td align="right">{formatDateTime(order.created_at)}</Td>
                    </Tr>
                  )
                })}
              </tbody>
            </Table>
          </div>
        )}
      </Card>
    </AppShell>
  )
}
