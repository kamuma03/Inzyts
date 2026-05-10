/** State-pattern primitives. See docs/state-patterns.md (or the v1 spec) for
 *  the decision tree. The 30-second version:
 *
 *    Loading + shape known   → <Skeleton> / <SkeletonCard> / <SkeletonList>
 *    Loading + shape unknown → <Spinner> / <InlineSpinner> (panel/inline)
 *    Loading ambient         → <ProgressPill intent="accent">
 *    Empty                   → <EmptyState>
 *    Error in panel          → <ErrorState onRetry=…>
 *    Error in field/form     → <InlineError>
 *    Error background        → <Toast intent="bad">  (handled by Toast.tsx)
 */

export { Skeleton, SkeletonLine, SkeletonCard, SkeletonList } from './Skeleton';
export { Spinner, InlineSpinner } from './Spinner';
export { EmptyState, type EmptyStateIcon } from './EmptyState';
export { ErrorState } from './ErrorState';
export { InlineError } from './InlineError';
export { ProgressPill } from './ProgressPill';
