import { cn } from '../lib/cn'

/** --raised, at the real content's dimensions. No cross-hue shimmer. */
export function Skeleton({ className, label }: { className?: string; label?: string }) {
  return (
    <div
      role="status"
      aria-label={label ?? 'Memuat'}
      className={cn('animate-pulse rounded-control bg-surface-raised', className)}
    />
  )
}

export function SkeletonText({ lines = 3 }: { lines?: number }) {
  return (
    <div className="space-y-2" role="status" aria-label="Memuat">
      {Array.from({ length: lines }, (_, i) => (
        <div
          key={i}
          className={cn('animate-pulse rounded-control bg-surface-raised h-3', i === lines - 1 ? 'w-2/3' : 'w-full')}
        />
      ))}
    </div>
  )
}
