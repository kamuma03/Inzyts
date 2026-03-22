import React, { useCallback, type FC, type ChangeEvent, type DragEvent } from 'react';
import { UploadCloud } from 'lucide-react';

interface UploadedFile {
    filename: string;
    saved_path: string;
    size: number;
}

interface FileUploadSectionProps {
    files: File[];
    setFiles: (files: File[]) => void;
    uploadedPaths: string[];
    uploadedFiles: UploadedFile[];
    loading: boolean;
    isDragOver: boolean;
    setIsDragOver: (v: boolean) => void;
    fileInputRef: React.RefObject<HTMLInputElement>;
    setError: (err: string | null) => void;
    onUpload: () => void;
    onClearFiles: () => void;
}

const VALID_EXTENSIONS = ['.csv', '.parquet', '.log', '.xlsx', '.xls', '.json'];

export const FileUploadSection: FC<FileUploadSectionProps> = ({
    files, setFiles, uploadedPaths, uploadedFiles, loading, isDragOver,
    setIsDragOver, fileInputRef, setError, onUpload, onClearFiles,
}) => {
    const handleDragOver = useCallback((e: DragEvent<HTMLDivElement>) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragOver(true);
    }, [setIsDragOver]);

    const handleDragLeave = useCallback((e: DragEvent<HTMLDivElement>) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragOver(false);
    }, [setIsDragOver]);

    const handleDrop = useCallback((e: DragEvent<HTMLDivElement>) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragOver(false);

        const droppedFiles = Array.from(e.dataTransfer.files);
        const validFiles = droppedFiles.filter(f =>
            VALID_EXTENSIONS.some(ext => f.name.toLowerCase().endsWith(ext))
        );

        if (validFiles.length === 0) {
            setError("No valid files. Accepted: CSV, Parquet, JSON, XLSX, LOG");
            return;
        }
        if (validFiles.length > 6) {
            setError("Maximum 6 files allowed.");
            return;
        }

        setFiles(validFiles);
        setError(null);
    }, [setFiles, setError, setIsDragOver]);

    const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files.length > 0) {
            const selectedFiles = Array.from(e.target.files);
            if (selectedFiles.length > 6) {
                setError("Maximum 6 files allowed.");
                return;
            }
            setFiles(selectedFiles);
            setError(null);
        }
    };

    return (
        <div className="flex flex-col gap-4 p-2">
            {/* Drag-and-drop zone */}
            <div
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
                className={`border-2 border-dashed rounded-xl py-8 px-6 flex flex-col items-center gap-3 cursor-pointer transition-all duration-200 ${isDragOver ? 'border-[var(--bg-turquoise-surf)] bg-[rgba(76,201,240,0.08)]' : 'border-[var(--border-color)] bg-[rgba(0,0,0,0.1)]'}`}
            >
                <UploadCloud size={36} color={isDragOver ? 'var(--bg-turquoise-surf)' : 'var(--text-secondary)'} className="transition-colors duration-200" />
                <div className="text-center">
                    <div className={`text-[0.95rem] font-medium ${isDragOver ? 'text-[var(--bg-turquoise-surf)]' : 'text-[var(--text-primary)]'}`}>
                        {isDragOver ? 'Drop files here' : 'Drop files here or click to browse'}
                    </div>
                    <div className="text-[0.8rem] text-[var(--text-secondary)] mt-1">
                        CSV, Parquet, JSON, XLSX, LOG (max 6 files)
                    </div>
                </div>
                <input
                    ref={fileInputRef}
                    id="file-upload-input"
                    type="file"
                    accept=".csv,.parquet,.log,.xlsx,.xls,.json"
                    multiple
                    onChange={handleFileChange}
                    className="hidden"
                />
            </div>

            {/* Selected files ready to upload */}
            {files.length > 0 && (
                <div className="flex flex-col gap-2">
                    <div className="text-[0.85rem] text-[var(--text-secondary)]">
                        Selected: {files.map(f => f.name).join(', ')}
                    </div>
                    <button
                        onClick={onUpload}
                        disabled={loading}
                        className={`flex items-center justify-center gap-2 py-3 px-8 bg-[var(--bg-blue-green)] text-white border-none rounded-md cursor-pointer font-semibold transition-opacity duration-200 ${loading ? 'opacity-70' : 'opacity-100'}`}
                    >
                        <UploadCloud size={18} /> {loading ? 'Uploading...' : 'Upload Selected Files'}
                    </button>
                </div>
            )}

            {/* Uploaded Files List */}
            {uploadedPaths.length > 0 && (
                <div className="bg-[rgba(0,0,0,0.2)] rounded-lg p-3">
                    <div className="flex justify-between items-center mb-2">
                        <div className="text-[0.85rem] text-[var(--bg-turquoise-surf)] font-semibold">Uploaded ({uploadedPaths.length})</div>
                        <button onClick={onClearFiles} className="bg-none border-none text-[#fc8181] text-[0.8rem] cursor-pointer underline">Clear</button>
                    </div>
                    <ul className="list-none p-0 m-0">
                        {uploadedFiles.map((f, i) => (
                            <li key={i} className="text-[0.85rem] text-[var(--text-primary)] py-[0.3rem] flex justify-between items-center">
                                <span className="flex items-center gap-2">
                                    <span className="w-1.5 h-1.5 rounded-full bg-[var(--bg-turquoise-surf)] shrink-0" />
                                    {f.filename}
                                </span>
                                <span className="text-[var(--text-secondary)] text-[0.8rem]">{(f.size / 1024).toFixed(1)} KB</span>
                            </li>
                        ))}
                    </ul>
                </div>
            )}
        </div>
    );
};
