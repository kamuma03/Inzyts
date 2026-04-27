import { type FC } from 'react';
import type { CellOutput } from '../types';
import { TextOutput } from './TextOutput';
import { ErrorOutput } from './ErrorOutput';
import { RichOutput } from './RichOutput';

interface CellOutputViewProps {
    output: CellOutput;
}

/** Dispatches a single output to the correct renderer based on output_type. */
export const CellOutputView: FC<CellOutputViewProps> = ({ output }) => {
    switch (output.output_type) {
        case 'stream':
            return <TextOutput output={output} />;
        case 'error':
            return <ErrorOutput output={output} />;
        case 'execute_result':
        case 'display_data':
            return <RichOutput output={output} />;
        default:
            return null;
    }
};
