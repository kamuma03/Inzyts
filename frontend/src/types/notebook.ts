export interface CellOutput {
    output_type: string;
    text?: string;
    data?: { 'image/png'?: string };
}

export interface NotebookCellData {
    cell_type: 'code' | 'markdown';
    source: string;
    outputs: CellOutput[];
}
