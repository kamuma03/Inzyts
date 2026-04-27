const truthy = (v: unknown): boolean => {
    if (typeof v === 'boolean') return v;
    if (typeof v !== 'string') return false;
    const s = v.toLowerCase().trim();
    return s === '1' || s === 'true' || s === 'yes' || s === 'on';
};

export const featureFlags = {
    commandCenter: truthy(import.meta.env.VITE_FEATURE_COMMAND_CENTER),
};
