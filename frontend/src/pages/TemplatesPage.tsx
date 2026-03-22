
import React from 'react';
import { useNavigate } from 'react-router-dom';
import { TemplateManager } from '../components/TemplateManager';

export const TemplatesPage: React.FC = () => {
    const navigate = useNavigate();

    return (
        <div className="flex-1 overflow-y-auto z-10">
            <TemplateManager onBack={() => navigate('/')} />
        </div>
    );
};
