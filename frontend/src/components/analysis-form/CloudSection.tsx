import type { FC } from 'react';

interface CloudSectionProps {
    cloudUri: string;
    setCloudUri: (v: string) => void;
}

export const CloudSection: FC<CloudSectionProps> = ({ cloudUri, setCloudUri }) => {
    return (
        <div className="flex flex-col gap-4">
            <input
                type="text"
                placeholder="Cloud URI (e.g. s3://bucket/path/to/file.csv, gs://bucket/file.parquet)"
                value={cloudUri}
                onChange={(e) => setCloudUri(e.target.value)}
                className="w-full p-4 rounded border border-[var(--border-color)] bg-[rgba(0,0,0,0.2)] text-[var(--text-primary)] text-base"
            />
            <div className="text-[0.8rem] text-[var(--text-secondary)]">
                Supported: S3 (s3://), Google Cloud Storage (gs://), Azure Blob (az://, abfs://). Credentials configured server-side via environment variables.
            </div>
        </div>
    );
};
