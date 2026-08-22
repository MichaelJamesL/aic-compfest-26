import { cn } from '../lib/cn'

/** --raised, at the real content's dimensions. No cross-hue shimmer. */
export function Skeleton({ className }: { className?: string }) {
  return <div className={cn('animate-pulse rounded-control bg-raised', className)} />
}

export function SkeletonText({ lines = 3 }: { lines?: number }) {
  return (
    <div className="space-y-2">
      {Array.from({ length: lines }, (_, i) => (
        <Skeleton key={i} className={cn('h-3', i === lines - 1 ? 'w-2/3' : 'w-full')} />
      ))}
    </div>
  )
}
