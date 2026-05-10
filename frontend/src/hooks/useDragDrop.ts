import { useCallback, useState, type DragEvent } from 'react';

/** Reusable drag-and-drop file handling.
 *
 * Owns the `isDragOver` boolean state and returns the three handlers a drop
 * zone needs. Callers receive the raw `File[]` and decide how to filter or
 * route them — that keeps the hook small and makes it easy to share between
 * consumers that accept different extensions.
 *
 * Usage:
 *
 *     const { isDragOver, onDragOver, onDragLeave, onDrop } =
 *         useDragDrop(files => setFiles(files));
 *     <div className={isDragOver ? 'drop-active' : ''}
 *          onDragOver={onDragOver}
 *          onDragLeave={onDragLeave}
 *          onDrop={onDrop} />
 */
export function useDragDrop(onFiles: (files: File[]) => void) {
    const [isDragOver, setIsDragOver] = useState(false);

    const onDragOver = useCallback((e: DragEvent<HTMLDivElement>) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragOver(true);
    }, []);

    const onDragLeave = useCallback((e: DragEvent<HTMLDivElement>) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragOver(false);
    }, []);

    const onDrop = useCallback((e: DragEvent<HTMLDivElement>) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragOver(false);
        onFiles(Array.from(e.dataTransfer.files));
    }, [onFiles]);

    return { isDragOver, onDragOver, onDragLeave, onDrop };
}
